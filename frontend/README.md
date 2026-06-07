# Portfolio AI Frontend

React + Vite + Tailwind CSS frontend for the Portfolio AI chatbot.

## Structure

```
src/
├── main.jsx           # React entry point
├── App.jsx            # Main router (Landing/Chat)
├── index.css          # Tailwind setup
├── pages/
│   ├── Landing.jsx    # Intro + "Start Chat" button
│   └── Chat.jsx       # Chat interface
├── components/
│   ├── ChatWindow.jsx # Message display
│   └── MessageInput.jsx # Message input + send
└── hooks/
    └── useChat.js     # WebSocket management
```

## Development

```bash
npm install
npm run dev
```

Opens http://localhost:5173 (proxies /api and /ws to localhost:8000)

## Build & Deploy

```bash
npm run build
scp -r dist/* root@cwetzel.com:/var/www/dev.cwetzel.com/
```

## Features

- **Landing page**: Intro + Start button
- **Chat interface**: Real-time WebSocket streaming
- **Responsive**: Tailwind CSS, mobile-friendly
- **Error handling**: Graceful fallback for API errors
- **Auto-scroll**: Scrolls to latest message

## API Integration

Routes to FastAPI proxy (cwetzel.com:8000):

- `POST /api/chat` - One-shot chat (not used in MVP)
- `WS /ws/chat` - WebSocket streaming (primary)
- `POST /api/search` - Knowledge base search (future)

## Performance

- Vite: Fast HMR, optimized build
- Tailwind: Purged CSS (~30KB)
- Message streaming: Real-time via WebSocket
