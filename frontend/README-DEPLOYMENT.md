# Frontend Deployment Guide

## Current Status

✅ **React Vite build deployed to dev.cwetzel.com** (2026-06-10)

The standalone HTML file (`index-mvp-fixed.html`) has been replaced with a modular React Vite build for maintainability.

## Architecture

```
dev.cwetzel.com
├─ Nginx (reverse proxy, SSL)
├─ Static React build
│  ├─ index.html (436 bytes, template)
│  └─ assets/
│     ├─ index-*.js (146KB, minified React app)
│     └─ index-*.css (9.24KB, Tailwind styles)
└─ Routes API requests to FastAPI proxy
   └─ proxy forwards to T5810 vLLM (port 8004, SSH tunnel)
```

## Building

### Prerequisites
- Node.js 24+
- npm 11+
- External drive `/Volumes/XcodeNVMe` mounted (for npm cache)

### Build Steps

```bash
cd frontend

# Install dependencies
npm install

# Build for production
npm run build

# Output: dist/ folder
#   - dist/index.html
#   - dist/assets/index-*.js
#   - dist/assets/index-*.css
```

### Local Testing

```bash
# Start dev server at http://localhost:5173
npm run dev

# The app will proxy /api and /ws to localhost:8000 (see vite.config.js)
```

## Deployment

### Deploy to dev.cwetzel.com

```bash
# From project root
rsync -avz --delete frontend/dist/ root@cwetzel.com:/var/www/dev.cwetzel.com/
```

This:
- Uploads all files from `dist/` 
- Replaces old files on the server
- Cleans up deleted files (--delete)

### After Deployment

Verify at: https://dev.cwetzel.com/

Check:
- ✓ Page loads
- ✓ No 404s in console
- ✓ Chat UI visible
- ✓ WebSocket connects on first message
- ✓ Model name is `qwen2.5-coder-14b-pscode`

## Model Configuration

The model is hardcoded in `src/hooks/useChat.js`:

```javascript
model: 'qwen2.5-coder-14b-pscode'
```

**This must match what's running on T5810 vLLM.** Check `/opt/vllm/startup.log` or `systemctl status vllm-qwen` on T5810 to verify.

## Source Files

- **`src/App.jsx`** — Main component (routing between landing/chat)
- **`src/hooks/useChat.js`** — WebSocket chat logic, streaming, model config
- **`src/components/ChatWindow.jsx`** — Message display, markdown rendering
- **`src/components/MessageInput.jsx`** — Input field with send button
- **`src/pages/Landing.jsx`** — Landing page
- **`src/pages/Chat.jsx`** — Chat interface

## Configuration Files

- **`vite.config.js`** — Build config, dev proxy
- **`tailwind.config.js`** — Tailwind CSS setup
- **`package.json`** — Dependencies (React 18, Vite, Tailwind)

## Known Issues

### External Drive Required

npm cache is stored on `/Volumes/XcodeNVMe`. This must be mounted before running `npm install`:

```bash
# If npm install fails with EACCES /Volumes/XcodeNVMe
# 1. Mount the drive
# 2. Configure npm cache:
npm config set cache ~/.npm
# 3. Try again
npm install
```

### Asset Paths

The build uses relative paths (`/assets/...`). If deploying to a subdirectory (not root), update `vite.config.js`:

```javascript
export default defineConfig({
  base: '/your-subdirectory/',
  // ...
})
```

## What's NOT Here Anymore

- ❌ `index-mvp-fixed.html` (standalone HTML file)
- ❌ `index-mvp.html` (old version)
- ❌ Manual HTML maintenance

These have been replaced by the React source of truth in `/src/`.

## Next Steps

### Automated Builds (TODO)

Set up GitHub Actions to:
1. Build on every push to `frontend/` directory
2. Run tests (if added)
3. Deploy to dev.cwetzel.com automatically

### Testing (TODO)

Add:
- Unit tests for useChat hook
- E2E tests for chat flow
- Visual regression tests

### Performance (TODO)

Monitor:
- JS bundle size (currently 146KB gzipped)
- CSS bundle size (currently 9.24KB)
- WebSocket message latency
- LLM response time (T5810 side)

## Related Documentation

- **[CLAUDE.md](../CLAUDE.md)** — Project overview and architecture
- **Memory: [actual-deployment-config](../.claude/projects/-Users-cwetzel-ai-cwdotcom/memory/actual_deployment_config.md)** — What's really running
- **Memory: [session-docs-alignment-2026-06-10](../.claude/projects/-Users-cwetzel-ai-cwdotcom/memory/session_docs_alignment.md)** — Session notes on alignment work
