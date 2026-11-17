// Verify the agent-produced sand simulator in real headless Chrome via CDP.
// Palette-free strategy: analyze per-pixel variance of horizontal strips of the
// world canvas (via getImageData) — sand arrival/departure changes variance.
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const DIR = process.argv[2] || 'sand-simulator';
const PAGE = `file:///home/chris/ai/super-agent/${DIR}/index.html`;
const SHOTS = `/tmp/sand-shots-${DIR.replace(/\W/g, '_')}`;
fs.mkdirSync(SHOTS, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ---- launch chrome, parse DevTools ws url ----
const chrome = spawn('google-chrome-stable', [
  '--headless=new', '--remote-debugging-port=0',
  `--user-data-dir=${SHOTS}/profile`,
  '--no-first-run', '--disable-extensions', '--mute-audio',
  '--window-size=520,640',
  PAGE,
], { stdio: ['ignore', 'pipe', 'pipe'] });

const wsUrl = await new Promise((res, rej) => {
  let acc = '';
  const to = setTimeout(() => rej(new Error('no DevTools url in stderr')), 20000);
  chrome.stderr.on('data', (d) => {
    acc += d;
    const m = acc.match(/DevTools listening on (ws:\/\/\S+)/);
    if (m) { clearTimeout(to); res(m[1]); }
  });
});
const port = new URL(wsUrl).port;
const targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json();
const page = targets.find((t) => t.type === 'page');
if (!page) throw new Error('no page target');

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

let id = 0;
const pending = new Map();
const pageErrors = [];
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) {
    const p = pending.get(m.id); pending.delete(m.id);
    m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result);
  } else if (m.method === 'Runtime.exceptionThrown') {
    pageErrors.push(m.params.exceptionDetails?.exception?.description || m.params.exceptionDetails?.text);
  } else if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
    pageErrors.push(m.params.args?.map((a) => a.value ?? a.description).join(' '));
  }
};
const send = (method, params = {}) => new Promise((res, rej) => {
  const i = ++id; pending.set(i, { res, rej });
  ws.send(JSON.stringify({ id: i, method, params }));
});
const evalJs = async (expr) => {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  if (r.exceptionDetails) throw new Error('page eval failed: ' + JSON.stringify(r.exceptionDetails).slice(0, 300));
  return r.result.value;
};
const shot = async (name) => {
  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(`${SHOTS}/${name}.png`, Buffer.from(data, 'base64'));
  console.log(`[shot] ${name}.png`);
};

await send('Runtime.enable');
await send('Page.enable');
await send('Page.bringToFront');

// ---- analysis helpers injected into the page ----
const ANALYZE = `(() => {
  const cs = [...document.querySelectorAll('canvas')];
  if (!cs.length) return null;
  const c = cs.reduce((a, b) => (a.width * a.height >= b.width * b.height ? a : b));
  const cc = document.createElement('canvas');
  cc.width = c.width; cc.height = c.height;
  const x = cc.getContext('2d');
  x.drawImage(c, 0, 0);
  const d = x.getImageData(0, 0, cc.width, cc.height).data;
  const stripVar = (y0, y1) => {
    let n = 0; const mean = [0, 0, 0];
    for (let y = y0; y < Math.min(y1, cc.height); y++)
      for (let px = 0; px < cc.width; px++) {
        const i = (y * cc.width + px) * 4;
        mean[0] += d[i]; mean[1] += d[i + 1]; mean[2] += d[i + 2]; n++;
      }
    mean[0] /= n; mean[1] /= n; mean[2] /= n;
    let v = 0;
    for (let y = y0; y < Math.min(y1, cc.height); y++)
      for (let px = 0; px < cc.width; px++) {
        const i = (y * cc.width + px) * 4;
        v += ((d[i] - mean[0]) ** 2 + (d[i + 1] - mean[1]) ** 2 + (d[i + 2] - mean[2]) ** 2) / 3;
      }
    return v / n;
  };
  const r = c.getBoundingClientRect();
  return { w: c.width, h: c.height, left: r.left, top: r.top, cssW: r.width, cssH: r.height,
           topVar: stripVar(4, 36), bottomVar: stripVar(364, 396), fullVar: stripVar(0, cc.height) };
})()`;

const results = { checks: [] };
const check = (name, ok, detail) => { results.checks.push({ name, ok, detail }); console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}  (${detail})`); };

try {
  await sleep(1200); // let page settle
  const canvasInfo = await evalJs(ANALYZE);
  if (!canvasInfo) throw new Error('no <canvas> found in page');
  check('canvas exists, 400x400 attribute size', canvasInfo.w === 400 && canvasInfo.h === 400, `${canvasInfo.w}x${canvasInfo.h}`);
  await shot('1-initial');

  const baselineTop = canvasInfo.topVar;
  const baselineBottom = canvasInfo.bottomVar;
  console.log(`[baseline] topVar=${baselineTop.toFixed(3)} bottomVar=${baselineBottom.toFixed(3)}`);

  // ---- hold left mouse button near top of canvas, wiggle ----
  const cx = canvasInfo.left + canvasInfo.cssW / 2;
  const yPaint = canvasInfo.top + 24;
  const mouse = (type, x, y, extra = {}) =>
    send('Input.dispatchMouseEvent', { type, x, y, button: 'left', buttons: 1, clickCount: 1, ...extra });
  await mouse('mousePressed', cx, yPaint);
  for (let i = 0; i < 24; i++) {
    await mouse('mouseMoved', cx + Math.sin(i / 3) * 45, yPaint + (i % 4));
    await sleep(50);
  }
  const duringPaint = await evalJs(ANALYZE);
  await shot('2-while-holding');
  await mouse('mouseReleased', cx, yPaint, { buttons: 0 });
  check('left-button hold adds sand at cursor',
    duringPaint.topVar > baselineTop + 100 && duringPaint.topVar > baselineTop * 1.5,
    `topVar ${baselineTop.toFixed(3)} -> ${duringPaint.topVar.toFixed(3)}`);

  // ---- let it fall ----
  await sleep(4000);
  const settled = await evalJs(ANALYZE);
  await shot('3-settled');

  check('paint area drains after release (sand fell)',
    settled.topVar <= baselineTop + Math.max(2, baselineTop * 0.1),
    `topVar ${duringPaint.topVar.toFixed(3)} -> ${settled.topVar.toFixed(3)} (baseline ${baselineTop.toFixed(3)})`);
  check('sand piles at the bottom',
    settled.bottomVar >= baselineBottom + 100 && settled.bottomVar > settled.topVar + 100,
    `bottomVar ${baselineBottom.toFixed(3)} -> ${settled.bottomVar.toFixed(3)}`);
  check('no page errors', pageErrors.length === 0, pageErrors.join(' | ').slice(0, 200) || 'clean');
} catch (e) {
  check('verifier ran without harness error', false, e.message);
} finally {
  fs.writeFileSync(`${SHOTS}/results.json`, JSON.stringify({ pageErrors, ...results }, null, 2));
  try { await shot('4-final'); } catch {}
  chrome.kill('SIGKILL');
}

const failed = results.checks.filter((c) => !c.ok).length;
console.log(failed === 0 ? '\nALL CHECKS PASSED' : `\n${failed} CHECK(S) FAILED`);
process.exit(failed === 0 ? 0 : 1);
