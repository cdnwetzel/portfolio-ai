# Plan: Faithfulness Verifier Layer (self-auditing RAG)

**Status:** Design / not yet built. Code deferred — this is the build spec only.
**Date:** 2026-06-20
**Target host:** the idle Ryzen 9 5950X / 64 GB / RTX 3060 Ti 8 GB box (NOT the T5810 — its
A4500s are already full serving vLLM).

---

## 1. What it is
A **live, out-of-band faithfulness verifier** for the cwdotcom portfolio chat. For every answer
the chat produces, a small judge model scores whether each *claim in the answer* is supported by
the *KB chunks that were actually retrieved* for that answer. It logs a verdict, flags drift, and
exposes a rolling faithfulness metric and a review queue.

It turns cwdotcom's core promise — *grounded, no hallucination* — from "we hope" into a measured,
continuously-monitored signal, and it does so on otherwise-idle hardware without touching the
serving cluster.

One sentence: **the chat answers; the spare box quietly grades every answer against its own
sources, flags the ones that drift, and feeds those back as the to-do list that keeps the KB and
retrieval honest.**

## 2. What it is NOT (scope guards)
- **Not a gate / blocker** (by default). It does not sit in the response path and does not hold,
  rewrite, or veto answers. The user gets the answer; the verdict happens after.
- **Not a correctness oracle.** It judges *faithfulness to the retrieved chunks*, not truth about
  the world. "Faithful" means "the sources say this," not "this is objectively correct."
- **Not a retriever / re-ranker.** It does not change what gets retrieved or how it's ranked.
  (It can *reveal* retrieval failures, but fixing them is a separate action.)
- **Not a safety / guardrail filter.** Toxicity, jailbreak, PII-leak, prompt-dump are covered by
  the system prompt + `scripts/selftest.py` adversarial checks — out of scope here.
- **Not a replacement for the self-test.** The self-test is a *batch regression gate*; this is a
  *live per-response drift monitor*. They complement; neither subsumes the other.
- **Not a fine-tune / training task.** No LoRA, no model training. Off-the-shelf judge model.
- **Not a user-facing feature** (by default). Output is telemetry + a review queue. A UI
  confidence chip is an explicit *stretch*, not v1.

## 3. What it does (behavior)
For each completed chat response it receives `(query, answer, chunks)` and:
1. **Skips refusals.** If the answer is the grounded-fallback ("I don't have that documented…")
   or a deflection, there are no factual claims to audit → record `verdict=refusal`, no score.
2. **Strips non-claims.** Removes the `FOLLOWUPS:[…]` block and conversational framing before
   judging (reuse the FOLLOWUPS-strip logic already in the frontend/selftest).
3. **Decomposes** the answer into atomic factual claims.
4. **Adjudicates** each claim against the provided chunks → one of:
   - `supported` — directly stated or clearly entailed by a chunk
   - `contradicted` — a chunk states the opposite (the loud signal)
   - `unsupported` — not found in any chunk (even if plausibly true)
5. **Scores:** `faithfulness = supported / total_claims`.
6. **Flags:** `flagged = faithfulness < THRESHOLD OR any contradicted`.
7. **Stores** the verdict; updates `/metrics`; if flagged, surfaces it in `/review`.

## 4. Limits (be honest about these)
- **The judge is itself an LLM** → it can be wrong (meta-hallucination, missed entailment,
  over-strict on paraphrase). Treat scores as a *signal*, not ground truth; spot-check early and
  keep the model small-but-capable (7–8B), not tiny (3B is underpowered for entailment).
- **Faithful ≠ correct.** It cannot catch an answer that faithfully repeats a *wrong fact in the
  KB*. KB accuracy is a separate concern (the self-test + human review).
- **It does not directly detect retrieval misses.** If the right chunk was never retrieved, the
  answer may score "unsupported" — but the root cause is retrieval, not generation. The verdict
  flags the symptom; triage decides the cause.
- **Claim decomposition is imperfect** — compound/hedged sentences split unevenly; scores are
  approximate. Use trends + flags, not 3-decimal precision.
- **Throughput-bounded.** One 8 GB GPU judges ~1 response at a time; under concurrent load,
  verify requests queue. Mitigation: a bounded queue + **sampling valve** (verify 100% at low
  volume, sample under load). Fine for single-user; matters only at scale.
- **Post-hoc, not preventive.** A hallucinated answer still reaches the user *once*; the verifier
  catches it for the next iteration, it doesn't stop it live (that's the inline-gate tradeoff,
  deliberately not the default).
- **Single-box dependency** for the verifier — but **fail-open**: if it's down, the chat is
  unaffected; only verdicts stop.
- **Real cost is modest but nonzero:** GPU time + one more service to keep alive.

## 5. How it fits (architecture)
```
                          cloud VPS (cwetzel.com)
  browser ⇄ wss ⇄ api-proxy ──embed→Qdrant→rerank→vLLM(14B)──> answer  (UNCHANGED path)
                      │
                      └─ after 'done' (answer already delivered):
                         fire-and-forget POST {request_id, query, answer, chunks, timing}
                                 │  short timeout, try/except, asyncio.create_task — never blocks
                                 ▼  SSH tunnel: -L 127.0.0.1:8007:<RYZEN_LAN_IP>:8007
                       ┌──────────────────────────────────────────────┐
                       │  Ryzen box (home LAN): verifier-service :8007 │
                       │   ├─ judge model (7-8B 4-bit) on RTX 3060 Ti  │
                       │   ├─ /verify  → claim-level faithfulness       │
                       │   ├─ SQLite verdict store                      │
                       │   └─ /metrics  /review  /health                │
                       └──────────────────────────────────────────────┘
```
**Why it fits cleanly:**
- The proxy *already* holds `(user_query, full_response, context_docs[with full content])` at the
  moment `done` is sent — no new retrieval, no extra round trip in the user path.
- It mirrors the existing **service-on-a-box** pattern (`home/embed-service/`,
  `home/rerank-service/`) and the **tunnel-forward** pattern (ports 8004/8005/8006/6333).
- It's monitored by the existing **self-test / canary** pattern.
- It reads the **same `sources`/`timing` telemetry** we already added per response; the verdict
  is a new field alongside them (correlated by `request_id`).
- The serving cluster (A4500s) is never asked to self-critique — judging lives on separate GPU.

## 6. How to build it (the verifier-service)
New dir `home/verifier-service/` mirroring `home/rerank-service/`.

**6.1 Judge model + runtime.** Qwen2.5-7B-Instruct, 4-bit (~5.5–6 GB on the 3060 Ti, leaves
headroom for OS). Easiest: local **Ollama** (`ollama pull qwen2.5:7b-instruct-q4_K_M`,
served at `localhost:11434`); the service calls it. (vLLM is an alternative but Ollama is
lower-friction on a single 8 GB card.) Model name is a config var so it can be swapped.

**6.2 Service (`verifier.py`, FastAPI).** Endpoints:
- `POST /verify` — body `{request_id?, query, answer, chunks:[{title,source,content}]}` →
  `{verdict_type: "judged"|"refusal", faithfulness: float|null, claims:[{text,verdict,source}],
    flagged: bool, judge_model: str, latency_s: float}`.
- `GET /metrics?window=24h` → `{count, refusals, mean_faithfulness, flagged_count, flagged_rate}`.
- `GET /review?limit=20` → recent flagged verdicts (full claim detail).
- `GET /health` → `{status:"ok"}`.

**6.3 Judge prompt contract** (single structured call per response):
```
System: You are a strict faithfulness auditor for a retrieval-augmented chat. Judge ONLY whether
each factual claim in the ANSWER is supported by the numbered SOURCE CHUNKS. Use NO outside
knowledge. supported = stated or clearly entailed by a chunk; contradicted = a chunk states the
opposite; unsupported = not found in any chunk (even if plausibly true).
User: QUERY: {q}\n\nANSWER: {a}\n\nSOURCES:\n[1] {chunk1}\n[2] {chunk2}...\n
Output ONLY JSON: {"claims":[{"text":"...","verdict":"supported|unsupported|contradicted","source":<n|null>}]}
```
Parse leniently, validate strictly (reuse the FOLLOWUPS-parser lesson). Service computes
`faithfulness` and `flagged` from the claims; the model just adjudicates.

**6.4 Store.** SQLite at `~/verifier/verdicts.db`:
```
verdicts(id PK, ts TEXT, request_id TEXT, query TEXT, answer TEXT,
         verdict_type TEXT, n_claims INT, n_supported INT, n_unsupported INT,
         n_contradicted INT, faithfulness REAL, flagged INT,
         claims_json TEXT, judge_model TEXT, latency_s REAL)
```
(JSONL is the acceptable simpler fallback.)

**6.5 Throughput valve.** Bounded in-flight queue; if full, drop with a logged counter (or apply
a `SAMPLE_RATE` < 1.0). At single-user volume this never triggers; it's the safety for scale.

**6.6 Init + provisioning.** An OpenRC/systemd unit (per the Ryzen box's init — see Open
Questions) mirroring `rerank-service.openrc`, plus `home/setup-verifier.sh` (mirror
`home/setup-t5810-services.sh`) that: copies code, installs the unit, pulls the Ollama model,
enables at boot. Note `${VERIFIER_HOST}` is a **new box**, not the T5810.

## 7. How to integrate it
**7.1 Proxy hook (`cloud/api-proxy.py`).** After the streaming loop sends `done` (~line 265),
the proxy already has `user_query`, accumulated `full_response`, and `context_docs` (full chunk
content). Add:
- `VERIFIER_URL = "http://127.0.0.1:8007"` next to EMBED/RERANK_URL.
- A fire-and-forget task: `asyncio.create_task(_fire_verify(request_id, user_query, full_response, context_docs))`
  where `_fire_verify` POSTs to `{VERIFIER_URL}/verify` with `timeout=5` inside a try/except that
  swallows everything. **It runs after the answer is delivered and must never block, raise into,
  or delay the WS handler.**
- Strip the `FOLLOWUPS` block from `full_response` before sending (reuse existing strip logic).
- Pass `context_docs` *full content* (not the truncated frontend `sources`).
- Optional: emit a `request_id` (uuid) per response so the verdict correlates with the existing
  per-response timing/sources telemetry and the frontend record.

**7.2 Tunnel forward (`cloud/systemd/portfolio-ai-tunnel.service`).** Add
`-L 127.0.0.1:8007:<RYZEN_LAN_IP>:8007` to `ExecStart`. The forward target is resolved on the
home side (the SSH endpoint that terminates the tunnel), so that host must reach the Ryzen box on
the LAN — confirm (Open Q1). Commit the updated unit + document the IP.

**7.3 Config / secrets.** No secrets. `VERIFIER_URL`, `THRESHOLD`, `SAMPLE_RATE`, judge model
name are env/config. Keep the proxy's behavior identical when `VERIFIER_URL` is unset/unreachable
(fail-open).

**7.4 Deploy.** Backend hook via `cloud/deploy.sh`; verifier via `home/setup-verifier.sh`;
tunnel via re-deploying the unit. All reproducible, same as today.

## 8. How to test it
**8.1 Judge accuracy (offline, gates trust before telemetry is believed).**
- A fixtures file of `(answer, chunks, expected)` cases run directly against `/verify`:
  - **Faithful** answer fully covered by chunks → high faithfulness, not flagged.
  - **Hallucinated** answer with a claim absent from chunks → `unsupported`, flagged.
  - **Contradicted** answer (says the opposite of a chunk) → `contradicted`, flagged.
  - **Refusal** ("I don't have that documented") → `verdict_type=refusal`, no score.
  - **Paraphrase** (same fact, different words) → still `supported` (guards over-strictness).
- Pass criteria: correct verdict_type + flag on each. This is the verifier's own self-test,
  same positive/negative pattern as `scripts/selftest.py --from-results`.

**8.2 Fail-open (the most important integration test).** Stop `verifier-service`; run a normal
chat query → the answer must stream **unchanged and on time**; only the verdict is absent. Then
make `VERIFIER_URL` unreachable → same result. The chat must be provably independent of the
verifier.

**8.3 Latency invariant (no-regression).** Run `scripts/selftest.py` smoke before/after wiring
the hook → the latency profile must be unchanged (the hook is post-`done`, fire-and-forget).

**8.4 End-to-end.** Issue a known-grounded query and a query likely to drift; confirm verdicts
land in the store with sane claims, the grounded one scores high, and `/metrics` + `/review`
reflect them. Hand-check a sample of flagged answers to calibrate `THRESHOLD`.

**8.5 Canary coverage.** Extend `scripts/selftest.py` / `selftest-canary.sh` to check
`verifier/health`, so a dead verifier is noticed (it's monitoring the chat; the canary monitors
it).

## 9. Phasing
- **P1 — Core:** `verifier-service` + judge model + `/verify` + store. Pass §8.1 offline fixtures.
- **P2 — Wire-in:** proxy fire-and-forget hook + tunnel forward. Pass §8.2 fail-open + §8.3
  latency invariant. Confirm verdicts land for live answers with zero user-facing change.
- **P3 — Loop + telemetry:** `/metrics` + `/review`; begin triaging flags into KB/retrieval fixes.
- **P4 — Coverage + flex:** canary covers the verifier; optionally surface a faithfulness number
  on the "About this system" panel.

## 10. Open questions (resolve at kickoff)
1. **Ryzen box: OS, init system, and LAN reachability** from the tunnel's home-side SSH endpoint
   (needed for `-L 8007`). Pin its LAN IP.
2. **Judge model/runtime:** Qwen2.5-7B-Instruct 4-bit via Ollama (default) vs vLLM; confirm fit
   (~5.5–6 GB) with OS headroom on the 3060 Ti.
3. **Threshold + flag policy:** starting `THRESHOLD` (e.g. 0.8); does any `contradicted` always
   flag? Tune from the observed distribution (same discipline as the reranker-score calibration).
4. **Scope guard:** faithfulness only for v1, or also answer-relevance ("did it address the
   query")? Default: faithfulness only.
5. **Retention/privacy:** how long to keep `query`/`answer` rows; the chat is single-tenant public
   portfolio content, so low sensitivity, but set a retention window + size cap on the store.

## 11. Reuse map (what already exists vs. net-new)
- **Reuse as-is:** the RAG pipeline + per-response `sources`/`timing` telemetry (`api-proxy.py`),
  the service pattern (`home/rerank-service/`), the tunnel (`cloud/systemd/portfolio-ai-tunnel.service`),
  the deploy + canary scaffolding (`cloud/deploy.sh`, `scripts/selftest*.{py,sh}`), the
  lenient-parse/strict-validate and FOLLOWUPS-strip lessons.
- **Net-new:** `home/verifier-service/` (code + unit), the judge model on the Ryzen box, the
  SQLite verdict store, the proxy fire-and-forget hook + `VERIFIER_URL`, the `-L 8007` tunnel
  forward, `home/setup-verifier.sh`, and the verifier fixtures/canary check.

## 12. Eval refinements (from iChris + firm review, 2026-06-27)
A review of `../iChris/` (`ichris/eval/*`) and the firm's monday roadmap (`bl89`, `bl278`)
sharpened the judging design. These apply to *both* this live verifier and the offline graded
eval in `plans/rag-improvements.md` §1.1 — same judge engine, two entry points.
- **Independent judge (echo bias).** The judge MUST be a different model than the one that wrote
  the answer (the 14B). The spare-box 7-8B judge already satisfies this — keep it that way; never
  judge an answer with the model that produced it. (`bl89`: a single same-family judge "penalizes
  assertive answers" and graded a *more* faithful version *worse*.)
- **Multi-axis, graded 1–5, not boolean.** Beyond per-claim supported/unsupported, also emit a
  1–5 `grounding` (and optionally `citation_correctness`) so trends are visible, not just pass/fail.
  Stream verdicts to JSONL for distribution tracking (`ichris/eval/harness.py`, temp 0, strict JSON).
- **Human golden set as backstop.** Multi-LLM convergence is NOT sufficient for sign-off
  (`bl278`: only 1 of 4 LLMs caught a critical fact). Keep a ~30-question YAML golden set with a
  rubric (accuracy/completeness/usefulness/hallucination-free); use it to validate the judge itself.
- **Ship thresholds (when used as a gate offline).** e.g. promote only at mean ≥3.5, no axis <2.5,
  over ≥15 evals — concrete numbers to adopt rather than invent.
- **Prompt-version hash on every verdict.** Stamp `sha1(system_prompt)[:8]` so a faithfulness dip
  is attributable to a prompt change vs a pipeline change (`ichris/llm/prompts.py:99`).
- **Judge-accuracy validation (§8.1) is now non-optional**, precisely because the firm's own
  lesson is "the eval can measure the wrong thing." The positive/negative/paraphrase/contradiction
  fixtures gate trust in the judge before its scores are believed.
