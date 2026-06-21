# Plan: Faithfulness Verifier Layer (self-auditing RAG)

**Status:** Design / not yet built. Code deferred — this is the build plan only.
**Date:** 2026-06-20

## Context / why
cwdotcom's core promise is **grounded, no-hallucination** answers. Today nothing verifies
that *per production response*: the system prompt asks the model to stay grounded, and
`scripts/selftest.py` is a **batch regression gate** (fixed battery, run on deploy + hourly
canary). Neither can tell whether *the answer a visitor just received* invented a claim.

This adds a **live faithfulness layer**: for every answer, an out-of-band judge checks whether
each claim is supported by the chunks that were actually retrieved, logs a verdict, and flags
drift for review. It runs on the otherwise-idle **Ryzen 9 5950X / 64 GB / RTX 3060 Ti 8 GB box**
so it never touches the A4500 serving cluster (which is full — vLLM owns the VRAM).

It complements, not duplicates, the self-test: self-test = "does the system still ground on a
fixed battery?" (regression); verifier = "is every real answer faithful to its sources?" (live
drift). Together that's actual QA. Same primitive later answers "did an iChris-lite draft invent
a client fact?" — but it earns its keep on cwdotcom first.

## Design principles (non-negotiable)
1. **Out-of-band by construction.** The answer has already streamed to the user before judging
   starts. Verification is post-hoc — it can NEVER add latency to a response. Fail-open: if the
   verifier is slow/down/wrong, the chat is unaffected.
2. **Claim-level + interpretable.** Output names *which* claim was unsupported (actionable),
   not just a score. A `contradicted` claim is the loud signal.
3. **Closes a loop.** Flagged answers feed a review queue that drives concrete fixes (KB gap,
   retrieval miss, prompt tweak) — not just a dashboard.
4. **Reuse existing patterns.** Mirror `home/rerank-service/` (model behind a small FastAPI,
   reachable over the SSH tunnel); monitor it with the existing self-test/canary pattern.

## Architecture
```
cloud api-proxy ──(answer streams to user, UNCHANGED)──> browser
      │
      └─ after 'done': fire-and-forget POST {query, answer, chunks, timing}  (short timeout, try/except)
              ▼  via SSH tunnel forward → home LAN
   Ryzen box: verifier-service (:8007)
      ├─ judge model (4-bit ~7-8B) on the RTX 3060 Ti
      ├─ faithfulness check (claim decompose → per-claim adjudication)
      └─ verdict → SQLite store; exposes /verify /metrics /review /health
```
The proxy passes the **exact chunks that were in the prompt** (full `context_docs` content, not
the truncated frontend `sources`) — the answer was meant to be grounded in *those*.

## Components to build

### 1. `verifier-service` (new, on the Ryzen box)
Mirror `home/rerank-service/`. New dir `home/verifier-service/` with `verifier.py` + an init
script (the Ryzen box's init system TBD — see Open Questions).
- **Judge model:** Qwen2.5-7B-Instruct 4-bit (NOT 3B — reasoning capacity matters for claim
  support; BF16-precision is a red herring for short verdicts). Easiest path: local Ollama
  (`ollama run qwen2.5:7b-instruct-q4_K_M` → `localhost:11434`); the service wraps it. vLLM is
  an alternative but Ollama is lower-friction on a single 8 GB card.
- **`POST /verify`** — body `{query, answer, chunks:[{title,source,content}]}` →
  `{faithfulness: 0.0-1.0, claims:[{text, verdict, source}], flagged: bool, model, latency_s}`.
  `verdict ∈ {supported, unsupported, contradicted}`. `flagged = faithfulness < THRESHOLD or any contradicted`.
- **`GET /metrics`** — rolling faithfulness rate, counts, flagged count over a window.
- **`GET /review`** — recent flagged verdicts (for the loop).
- **`GET /health`** — `{status: ok}` (for the canary).
- **Store:** SQLite on the box (`~/verifier/verdicts.db`): one row per response
  `(ts, query, answer, faithfulness, flagged, claims_json, latency_s)`. Cheap to query for
  /metrics + /review. (JSONL is the simpler fallback if SQLite feels heavy.)

### 2. The judge method (the prompt contract)
Single structured call per response (fast enough async on the 3060 Ti):
1. **Decompose** the answer into atomic factual claims.
2. **Adjudicate** each claim against the provided chunks → supported / unsupported /
   contradicted, with the supporting chunk's source.
3. `faithfulness = supported / total`; `flagged` per rule above.
Force structured JSON output (the judge model's structured-output mode, or a strict prompt +
a tolerant parser — reuse the FOLLOWUPS-parser lesson: parse leniently, validate).
Lead axis = **faithfulness**. Optional second axis later = **answer-relevance** (did it address
the query). Don't over-scope v1.

### 3. Proxy hook (`cloud/api-proxy.py`)
- After the streaming loop completes (`done` is sent, ~line 265), the proxy already holds
  `user_query`, the assembled `full_response`, and `context_docs` (full chunk content). Add a
  **fire-and-forget** `asyncio.create_task(...)` that POSTs to `VERIFIER_URL` with a short
  timeout, wrapped in try/except — **must not block or affect the user**. The answer is already
  delivered.
- Add `VERIFIER_URL = "http://127.0.0.1:8007"` (alongside EMBED/RERANK_URL).
- Optional: stamp the proxy's response record with `request_id` so the verdict can be correlated
  with the existing per-response timing/sources telemetry.

### 4. Tunnel forward (`cloud/systemd/portfolio-ai-tunnel.service`)
- Add `-L 127.0.0.1:8007:<RYZEN_LAN_IP>:8007` to the existing `ExecStart`. The forward target is
  resolved on the home side, so the home SSH endpoint must be able to reach the Ryzen box on the
  LAN (confirm — see Open Questions). This makes the verifier reachable at the cloud's
  `localhost:8007`, same pattern as 8005/8006.
- Commit the updated unit; document the parameterized IP.

### 5. Provisioning + monitoring
- A `home/setup-verifier.sh` (mirror `home/setup-t5810-services.sh`) that installs
  `verifier-service` on the Ryzen box (copy code, install init script, pull the Ollama model,
  enable at boot). Note: **different box** than the T5810 — new `${VERIFIER_HOST}`.
- **Self-test coverage:** extend `scripts/selftest.py` / canary to (a) check `verifier/health`
  is up, and (b) an offline `--from-results`-style check that the verifier correctly **flags a
  known-hallucinated answer** and **passes a known-faithful one** (the negative/positive pattern
  we already use). The verifier watches the chat; the self-test watches the verifier.

## Surfaces (the loop + the flex)
- **`/review`** → a review queue of low-faithfulness answers. Each flag is a free finding:
  hallucination, retrieval miss, or KB gap → drives the next KB/retrieval fix.
- **Faithfulness rate over time** (`/metrics`) → one honest number. Optional: surface it on the
  frontend "About this system" panel ("answers are X% claim-faithful to retrieved sources,
  continuously measured") — the meta-system that *proves* the grounded-RAG pitch.
- **Stretch (not v1):** a subtle per-answer "✓ grounded" confidence chip in the UI fed by the
  verdict. Keep out-of-band by default; only consider inline-blocking at real stakes.

## Phasing
- **P1 — Verifier core:** `verifier-service` + judge model + `/verify` + SQLite store on the
  Ryzen box. Validate offline (feed it a faithful and a hallucinated `(answer, chunks)` pair →
  correct verdicts).
- **P2 — Wire it in:** proxy fire-and-forget hook + tunnel forward. Confirm verdicts land for
  live chat answers with **zero** user-facing latency change.
- **P3 — Loop + telemetry:** `/metrics` + `/review`; start triaging flags into KB/retrieval fixes.
- **P4 — Self-test coverage + (optional) About-panel faithfulness number.**

## Verification / no-regression
- **Latency invariant:** the existing self-test smoke latency profile must be unchanged after P2
  (the hook is post-`done`, fire-and-forget) — confirm the gate still passes with the same timings.
- **Fail-open:** kill `verifier-service` and confirm the chat is fully unaffected (answers still
  stream; only verdicts stop).
- **Judge accuracy:** the offline positive/negative check (P1) gates trust before P3 telemetry is
  believed; spot-check a sample of flagged answers by hand early.
- Commit/push each phase; deploy via the existing scripts; keep live state reproducible.

## Open questions (resolve at kickoff)
1. **Ryzen box: OS, init system, and LAN reachability** from the home SSH endpoint that
   terminates the tunnel (needed for the `-L 8007` forward). IP to pin.
2. **Judge model + runtime:** Qwen2.5-7B-Instruct 4-bit via Ollama (default) vs vLLM. Confirm it
   fits the 3060 Ti with headroom (~5.5–6 GB) alongside the OS.
3. **Threshold + flag policy:** starting `THRESHOLD` (e.g. 0.8) and whether any `contradicted`
   always flags. Tune from observed distribution (same discipline as the reranker-score lesson).
4. **Scope guard:** faithfulness only for v1, or add answer-relevance? Default: faithfulness only.
5. **Retention:** how long to keep verdict rows / answers in the store (privacy + size).

## Honest scope
Telemetry + review loop by default, **not** a gate (inline-blocking re-introduces latency + a
hot-path failure point — only worth it at real stakes). On a single-user demo it'll be quiet
most days; its worth is the continuous proof, catching rare drift, and being battle-tested
before it matters. It's one more service to keep alive — but the service+tunnel+canary pattern
already exists, so that's cheap.
