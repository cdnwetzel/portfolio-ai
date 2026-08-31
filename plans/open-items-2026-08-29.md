# Open Items — 2026-08-29

Written after restoring the site from a total outage. Everything below was **verified
live today**, not read from documentation — the docs describe a system that no longer
exists (see P3).

**Ground truth as of 2026-08-29 11:40:**

| Component | State | Evidence |
|---|---|---|
| Chat answers | **Working, degraded** | self-test 3/3; running on non-streaming fallback |
| Model served | `qwen3.8-27b` (FP8, 32K ctx) | `/v1/models`; pinned via `MODEL_ID` |
| vLLM streaming | **BROKEN** | `HTTP 500: No module named 'anyio._backends'` |
| Embedder :8005 | Working | `http=200` from VPS |
| Qdrant :6333 | Working | retrieval returns 5 sources |
| Verifier :8007 | Working | `{"status":"ok","backend":"ollama","model":"qwen2.5:14b-instruct-q4_k_m"}` |
| **Reranker** | **Supervised, verified 2026-08-30** | `supervise-daemon`, default runlevel, respawn proven by killing the child (77654 → 77799) |
| Compress :8788 | Listening, no `/health` | `COMPRESS_URL` set in unit; undocumented |
| Deploy stamp | **Stale** | `DEPLOY_GIT_SHA=0b10cae`, actual code `199a639` |

---

## P0 — Production is degraded right now

### P0.1 — vLLM streaming is broken (`anyio._backends`)
**Impact:** answers arrive all at once instead of token-by-token. Perceived latency is
much worse even though total time is unchanged; TTFT telemetry is `None`.
**Diagnosis:** `/v1/models` and `stream:false` completions both work; only `stream:true`
returns HTTP 500. That is a lazily-imported anyio backend missing from the serving
environment — almost certainly a partially-completed pip upgrade.
**Not fixed here** because it lives on the vLLM host, which is behind the tunnel and is
*not* one of .20/.115/.125/.67.
**Fix:** on the vLLM host, in the venv serving :8004:
`pip install --force-reinstall anyio` then restart the service.
**Verify:** `curl -X POST …/v1/chat/completions -d '{…,"stream":true}'` returns SSE
`data:` lines, then `python3 scripts/selftest.py`. The proxy self-heals — it attempts
streaming first on every request, so no redeploy is needed once the host is repaired.
**Effort:** minutes, once someone is on that box.

### P0.2 — The reranker is gone — ✅ RESTORED 2026-08-29 12:21, but UNMANAGED
**Resolved:** Chris started `rerank.py` manually on asrock (.115:8006). It is reachable
through the existing `8016 → asrock:8006` tunnel forward, which is already the proxy's
default `RERANK_URL` — so no config change or redeploy was needed and reranking resumed
immediately. Verified live: `POST /rerank 200 OK`, `Reranked 15 candidates`, zero
`Rerank error` entries. Retrieval latency ~100 ms → 762 ms, i.e. the cross-encoder pass
is genuinely running again.

**Still open — see P0.3.** It is a `nohup` process, not a supervised service.

### P0.3 — The rerank OpenRC wrapper — ✅ RESOLVED 2026-08-30, verified by test
**What was actually true:** yesterday's "it's a nohup" report was already stale. By the
time it was checked, the unit had been rewritten on the box and was running properly
under `supervise-daemon`, in the default runlevel. The rewrite is good work: it waits for
real free VRAM instead of crash-looping into a CUDA OOM, sets `respawn_max=0` (unlimited)
in place of the old 5-in-30s that "gave up in under a minute", writes
`output_log`/`error_log` where the previous unit set **neither** (which is why the
original failure was undiagnosable), and refuses to start when `RERANK_BIND` is unset so
it cannot silently bind loopback and look healthy while being unreachable from the VPS.

**But it existed nowhere in git** — same production-ahead-of-repo drift as the 08-21/22
work. Now captured in `home/rerank-service/rerank-service.openrc`.

**Verified by test, not by status line:** killed the supervised child (77654);
`supervise-daemon` respawned it as 77799 and the port rebound. End-to-end after that:
tunnel `:8016` healthy, live query reranked, 0 `Rerank error` entries, retrieval 545 ms.

**Process note, recorded because it cost real time:** the first respawn test was invalid
and destructive. The pgrep pattern matched `supervise-daemon` itself — its cmdline
contains the python path and `rerank.py` — so `head -1` selected the *supervisor*. Killing
it orphaned the child to PPID 1 and left the service genuinely `unsupervised`; the
subsequent `restart` then could not stop the orphan, and the new supervisor's child
crash-looped on `address already in use` every 15 s, reloading the model onto the GPU each
time. Recovery was stop → kill orphan → clean start. **When testing a supervisor, resolve
the child by its PPID, never by a command-line pattern the supervisor also matches.**

### P0.4 — Same latent failure in embed-service and verifier-service (NEW, not fixed)
**Found by auditing sibling units after the rerank fix.** Both still carry the exact
config that caused this outage: `respawn_max=5` and **no `output_log`/`error_log`**.

| Unit | respawn_max | logging | risk if it latches off |
|---|---|---|---|
| `embed-service` | 5 | **none** | **Total outage.** No embeddings → no retrieval at all. Worse than the reranker, which fails open to cosine. |
| `verifier-service` | 5 | **none** | Faithfulness checking stops silently; chat unaffected (fully fail-open). |
| `ollama` | 5 | has log | verifier's judge backend |
| `qdrant` | 8 | has log | already learned this — its comments record "respawn_max exceeded → service latched off" |
| `rerank-service` | 0 | has log | fixed |

`qdrant` hit this precise bug before and was fixed in isolation; the lesson was never
applied across the fleet. `embed-service` is the one that matters: a bounded respawn on a
service with no logging means a transient squeeze latches it off permanently and
invisibly, and unlike the reranker there is no fail-open path.
**Fix:** `respawn_max=0` + `output_log`/`error_log` on embed and verifier, mirroring the
rerank unit. **Not done — needs authorization**, since it changes restart behaviour on
home boxes the user did not ask me to touch.

### P0.3 (original diagnosis, retained for context) — The rerank OpenRC wrapper is broken
**Impact:** the reranker is alive only because of a manual `nohup`. It will not come back
after a reboot, an OOM kill, or a crash — and its absence is silent, because the proxy
fails open to cosine. That is precisely how it went missing the first time and stayed
missing long enough to matter.
**Symptom:** `rc-service rerank-service start` reports "already starting" but never
brings the port up; `rerank.py` runs fine when launched directly. Logs currently going
to `/home/chris/rerank-service/rerank.log`.
**Likely causes:** a stale pidfile or supervise directory leaving OpenRC believing the
service is mid-start; or `start-stop-daemon` backgrounding semantics mismatched to how
`rerank.py` daemonises (needs `--background` / `--make-pidfile`, or the script must not
fork). Check for a stale pid under `/run/` first — that alone produces the
"already starting" wedge.
**Fix:** repair the wrapper so it supervises the process properly, then `rc-update add`
so it survives reboot. Chris's other session offered to do this — **yes, worth doing.**
**Verify:** `rc-service rerank-service restart`, confirm :8006 listens, reboot-test if
practical, and confirm `Rerank error` stays absent from the proxy log.
**Note:** this is the same class as DEFECT_LEDGER #2 (judge timeout wrapper living in
`/tmp`) — critical path depending on an unmanaged process. Worth a sweep for others.

### P0.2 (original diagnosis, retained for context) — The reranker is gone
**Impact:** retrieval is failing open to cosine top-5. Every answer is being generated
from bi-encoder candidates with no cross-encoder precision pass. This is the "15.8x
faster GPU reranker" from Tier 3 — it is simply not running.
**Evidence:** proxy default `RERANK_URL=http://127.0.0.1:8016` → `http=000`. The tunnel
also forwards `8006 → <host>:8006` → `http=000`. Nothing listens on :8006 across the
four fleet nodes. Logs show `Rerank error: ; falling back to cosine order` on every query.
**Confirmed 2026-08-29:** asrock-b550 (.115) is the intended verifier **and** reranker
host, and it is still serving the verifier — but a full port sweep of .115 shows only
**8007 and 11434** open. The verifier is up; the rerank service is simply not running.
So "verifier/reranker host" is accurate as *design intent* and wrong as *current state*.
**Likely why:** .115 now holds `llama3.3:70b` (42.5 GB) and `q36-moe` (36.9 GB) in
Ollama. Those far exceed the RTX 5060 Ti's 16 GB, so they are CPU/offload-served and the
box is under heavy memory pressure — plausible grounds for the reranker having been
stopped, deliberately or by an OOM. **Check first:** whether the service is stopped or
crash-looping (`rc-service rerank-service status`, then its log) before assuming a
capacity decision was made.
**Decision needed:** which host should run `home/rerank-service`, and on GPU or CPU?
CPU is viable — it ran that way pre-Tier-3 at ~4 s/query, which is tolerable given the
generator now dominates latency.
**Then:** start the service, set `RERANK_URL` in the unit file to the correct tunneled
port, redeploy, confirm `Rerank error` stops appearing.
**Effort:** ~1 hour including the tunnel/env wiring.

---

## P1 — Monitoring cannot see failure

### P1.1 — `/health` proves nothing
**This is the most important item in this document.** The site returned an empty answer
to *every* question for an unknown period — possibly days — and the 5-minute VPS
aggregator, the 30-minute T5810 canary and the healthchecks.io dead-man's switch all
stayed green, because `/health` only proves the proxy process is alive.
**Fix:** add a synthetic generation probe to the aggregator — one known question every
N minutes, asserting a non-empty answer with ≥1 source, paging via ntfy on failure. The
logic already exists in `scripts/selftest.py`; it just only runs at deploy time.
**Guard rails:** keep it to one probe on a long interval so it doesn't distort the
verdict corpus or load the GPU.
**Effort:** ~1 hour. **Do this before any further quality work** — none of the rest
matters if the next outage is also invisible.

### P1.2 — Deploy stamp is stale
`DEPLOY_GIT_SHA=0b10cae` while the running code is `199a639`, because a deploy happened
before the commit. The version endpoint therefore misreports what is live.
**Fix:** have `deploy.sh` refuse to deploy from a dirty tree, or stamp the real `HEAD`
after committing. **Effort:** ~15 min.

---

## P2 — Quality, and why every prior measurement is now void

### P2.1 — Re-baseline everything against `qwen3.8-27b` — ✅ DONE 2026-08-29
**New baseline (reranker restored, `enable_thinking=false`):** graded eval PASSED, 32
grounded evals, **mean grounding 4.78**, 0 safety hard-fails, 0 transport errors, and
**zero review-level warnings** — the first run on record with none. Consistency battery
**7/7 probes at 5/5**. Self-test 3/3. Recorded in DEFECT_LEDGER under "BASELINE".
**Closed on the way:** ledger #5 (favorite-language, root cause was a retrieval miss, not
the KB gap the original entry guessed at) and #6 (superseded by the model change).
**Do not** compare these to 4.80/4.70 or to "pscode 0.71" — different model.

### P2.1 (original) — Re-baseline everything against `qwen3.8-27b`
**The model changed, so all existing quality numbers are meaningless.** Specifically
void: the golden-set grounding baseline (4.70–4.80), the consistency battery's 6/6,
the base-vs-LoRA A/B, and DEFECT_LEDGER #1's "0.71 pscode" figure. Every one of those
was measured on `qwen2.5-coder-14b`.
**Do, in order:**
1. `python3 scripts/consistency_battery.py` — deterministic, no judge, cheapest signal.
2. `python3 scripts/eval_graded.py` — establishes the new grounding baseline.
3. `python3 scripts/ws_concurrency_check.py` — already passing; keep it passing.
4. Record the new numbers in DEFECT_LEDGER #1 and mark the old ones superseded.
**Note:** re-baseline *after* P0.2, or the numbers bake in a missing reranker.

### P2.2 — Reasoning-model token budget
`qwen3.8-27b` spends `max_tokens` on chain-of-thought before emitting content; with
thinking enabled, long answers returned **completely empty**. Mitigated today with
`chat_template_kwargs.enable_thinking=false` (`DISABLE_THINKING=0` to opt out).
**Open question:** whether thinking-on plus a larger budget produces *better* grounded
answers. Worth one A/B now that the harness exists — but only after P2.1 gives a baseline.

### P2.3 — Context window is still sized for 16K
The new model has 32K (`max_model_len: 32768`) but `MAX_CONTEXT_TOKENS` is unchanged.
More evidence per answer is the single cheapest quality lever available, and it directly
offsets P0.2's loss of reranker precision.
**Caveat:** `RAG_TOP_K` is a fixed *count*, so raising the budget alone changes nothing —
top-k must rise with it. Measure with the graded eval; do not assume it helps.

### P2.4 — Judge flags never reach the UI
The verifier correctly flags contradictions (confirmed 2026-08-19: `flagged=True,
n_contradicted=1` on the ASRock answer) but the flag did not appear in the browser.
So the faithfulness layer is doing its job invisibly. Root cause not yet found —
candidates are verdict arrival after socket close, or the flag UI being too subtle.
**Relates to** DEFECT_LEDGER #3 (verdict window).

### P2.5 — Carried-over ledger items
- **#2** judge timeout wrapper still in `/tmp` — will vanish on reboot.
- **#3** `VERDICT_WINDOW_MS` stopgap.
- **#4** `verdicts.db` has no backup. Tier 7 claimed this closed; verify it actually runs.
- **#5** "favorite programming language" answers neither way.
- **#6** grounding 4.80 → 4.70 watch item — **superseded by P2.1**, re-measure instead.

---

## P3 — The documentation describes a system that does not exist

`CLAUDE.md` is confidently wrong about: the model (Qwen2.5-Coder-14B + pscode LoRA →
`qwen3.8-27b`), the context window (16K → 32K), the reranker (documented as live on
asrock GPU → not running), the fleet topology, and it omits the compress service on
:8788 entirely. Per this repo's own rule — *"a wrong doc is worse than a missing one"* —
this is a real defect.

**Confirmed so far:**
- **asrock-b550 (.115)** — verifier (:8007, ollama backend, `qwen2.5:14b-instruct-q4_k_m`)
  + Ollama (:11434, 15 models incl. `llama3.3:70b`, `q36-moe`). Intended reranker host;
  reranker **not running**.
- **.125** — Qdrant (:6333) + something on :8007.
- **.20** — Ollama only (incl. `nomic-embed-text`, `qwen3-coder:30b`).
- **.67** — Ollama only (`qwen2.5vl:3b`).

**Still blocked on you:** the **vLLM + embedder host**. Neither :8004 nor :8005 is open
on any of the four, yet both answer through the tunnel — so a fifth box (or a
localhost-bound service on the tunnel endpoint) is serving them, and it is the host that
needs the P0.1 anyio repair. Also: what is the compress service on :8788, and is the
second :8007 on .125 a spare verifier or something else? Answer those and I will
reconcile CLAUDE.md against measured reality instead of guessing.

---

## Suggested order

1. ~~**P0.2** reranker~~ — ✅ done 2026-08-29 12:21.
2. **P1.1** monitoring — so the next outage is visible. Everything else is guesswork
   without it, and P0.3 makes it urgent: an unmanaged reranker can vanish silently again.
3. ~~**P0.3** rerank OpenRC wrapper~~ — ✅ done 2026-08-30. **New: P0.4** — embed-service carries the same bounded-respawn + no-logging config, and unlike the reranker it has no fail-open path.
4. **P0.1** streaming — small fix, large UX win, needs someone on the vLLM host.
5. **P2.1** re-baseline — now unblocked (reranker is back; streaming affects UX, not
   answer quality). **In progress 2026-08-29.**
6. **P3** docs — cheap once the topology question is answered, and it stops the next
   session starting from false premises.
7. **P2.2 / P2.3** tuning experiments, against the new baseline.

**One-line summary:** the site is up with retrieval fully restored, but it streams
nothing, runs on an unevaluated model, depends on an unsupervised reranker process, and
is watched by monitoring that cannot detect its own failure. Fix the monitoring first.
