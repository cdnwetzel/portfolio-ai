# Plan: Markdown Rendering for Chat UI

## Goal
Render model responses as formatted markdown instead of raw text. The model already outputs proper markdown (code blocks, headers, bold, lists) — the frontend just needs to parse and display it.

## Current State
`ChatWindow.jsx` line 23 renders all message content as raw text:
```jsx
<p className="whitespace-pre-wrap">{msg.content}</p>
```

## Steps

### 1. Install dependencies
```bash
cd frontend
npm install react-markdown react-syntax-highlighter
```

### 2. Update `ChatWindow.jsx`
- Import `ReactMarkdown` and a `SyntaxHighlighter` theme
- Replace the `<p>` raw text render with `<ReactMarkdown>` for assistant messages
- Wire in a custom `code` renderer that uses `SyntaxHighlighter` for fenced code blocks
- Keep user messages as plain text (they don't send markdown)

### 3. Style code blocks
- Choose a theme from `react-syntax-highlighter` (e.g. `oneDark`, `atomDark`)
- Add CSS for the code block wrapper: background, padding, border-radius, overflow-x scroll
- Ensure inline code (`\`backtick\``) renders differently from fenced blocks

### 4. Build and deploy
```bash
npm run build
rsync -avz --delete frontend/dist/ root@cwetzel.com:/var/www/dev.cwetzel.com/
```

## Files to Change
- `frontend/src/components/ChatWindow.jsx` — primary change
- `frontend/package.json` / `frontend/package-lock.json` — dependency additions

## Notes
- `react-markdown` handles partial/streaming markdown gracefully — safe for token-by-token streaming
- Scope to assistant messages only; user bubbles stay as plain text
- No changes needed to `useChat.js`, `api-proxy.py`, or deployment config
