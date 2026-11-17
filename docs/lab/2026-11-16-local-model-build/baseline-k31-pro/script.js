const canvas = document.getElementById('playground');
const context = canvas.getContext('2d');

const CELL_SIZE = 4;
const WIDTH = canvas.width / CELL_SIZE;
const HEIGHT = canvas.height / CELL_SIZE;
const EMPTY = 0;
const SAND = 1;
const WALL = 2;

const cells = new Uint8Array(WIDTH * HEIGHT);
let pouring = false;
let mouseX = 0;
let mouseY = 0;
let lastTime = 0;

function index(x, y) {
  return y * WIDTH + x;
}

function createWalls() {
  for (let x = 0; x < WIDTH; x++) {
    cells[index(x, 0)] = WALL;
    cells[index(x, HEIGHT - 1)] = WALL;
  }

  for (let y = 0; y < HEIGHT; y++) {
    cells[index(0, y)] = WALL;
    cells[index(WIDTH - 1, y)] = WALL;
  }
}

function updateSand() {
  for (let y = HEIGHT - 2; y >= 1; y--) {
    const leftToRight = Math.random() < 0.5;

    for (let i = 1; i < WIDTH - 1; i++) {
      const x = leftToRight ? i : WIDTH - 1 - i;
      const current = index(x, y);

      if (cells[current] !== SAND) continue;

      const below = index(x, y + 1);
      if (cells[below] === EMPTY) {
        cells[below] = SAND;
        cells[current] = EMPTY;
        continue;
      }

      const direction = Math.random() < 0.5 ? -1 : 1;
      const firstSide = index(x + direction, y + 1);
      const secondSide = index(x - direction, y + 1);

      if (cells[firstSide] === EMPTY) {
        cells[firstSide] = SAND;
        cells[current] = EMPTY;
      } else if (cells[secondSide] === EMPTY) {
        cells[secondSide] = SAND;
        cells[current] = EMPTY;
      }
    }
  }
}

function addSand() {
  if (!pouring) return;

  const x = Math.floor(mouseX / CELL_SIZE);
  const y = Math.floor(mouseY / CELL_SIZE);

  for (let offsetY = -1; offsetY <= 1; offsetY++) {
    for (let offsetX = -1; offsetX <= 1; offsetX++) {
      const cellX = x + offsetX;
      const cellY = y + offsetY;

      if (
        cellX > 0 && cellX < WIDTH - 1 &&
        cellY > 0 && cellY < HEIGHT - 1 &&
        Math.random() < 0.65
      ) {
        cells[index(cellX, cellY)] = SAND;
      }
    }
  }
}

function draw() {
  context.clearRect(0, 0, canvas.width, canvas.height);

  for (let y = 0; y < HEIGHT; y++) {
    for (let x = 0; x < WIDTH; x++) {
      const cell = cells[index(x, y)];
      if (cell === EMPTY) continue;

      context.fillStyle = cell === WALL ? '#727782' : '#e6bd62';
      context.fillRect(x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE);
    }
  }
}

function animate(time) {
  if (time - lastTime >= 1000 / 60) {
    addSand();
    updateSand();
    draw();
    lastTime = time;
  }

  requestAnimationFrame(animate);
}

function updateMousePosition(event) {
  const bounds = canvas.getBoundingClientRect();
  mouseX = (event.clientX - bounds.left) * canvas.width / bounds.width;
  mouseY = (event.clientY - bounds.top) * canvas.height / bounds.height;
}

canvas.addEventListener('pointerdown', (event) => {
  if (event.button !== 0) return;
  pouring = true;
  updateMousePosition(event);
  canvas.setPointerCapture(event.pointerId);
  addSand();
});

canvas.addEventListener('pointermove', (event) => {
  updateMousePosition(event);
});

canvas.addEventListener('pointerup', (event) => {
  if (event.button === 0) pouring = false;
});

canvas.addEventListener('pointercancel', () => {
  pouring = false;
});

createWalls();
draw();
requestAnimationFrame(animate);
