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

## Config (env)
| Var | Default | Used by |
|---|---|---|
| `CWDOTCOM_WS_URL` | `wss://dev.cwetzel.com/ws/chat` | `portfolio_answer` |
| `CWDOTCOM_RETRIEVE_URL` | `https://dev.cwetzel.com/api/retrieve` | `portfolio_search` |
| `VERIFIER_URL` | **none — required** | `portfolio_verify` |

`portfolio_search` goes through the proxy's `/api/retrieve` seam rather than talking to the
embed/rerank services directly: those bind `127.0.0.1` on the T5810 and aren't reachable off-box.

The faithfulness judge is a LAN-only service, so its address is deployment-specific and is not
committed here — set `VERIFIER_URL` in the MCP server's env. Without it, `portfolio_verify` returns
an "unconfigured" error rather than a misleading clean verdict; `portfolio_answer` is unaffected.

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
