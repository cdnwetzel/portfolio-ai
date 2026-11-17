# Demo surface — execution spec (M1 receipts · M2 status · M3 lab)

Date: 2026-11-16 · Status: PARKED, spec-complete (ready to implement on revival)
Origin: local-inference proof session; promoted from decision-plan on 2026-11-16 after
verifying protocol assumptions against `cloud/api-proxy.py` live code.

## Locked decisions (do not reopen without a new decision record)

- **No second generic chat endpoint.** The twin already demos model + serving; another
  chat dilutes the product and adds abuse surface. (Rejected 2026-11-16.)
- **No live tools for anonymous users.** Agentic capability appears only as curated,
  static receipts (M3). Tools + anonymous internet = free coding node, rejected
  regardless of rate limits.
- **All demo surfaces are read-only and fail-open.** A demo component failing must never
  affect chat — same invariant the verifier already honors (api-proxy.py:605-639).

## Current-state findings that shape M1 (verified against live code 2026-11-16)

The WSS protocol and proxy already carry most of what receipts need:

- `request_id` (UUID) is generated per request and sent in every `done` frame
  (api-proxy.py:733,742,767).
- `{"type":"sources","data":[...]}` already streams the retrieval results to the
  frontend (api-proxy.py:849). Sources are visible client-side today; they are just not
  rendered anywhere.
- A `{"type":"verdict",...}` push ALREADY exists — `_fire_verify` awaits the judge
  response and pushes metadata when `flagged` is true and the socket is still open
  (api-proxy.py:628-636). Verdict round-trip works; only non-flagged verdicts are
  dropped and nothing is persisted.
- Health endpoints verified 2026-11-16 from T5810: embedder `:8005/health` 200,
  Qdrant `:6333/healthz` 200, labrouter `:8004/health` 200, vLLM `:8007/health` 200.

**Consequence: M1 is smaller than the decision-plan feared.** No new lifecycle needed —
extend the existing one: persist every verdict, push all verdict states (not just
flagged), add timing to the `done` frame, render what already arrives.

---

## M1 — Per-answer receipts (implement first)

### M1.1 Proxy changes (`cloud/api-proxy.py`, deploys via deploy.sh)

1. **Persist verdicts.** In `_fire_verify`, after a 200 response, append one JSON line
   to a local append-only log (env `VERDICT_LOG`, default
   `/var/lib/api-proxy/verdicts.jsonl`; dir created by deploy script, `root:api-proxy
   0640` — the service runs as whatever user api-proxy.service specifies; match it).
   Write failures are swallowed and logged at debug — never affect chat.
   Record schema (one line per verdict):
   ```json
   {"ts":"2026-11-16T20:00:00Z","request_id":"...","flagged":false,
    "faithfulness":0.93,"n_contradicted":0,"n_claims":7,
    "latency_ms":6800,"model":"qwen3.8-27b","prompt_version":"..."}
   ```
   (include whatever fields `/verify` actually returns — the push path at :628-636 shows
   `flagged`, `faithfulness`, `n_contradicted` exist; capture the rest defensively with
   `.get()`).
2. **Push all verdict states, not just flagged.** Extend the existing push: after the
   answer's `done`, when the socket is open, send
   `{"type":"verdict","request_id":..., "state":"ok"|"flagged"|"unavailable",
     "faithfulness":..., "n_contradicted":...}`.
   Backward-compatible: add `state`, keep old fields. `unavailable` = verifier off/down/
   timeout/gate-skipped — the panel treats it as "not verified", NOT as an error
   (fail-open ethos; matches red-lines.md #2 metadata-only).
3. **Timing in the `done` frame.** Add `"timing":{"ttft_ms":...,"total_ms":...,
   "completion_tokens":...,"tok_s":...}`. TTFT = first chunk arrival minus request
   start; totals from the existing `usage` vLLM returns. Fields additive; old clients
   ignore them.
4. **Read endpoint (poll fallback):** `GET /api/verdicts/{request_id}` → latest record
   or 404. Reuse `rate_limit.py` (per-IP budget). GET-by-UUID only; **no list
   endpoint** in M1 (verdicts of the public portfolio chat are low-sensitivity, but no
   bulk enumeration without a reason). Serves clients whose socket closed before the
   push or that reconnect.
5. **Feature flags (all default-on for the new behavior, but kill-switchable):**
   `VERDICT_LOG` (unset = persistence off), `TRACE_PUSH=1` (unset = old flagged-only
   push). Rollback = flip env + restart; JSONL is deletable independently.

### M1.2 Frontend changes (`frontend/src/App.jsx` + one new component)

- `ReceiptPanel` component, collapsed by default, one per assistant message:
  - **Sources section**: renders the `sources` message already received (title, source
    doc, retrieval score; mark which survived reranking if the payload distinguishes —
    if not, M1 ships scores only).
  - **Verdict section**: state machine — `pending` (awaiting push/poll) → `ok`
    (faithfulness %, claims count) | `flagged` (amber; "claims contradicted: N") |
    `unavailable`/`off` (gray; "verification not run — judge disabled or unreachable").
  - **Timing line**: TTFT, total, tok/s from the `done` frame.
- Poll fallback: if no `verdict` push arrives within 3s of `done`, poll
  `/api/verdicts/{request_id}` at 3s, 8s, 20s, then settle to `unavailable`.
- Styling per existing Tailwind patterns; panel must be invisible to screen readers when
  collapsed appropriately (use `<details>` semantics or aria-expanded).

### M1.3 Ops

- deploy.sh: create `VERDICT_LOG` dir with correct ownership; ship a logrotate drop-in
  (weekly, keep 8, maxage 90) — volume is ~1 line/chat, rotation is hygiene only.
- Commit the missing systemd override files (`verifier.conf`, `verify-gate.conf` per
  service.d README) to `cloud/systemd/api-proxy.service.d/` — deployed-only config
  contradicts repo-as-source-of-truth. Confirm on the VPS whether the judge is
  currently enabled before M1.2's `pending` state is user-visible.

### M1.4 Acceptance criteria (all must hold)

1. Every completed answer (KB-grounded path) shows sources + timing in the panel.
2. Verdict resolves to ok/flagged within ~25s when the judge is enabled; panel shows
   `unavailable` when the judge is off/down — and **chat latency/behavior is identical
   in both cases** (invariant: verify with judge enabled vs disabled, diff the WSS
   timings).
3. `scripts/eval_graded.py` golden-set result is byte-identical to pre-M1 (receipts are
   observability, not behavior change).
4. `GET /api/verdicts/{id}` is rate-limited; 404 for unknown ids; no list endpoint.
5. Redaction: only metadata leaves the proxy (no query/answer content in verdict
   records or pushes) — red-lines.md #2 preserved; verify by inspecting one JSONL line
   and one push frame.
6. Verifier down drill: point VERIFIER_URL at a dead port → chat unaffected, panels
   show `unavailable`, no stack traces in journal.

### M1.5 Test plan

- Unit: verdict-record append (mock response), state mapping, rate limit on read
  endpoint. Existing pytest suite stays green.
- Integration (pre-deploy, on the VPS): scripted WSS chat → assert `done` carries
  `timing`; with judge enabled assert a `verdict` push arrives and one JSONL line
  lands; with judge disabled assert `unavailable` panel state.
- Post-deploy: same WSS script against production; check `/api/verdicts/{id}` curl.

---

## M2 — Live `/inside` status page

1. **Prerequisite — fix the drift** (from the gaps list): reconcile the kb port table
   (`ai_portfolio_system.md` lists :8007 as asrock verifier; live state is T5810
   vLLM :8007) and the README "A4500 NVLink pair" wording (no NVLink on A4500; PCIe
   Gen3 measured). A receipts product cannot ship inaccurate receipts.
2. **Server**: `GET /api/status` in api-proxy — server-side poller over the tunnel with
   a 5s in-process cache; the browser hits ONE endpoint:
   | component | probe (from VPS, via tunnel) |
   |---|---|
   | Apache/static | implicit (endpoint answered) |
   | api-proxy | `/health` self |
   | labrouter→vLLM | `127.0.0.1:8004/health` + `/v1/models` id match |
   | Qdrant | `127.0.0.1:6333/healthz` + `/livez` |
   | embedder | `127.0.0.1:8005/health` |
   | reranker | `127.0.0.1:8016/→asrock:8006` health (verify exact path on-box first) |
   | verifier | POST or health to `VERIFIER_URL` (env-gated; absent = "off" card, gray not red) |
   Component state: `ok` / `degraded` (answered but wrong model id or slow) / `unknown`
   (probe failed — **gray, never red**, fail-open ethos). Include 24h verdict
   distribution (faithfulness buckets from the M1 JSONL) once M1 ships.
3. **Page**: `frontend/public/inside.html` (static, fetches `/api/status` every 30s,
   renders cards + one-sentence stack description linking the repo). Deploys with the
   existing rsync. Rate-limit `/api/status` per-IP.
4. **Acceptance**: page renders every component card within 2s from cold load; killing
   a home-side service flips its card to `unknown` within one poll cycle and changes
   nothing else; no component's failure produces a 5xx on the page itself.

---

## M3 — Curated "built by the model" lab (static)

1. **Step 0 — artifact preservation (do soon, independent of M1/M2):** the 2026-11-16
   proof artifacts currently live in `/tmp` (screenshots, `results.json`, ACP driver
   `acp-drive.mjs`, CDP verifier `verify-sim.mjs`). Commit them to
   `docs/lab/2026-11-16-local-model-build/` (screenshots + results + both harness
   scripts) before any reboot; reference the sim builds in
   `../super-agent/sand-simulator{,-baseline}` or copy the three-file builds in as
   subdirectories. Without this step M3 has nothing to exhibit.
2. **Page**: `frontend/public/lab.html` — write-up: task prompt verbatim; what the local
   model produced (code excerpts); the verification evidence (check list + screenshots);
   the managed-baseline comparison table (161s vs 55s; parity on functional checks);
   link to repo paths. Static only — no live tools, no live model calls.
3. **Acceptance**: page passes the existing frontend build; all images committed (no
   /tmp paths); content reviewed against claims.md style (every claim has a receipt).

---

## Cross-cutting docs-drift fixes (small, do inside whichever milestone touches the file)

1. README: "A4500 NVLink pair" → "dual RTX A4500 (PCIe Gen3)" (measured 2026-11-16).
2. `ai_portfolio_system.md` port table: :8007 row vs live T5810 vLLM slot; tunnel
   forwards section. Same for `homelab_t5810.md` if it repeats the table.
3. Commit `verifier.conf` / `verify-gate.conf` to `cloud/systemd/api-proxy.service.d/`
   (see M1.3) or document them as intentionally VPS-only — pick one, say which.
4. Confirm repo copies of the vllm unit (`home/vllm-service/`) match `/opt/vllm-service`
   on the T5810; record the check result in the plan file when done.

## Sequencing

M1 (proxy + frontend + ops, one PR) → M2 (second PR, needs M1's JSONL for verdict
distribution) → M3 (static PR, needs step 0). Drift fixes ride along the milestone that
touches each file. Nothing deploys until `scripts/eval_graded.py` is green.

## Pre-flight results (2026-11-16, against production — done, not pending)

Run after the build landed, before deploy:

1. **Judge enablement: CONFIRMED ON.** `verifier.conf` on the VPS sets
   `VERIFIER_URL=http://127.0.0.1:8007` (VPS-loopback tunnel endpoint → asrock judge)
   and `verify-gate.conf` sets `VERIFY_MIN_SCORE=0.002` — matching the committed repo
   copies. Receipt panels will show real percentages from day one. Remaining
   deployed-only config: `override.conf` (duplicates VERIFIER_GPU, already in the
   unit file) and `system-info.conf` (duplicates KB_DOC_COUNT/KB_CHUNK_COUNT) —
   harmless duplication to clean up at leisure, not gating.
2. **Judge `/verify` schema: CONFIRMED.** Live response carries `verdict_type`,
   `claims[]` (per-claim `text`/`verdict`/`source` — CONTENT-BEARING, never
   persisted), `judge_model`, `latency_s`, `n_claims`, `n_supported`,
   `n_unsupported`, `n_contradicted`, `faithfulness`, `flagged`. The receipts record
   captures the metadata fields (`n_supported`/`n_unsupported`/`judge_model` added
   2026-11-16). Judge `/health` → 200: the `/api/status` default health path is
   correct.
3. **Redaction catch:** the defensive `n_claims` fallback ("or claims") would have
   persisted the claims ARRAY (answer content) on any judge that omits the int
   count — fixed to accept ints only, regression-tested.
