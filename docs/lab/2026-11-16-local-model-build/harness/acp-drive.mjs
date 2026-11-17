// Drive `kimi acp` (local model session) to build the sand simulator.
// JSON-RPC over stdio, newline-delimited. Auto-approves tool permissions.
import { spawn } from 'node:child_process';
import fs from 'node:fs';

const MODEL_ALIAS = process.argv[2] || 'local/qwen3.8-27b';
const WORKDIR = process.argv[3] || '/home/chris/ai/super-agent/sand-simulator';
const TASK = `Your task is to create a real-life sand simulator using HTML, CSS, and JS.
- There should be a wall around the playground (window).
- The playground should be 400x400 pixels and sand particles 4x4 pixels.
- The sand particles should roll down like in real life and pile up at the bottom.
- Add new sand when the left mouse button is held down.

Work in the current directory. Create index.html, style.css, and script.js. When done, reply with a short summary of what you built.`;

fs.mkdirSync(WORKDIR, { recursive: true });
fs.writeFileSync('/tmp/acp-stderr.log', '');

const child = spawn('kimi', ['acp'], { cwd: WORKDIR, stdio: ['pipe', 'pipe', 'pipe'] });
child.stderr.on('data', (d) => fs.appendFileSync('/tmp/acp-stderr.log', d));

let buf = '';
let nextId = 0;
const pending = new Map();
const send = (method, params) => {
  const id = ++nextId;
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
  return new Promise((res, rej) => pending.set(id, { res, rej, method }));
};

const reply = (id, result) => child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, result }) + '\n');

function handle(m) {
  if (m.id !== undefined && m.method) {
    // Reverse-RPC request from the agent
    if (m.method === 'session/request_permission') {
      const opts = m.params.options || [];
      const pick =
        opts.find((o) => /always/i.test(o.name || '')) ||
        opts.find((o) => /allow|approve|yes/i.test(o.name || '')) ||
        opts[0];
      console.log(`[PERM] ${m.params.toolCall?.title || m.params.toolCall?.kind || '?'} -> ${pick?.name || 'default'}`);
      reply(m.id, { optionId: pick?.optionId ?? pick?.id ?? 'allow' });
    } else {
      console.log(`[REVERSE-RPC] ${m.method} (empty result)`);
      reply(m.id, {});
    }
    return;
  }
  if (m.id !== undefined && pending.has(m.id)) {
    const p = pending.get(m.id);
    pending.delete(m.id);
    m.error ? p.rej(new Error(`${p.method}: ${JSON.stringify(m.error)}`)) : p.res(m.result);
    return;
  }
  if (m.method === 'session/update') {
    const u = m.params?.update || {};
    if (u.type === 'tool_call') console.log(`[TOOL] ${u.title || u.kind}`);
    else if (u.type === 'agent_message_chunk') process.stdout.write(u.content?.text ?? (typeof u.content === 'string' ? u.content : ''));
    return;
  }
  if (m.method) console.log(`[NOTIF] ${m.method}`);
}

child.stdout.on('data', (d) => {
  buf += d;
  let i;
  while ((i = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, i);
    buf = buf.slice(i + 1);
    if (line.trim()) {
      try { handle(JSON.parse(line)); } catch (e) { console.log('[PARSE-ERR]', line.slice(0, 200)); }
    }
  }
});

const watchdog = setTimeout(() => {
  console.error('\n[TIMEOUT] 20 minutes elapsed, killing agent');
  child.kill('SIGKILL');
  process.exit(2);
}, 20 * 60 * 1000);

try {
  const init = await send('initialize', {
    protocolVersion: 1,
    clientCapabilities: {},
    clientInfo: { name: 'local-probe', version: '0.1.0' },
  });
  console.log(`\n[INIT] ${init.agentInfo?.name} ${init.agentInfo?.version}`);

  const sn = await send('session/new', { cwd: WORKDIR, mcpServers: [] });
  console.log(`[SESSION] ${sn.sessionId}`);
  console.log(`[CONFIG-OPTIONS] ${JSON.stringify(sn.configOptions || [])}`);
  console.log(`[MODES] ${JSON.stringify(sn.modes || [])}`);

  try {
    await send('session/set_model', { sessionId: sn.sessionId, modelId: MODEL_ALIAS });
    console.log(`[MODEL] pinned explicitly: ${MODEL_ALIAS}`);
  } catch {
    console.log(`[MODEL] set_model unavailable; config default applies (${MODEL_ALIAS})`);
  }

  const t0 = Date.now();
  await send('session/prompt', { sessionId: sn.sessionId, prompt: [{ type: 'text', text: TASK }] });
  console.log(`\n[DONE] turn finished in ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  console.log(`[FILES] ${JSON.stringify(fs.readdirSync(WORKDIR))}`);
} catch (e) {
  console.error('\n[FAILED]', e.message);
  console.error('[STDERR tail]', fs.readFileSync('/tmp/acp-stderr.log', 'utf8').slice(-2000));
  process.exitCode = 1;
} finally {
  clearTimeout(watchdog);
  child.kill('SIGKILL');
}
