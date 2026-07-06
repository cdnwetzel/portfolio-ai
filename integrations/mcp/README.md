# portfolio-rag MCP server

Exposes cwdotcom's **grounded** retrieval to an MCP client (OpenClaw's `mcporter` skill) so a
WhatsApp/agent front-end can answer questions about Chris's work without hallucinating. Read-only,
one-way (OpenClaw depends on cwdotcom, never the reverse). Full design: `plans/openclaw-portfolio-rag.md`.

## Tools
- **`portfolio_answer(question)`** — the safe default. Drives cwdotcom's full hardened pipeline via
  the public WS (grounding prompt + guardrail + retrieval + verifier + FOLLOWUPS). Zero proxy change.
- **`portfolio_search(question, k=5)`** — raw grounded chunks (expand → embed → Qdrant → rerank), LAN.
- **`portfolio_verify(question, answer, chunks)`** — faithfulness check via the asrock judge.

## Run
```bash
pip install -r requirements.txt
python3 portfolio_mcp.py           # stdio MCP server (what mcporter connects to)
```

## Config (env, all optional)
`CWDOTCOM_WS_URL` (default `wss://dev.cwetzel.com/ws/chat`), `EMBED_URL`/`QDRANT_URL`/`RERANK_URL`
(default the T5810 LAN `10.0.1.125:8005/6333/8006`), `VERIFIER_URL` (default asrock `10.0.1.115:8007`),
`QDRANT_COLLECTION` (default `documents`).

## Test the logic without the MCP SDK
```bash
python3 -c "import asyncio, portfolio_mcp as m; print(asyncio.run(m.answer_tool('What has Chris built?')))"
```
`portfolio_answer` works from anywhere (public WS). `portfolio_search`/`portfolio_verify` need LAN
reach to the T5810/asrock services.

## OpenClaw side (Mac Mini)
Enable + configure the `mcporter` skill (`skills.entries.mcporter`) to launch this server over stdio,
then WhatsApp works. See `plans/openclaw-portfolio-rag.md` — the exact mcporter server-config schema
is the one node-survey unknown.
