// Falling-sand simulation on a 100x100 grid of 4x4 px grains.
const canvas = document.getElementById('playground');
const ctx = canvas.getContext('2d');

const CANVAS_SIZE = 400;
const CELL = 4;
const GRID = CANVAS_SIZE / CELL; // 100 columns and rows

const STEPS_PER_FRAME = 2; // simulation sub-steps per rendered frame
const POUR_SIZE = 8; // grains emitted per frame while the mouse is held

const EMPTY = 0;
const SAND = 1;

const grid = new Uint8Array(GRID * GRID); // 0 = empty, 1 = sand grain
const tint = new Uint8Array(GRID * GRID); // palette index per grain

// A palette of slightly varied sand tones so the pile looks natural.
const SAND_TONES = 24;
const palette = [];
for (let i = 0; i < SAND_TONES; i++) {
  const h = 38 + (Math.random() * 12 - 6);
  const s = 45 + Math.random() * 20;
  const l = 52 + Math.random() * 18;
  palette.push(hslToRgb(h, s, l));
}

// Offscreen buffer: one pixel per grain, scaled up 4x for display.
const buffer = document.createElement('canvas');
buffer.width = GRID;
buffer.height = GRID;
const bctx = buffer.getContext('2d');
const img = bctx.createImageData(GRID, GRID);

function hslToRgb(h, s, l) {
  s /= 100;
  l /= 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [Math.round(255 * f(0)), Math.round(255 * f(8)), Math.round(255 * f(4))];
}

const idx = (x, y) => y * GRID + x;
const inBounds = (x, y) => x >= 0 && x < GRID && y >= 0 && y < GRID;

function spawn(x, y) {
  if (inBounds(x, y) && grid[idx(x, y)] === EMPTY) {
    grid[idx(x, y)] = SAND;
    tint[idx(x, y)] = (Math.random() * SAND_TONES) | 0;
  }
}

function move(from, to) {
  grid[to] = grid[from];
  tint[to] = tint[from];
  grid[from] = EMPTY;
}

function step() {
  // Bottom-up so a grain falls at most one cell per step; the scan
  // direction alternates per row to avoid a left/right bias.
  for (let y = GRID - 1; y >= 0; y--) {
    const leftToRight = (y + frame) % 2 === 0;
    for (let i = 0; i < GRID; i++) {
      const x = leftToRight ? i : GRID - 1 - i;
      const id = idx(x, y);
      if (grid[id] === EMPTY) continue;

      // Straight down if there is room.
      if (y + 1 < GRID && grid[idx(x, y + 1)] === EMPTY) {
        move(id, idx(x, y + 1));
        continue;
      }

      // Otherwise slide diagonally down onto the pile. Try both sides in a
      // random order, and require the side cell to be empty so grains don't
      // slip through each other's corners.
      const dxs = Math.random() < 0.5 ? [-1, 1] : [1, -1];
      for (const dx of dxs) {
        const nx = x + dx;
        if (
          y + 1 < GRID && nx >= 0 && nx < GRID &&
          grid[idx(nx, y + 1)] === EMPTY &&
          grid[idx(nx, y)] === EMPTY
        ) {
          move(id, idx(nx, y + 1));
          break;
        }
      }
    }
  }
}

function render() {
  const data = img.data;
  for (let i = 0; i < grid.length; i++) {
    const p = i * 4;
    if (grid[i] === EMPTY) {
      data[p] = 0;
      data[p + 1] = 0;
      data[p + 2] = 0;
      data[p + 3] = 0;
    } else {
      const [r, g, b] = palette[tint[i]];
      data[p] = r;
      data[p + 1] = g;
      data[p + 2] = b;
      data[p + 3] = 255;
    }
  }
  bctx.putImageData(img, 0, 0);
  ctx.clearRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);
  ctx.imageSmoothingEnabled = false;
  ctx.drawImage(buffer, 0, 0, CANVAS_SIZE, CANVAS_SIZE);
}

// --- Input: hold the left mouse button to pour sand ---
let pouring = false;
let mouseX = 0;
let mouseY = 0;

function gridPos(e) {
  const rect = canvas.getBoundingClientRect();
  return {
    x: Math.floor(((e.clientX - rect.left) / rect.width) * GRID),
    y: Math.floor(((e.clientY - rect.top) / rect.height) * GRID),
  };
}

canvas.addEventListener('mousedown', (e) => {
  if (e.button !== 0) return;
  e.preventDefault();
  const p = gridPos(e);
  mouseX = p.x;
  mouseY = p.y;
  pouring = true;
});

window.addEventListener('mouseup', (e) => {
  if (e.button === 0) pouring = false;
});

canvas.addEventListener('mousemove', (e) => {
  const p = gridPos(e);
  mouseX = p.x;
  mouseY = p.y;
});

canvas.addEventListener('mouseleave', () => {
  pouring = false;
});

function pour() {
  if (!pouring) return;
  for (let i = 0; i < POUR_SIZE; i++) {
    const dx = Math.floor(Math.random() * 5) - 2;
    const dy = Math.floor(Math.random() * 3) - 1;
    spawn(mouseX + dx, mouseY + dy);
  }
}

// --- Main loop ---
let frame = 0;

function tick() {
  pour();
  for (let s = 0; s < STEPS_PER_FRAME; s++) {
    frame++;
    step();
  }
  render();
  requestAnimationFrame(tick);
}

tick();
