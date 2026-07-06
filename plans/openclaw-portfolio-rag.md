# Spec: OpenClaw ↔ cwdotcom — "portfolio-rag" integration

> Status: DESIGN (2026-07-06). Code-grounded against cwdotcom's retrieval surface and the
> `openclaw-setup` bootstrap repo. The OpenClaw-side registration is a labelled stub —
> "more lands as we survey the Mac Mini node" (OpenClaw's MCP API is npm-internal, verify on box).

## Context / goal
OpenClaw is an off-the-shelf **npm agent gateway** on `Chriss-Mac-mini` (`npm install -g openclaw`;
config in `openclaw-setup/config/openclaw.template.json`). It has **WhatsApp + session-memory +
a skills/MCP framework + vLLM(base+LoRA) routing**, but **no knowledge base / RAG** (`memorySearch:
false`, no vector/Qdrant/embeddings anywhere). So today it would *hallucinate* about Chris — exactly
the fabrications this session removed from cwdotcom. cwdotcom has the inverse: curated KB, tuned
retrieval, out-of-band verifier, grounding-hardened prompt — but only a web/WS front-end.

**Goal:** let someone WhatsApp the portfolio assistant and get the *same grounded answers* as the
web chat, on the same hardware, with **zero regression to cwdotcom's production posture**.
**Direction is one-way: OpenClaw depends on cwdotcom, never the reverse** (cwdotcom stays
self-contained; OpenClaw is a sandbox that "must earn a role").

## Design decision — MCP server owned by cwdotcom, enabled by openclaw-setup
- OpenClaw exposes an MCP path (`skills.mcporter`). MCP **decouples us from OpenClaw's internal
  skill SDK** (the npm internals we can't audit) — a stable, model-agnostic contract.
- The MCP server is a **thin, read-only facade** over cwdotcom's EXISTING retrieval + verifier.
  It lives in **cwdotcom** (versioned with the KB it exposes). `openclaw-setup` only *registers*
  it — that side is the stub that fills in on the node.
- Read-only, no actions → matches cwdotcom's posture; binds **loopback on the Mac Mini** (OpenClaw
  is the only caller).

## Tools the MCP server exposes
1. **`portfolio_answer(question) → {answer, sources[], flagged}`  — PRIMARY, safest.**
   Drives cwdotcom's *full hardened pipeline* via the existing public WS
   (`wss://dev.cwetzel.com/ws/chat`) reusing `scripts/run_diagnostic_battery.ask()`. Inherits
   EVERYTHING: grounding system prompt, `guardrails.is_prompt_extraction`, dense retrieval +
   rerank, out-of-band verifier (fires server-side), FOLLOWUPS. Buffers the token stream into one
   message for WhatsApp. **OpenClaw's own model is NOT trusted to ground — cwdotcom does.**
   - Transport: public WSS (on/off-LAN, TLS, no tunnel needed). Zero cwdotcom change.
   - Steering: the tool description tells the agent to call this for *any* question about Chris,
     his work, the homelab, projects, or this AI system — and relay `answer` + `sources` verbatim.
2. **`portfolio_search(question, k=5) → {chunks:[{title,source,content,score}]}`  — SECONDARY.**
   Raw grounded chunks, for when OpenClaw wants to combine KB facts with other tools/reasoning.
   - Impl: either (a) call cwdotcom LAN microservices directly — `expand_query` →
     `POST 10.0.1.125:8005/embed {text}` → Qdrant `POST 10.0.1.125:6333/collections/documents/points/search {vector,limit,with_payload}`
     → `POST 10.0.1.125:8006/rerank {query,documents,top_k}` — or (b) **[recommended]** call the new
     cwdotcom REST seam below so the flow isn't duplicated.
   - ⚠️ Grounding contract: if OpenClaw generates from these chunks itself, its prompt MUST say
     "answer ONLY from these chunks; if not covered, say you don't have it," or we reintroduce the
     hallucination we just fixed. Prefer `portfolio_answer` to avoid this entirely.
3. **`portfolio_verify(question, answer, chunks) → {faithfulness, flagged, claims}`  — OPTIONAL.**
   `POST :8007/verify` (via tunnel/LAN). Lets OpenClaw grade *any* answer (incl. its own) against
   the KB — a cheap "is this grounded?" self-check reusing the exact judge cwdotcom runs.

## One small enabling change in cwdotcom (optional but recommended)
Add **`POST /api/retrieve {query, k} → {chunks:[{title,source,content,score}]}`** to
`cloud/api-proxy.py` — ~15 lines wrapping the existing `search_knowledge_base()` (return its
`context_docs`). Today `/api/search` (`api-proxy.py:147`) needs a *pre-computed vector*; this gives
a clean **text-in / chunks-out** seam reusable by any caller. Reuse `is_prompt_extraction` on input;
metadata-only logging (red line #2). Deploy via `cloud/deploy.sh`; gate on `scripts/selftest.py`.
- Skippable: `portfolio_search` can hit the LAN microservices instead (works, duplicates ~30 lines).
- `portfolio_answer` needs **no** cwdotcom change regardless — it's the zero-risk starting point.

## The MCP server (new, cwdotcom-owned)
- `cwdotcom/integrations/mcp/portfolio_mcp.py` — Python stdio MCP server (mcp SDK or minimal
  JSON-RPC). Reuses `run_diagnostic_battery.ask` (answer), `/api/retrieve` or the microservices
  (search), `/verify` (verify). Pure facade; no new business logic.
- Env config (no secrets): `CWDOTCOM_WS_URL` (default `wss://dev.cwetzel.com/ws/chat`),
  `CWDOTCOM_RETRIEVE_URL` / LAN service hosts, `VERIFIER_URL`.
- Logs metadata only (mirror cwdotcom). Loopback-bound.

## OpenClaw side — RESOLVED + DEPLOYED on the node (2026-07-06, OpenClaw 2026.6.11)
The registration path is the **first-class `openclaw mcp` command** (writes `mcp.servers`), NOT the
mcporter skill. `openclaw mcp add <name> --command <cmd> --arg <a> --cwd <dir> --env K=V` probes the
server, then saves it. **Done on `Chriss-Mac-mini`:**
```
openclaw mcp add portfolio-rag \
  --command ~/ai/cwdotcom/integrations/mcp/.venv/bin/python \
  --arg    ~/ai/cwdotcom/integrations/mcp/portfolio_mcp.py \
  --cwd    ~/ai/cwdotcom/integrations/mcp \
  --env    CWDOTCOM_WS_URL=wss://dev.cwetzel.com/ws/chat
```
- Node prereqs verified: cwdotcom present at `~/ai/cwdotcom`; a `.venv` (py3.14) with
  `mcp`+`websockets`+`httpx`; `portfolio_answer` returns grounded answers on the node.
- `openclaw mcp probe portfolio-rag` → **3 tools exposed**; `openclaw mcp reload` applied.
- Access inherits existing posture: WhatsApp `allowFrom`/`commands.ownerAllowFrom` pin to
  `__OWNER_PHONE__`; `nodes.denyCommands` blocks device actions. Nothing new to harden.
- Reversible: `openclaw mcp unset portfolio-rag`.

### Two findings from the node that gate "done"
1. **Steering is REQUIRED.** An `openclaw agent --local` turn on a portfolio question called `exec`,
   NOT `portfolio_answer` — the base 14B won't route to the tool on the description alone. Need a
   steering snippet (agent/system guidance): *"For anything about Chris Wetzel's work, homelab,
   projects, or this AI system, call `portfolio_answer` and relay its `answer` + `sources`; do not
   answer from your own knowledge."* Also confirm the **gateway/WhatsApp** agent (not just `--local`)
   has the tool loaded after `mcp reload`.
2. **`portfolio_search` needs the `POST /api/retrieve` seam.** embed(8005)/rerank(8006) bind
   `127.0.0.1` on the T5810 (localhost-only) → NOT LAN-reachable from the Mac Mini (verified: embed
   `000`, while Qdrant 6333 and verifier 8007 are `200`). So the direct-LAN `search_tool` can't work
   from the node; it must call a public `POST /api/retrieve` on the VPS proxy (which reaches
   embed/rerank via the tunnel at 127.0.0.1). `portfolio_answer` + `portfolio_verify` are unaffected.

### `openclaw-setup` codification (fast follow)
Fold the `openclaw mcp add` (or `mcp set '<json>'`) step + a `.venv`/deps install into `bootstrap.sh`
so a fresh Mac reproduces it; keep the JSON entry in the template flow.

## Security / posture (non-negotiable)
- **Personal scope only.** Portfolio = public content. NEVER wire the firm's `psaios`/client data
  (handoff §1 sovereign boundary).
- Read-only tools; device skills stay off (notes/sms/camera already in OpenClaw's `denyCommands`).
- **Queries-not-logged:** MCP server logs metadata only. NOTE OpenClaw's `command-logger` hook logs
  interactions on *its* side — fine for personal portfolio content, but never on a work channel.
- MCP server loopback-bound; OpenClaw is the sole caller. No new inbound exposure on cwdotcom
  (`portfolio_answer` uses the existing public WSS; `/api/retrieve`, if added, sits behind Apache
  like `/api/search` — same single-tenant trust-the-network model).

## Verification / acceptance
1. **Parity:** `portfolio_answer("what has Chris built?")` returns the *same* grounded answer +
   sources as the web UI; `portfolio_search("gpu home lab")` returns the homelab chunks.
2. **No fabrication:** run several audited chips through `portfolio_answer`; confirm they match
   cwdotcom live; optionally `portfolio_verify` the result → not flagged.
3. **End-to-end (node):** WhatsApp "what's Chris's home lab?" → grounded answer + sources on the
   phone; a non-portfolio question ("what's the weather") → OpenClaw handles normally (no tool call).
4. **Regression:** cwdotcom unchanged (or only additive `/api/retrieve`); `selftest.py` smoke green.

## Build order
1. *(cwdotcom, optional)* add `POST /api/retrieve`; deploy; selftest.
2. *(cwdotcom)* `portfolio_mcp.py` — `portfolio_answer` first (zero-dep), then `portfolio_search`
   + `portfolio_verify`. Test locally against the live endpoints.
3. *(openclaw-setup, on the node)* register + enable the MCP skill; add the steering snippet;
   wire `bootstrap.sh`.
4. WhatsApp end-to-end + grounding-parity check.

**Effort:** `portfolio_answer` MCP ≈ small (wrap `ask()`); `/api/retrieve` ≈ tiny; the OpenClaw
registration is the one unknown (depends on OpenClaw's MCP API — resolve on the node survey).
