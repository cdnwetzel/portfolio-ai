# Fleet Assessment — 2026-08-30

Every line below was verified by logging into the boxes today. Where this contradicts
`CLAUDE.md`, **this document is right and CLAUDE.md is stale** — see §6.

Authoritative upstream sources found during the audit (read-only, on the T5810):
`/home/chris/ai/inference/FLEET-ENDPOINTS.md`, `MODEL-LEDGER.md`, and the build/tuning
scripts in `../psaios/tools/t5810-vllm/`. Those describe the *intended* lab design; this
document records the *actual running state* and where the two diverge.

---

## 1. What you actually have

| Node | Address | Hardware | Role | Access |
|---|---|---|---|---|
| **T5810** | `10.0.1.125` (also `10.0.1.51` on same NIC) | 2× RTX A4500, NVLink, 40 GB VRAM, 256 GB RAM | vLLM, labrouter, embedder, Qdrant, compress | `root@` OK |
| **asrock-b550** | `10.0.1.115` | RTX 5060 Ti 16 GB, 64 GB RAM | reranker, verifier, Ollama | `root@`/`chris@` OK |
| **mac-mini-3** | `10.0.1.20` | Apple M4, 16 GB | Ollama + MLX (measurement rig) | **this machine** |
| **orin1** | `10.0.1.67` | Jetson Orin Nano, 8 GB | vision (`qwen2.5vl:3b`) | `psadmin@` only |
| **VPS** | `cwetzel.com` | Ubuntu | Apache, api-proxy, tunnel origin | `root@` OK |

The T5810 carries **two IPs on one interface** (`enp0s25`): `10.0.1.125` and `10.0.1.51`.
vLLM's TP workers bind the `.51` address. Worth knowing before anyone "cleans up" an
address that looks stray.

### The design, as intended (from `FLEET-ENDPOINTS.md`)

**`labrouter` on T5810 `:8004` is the stable contract port.** The VPS tunnel forwards it;
models are swapped *behind* it so the VPS is never touched. vLLM backends sit on
`:8007` (Qwen3.8-27B-FP8), `:8008` (Qwen3.6-35B-A3B-FP8), `:8009` (pscode-14b).

This is a good design and it is genuinely in force. It also means the model-id pin I added
to the proxy (`MODEL_ID`) is complementary, not redundant: labrouter decides *which
backend*, the proxy decides *which model name it asks for*.

### T5810 ports (all loopback unless noted)

| Port | Owner | State |
|---|---|---|
| 8004 | **labrouter** (uvicorn) | listening — the contract port |
| 8005 | embedder `bge-base-en-v1.5` 768-d | listening |
| 8007 | **vLLM** `Qwen3.8-27B-FP8` (`0.0.0.0`) | listening — **see §3.1** |
| 6333/6334 | Qdrant | listening |
| 8788 | compress (headroom) | listening |
| 11435 | SSH tunnel → mac-mini-3:11434 | listening |
| 8006 | *(doc says reranker; nothing listening)* | **dead — reranker actually lives on asrock** |
| 8834 | `nessusd` | listening — unrelated scanner, noted for completeness |

---

## 2. What is healthy

- **asrock is in good shape.** `rerank-service`, `verifier-service` and `ollama` are all
  `started` and all three are in the default runlevel. GPU 13.0/16.3 GB used, 2.8 GB free.
- **Reranker** — supervised under `supervise-daemon`, respawn proven by test yesterday.
- **Retrieval path** — embedder, Qdrant and reranker all answer; live queries return 5
  sources with the cross-encoder pass running.
- **Model choice matches the ledger.** `MODEL-LEDGER.md` marks `Qwen3.8-27B-FP8` on T5810
  as **FINAL** for cwdotcom RAG (R1 75.0%, fleet best). The proxy is pinned to exactly that.
- **Quality baseline** (measured 2026-08-29, this model, reranker up): graded eval PASSED,
  32 grounded evals, mean grounding **4.78**, 0 safety hard-fails, 0 transport errors,
  0 review warnings; consistency battery 7/7 at 5/5.

---

## 3. What is broken or at risk — ranked

### 3.1 🔴 CRITICAL — vLLM is a zombie running from a deleted installation

**This is the single most dangerous fact about the system.**

- vLLM (pid 96627) was started **Aug 26 20:28** from `/opt/pscode/vllm-serve-env-0.27.1/`.
- **`/opt/pscode/` is now empty.** So is `/data/pscode/`.
- The process holds **820 deleted file mappings**; `/proc/96627/exe` resolves to a path
  marked `(deleted)`.
- Its parent is **PID 1** — nothing supervises it.
- `rc-service vllm status` → **stopped**. OpenRC is not managing the running server.

**Consequences, in order of severity:**

1. **If that process dies, generation is gone and cannot be restarted.** There is no vLLM
   venv on disk anywhere on the box. Recovery means rebuilding the environment first.
2. **This already caused a user-visible defect.** Streaming returns
   `HTTP 500: No module named 'anyio._backends'` because streaming triggers a *lazy*
   import, and the file it needs no longer exists. Already-resident code paths
   (`/v1/models`, non-streaming completions) keep working — which is exactly why the
   failure looked mysterious and partial. Confirmed identical against vLLM `:8007`
   directly and through labrouter `:8004`, so labrouter is not implicated.
3. The site is currently up **only** because the proxy falls back to non-streaming.

**Recovery path exists:** `../psaios/tools/t5810-vllm/01-build-venv.sh` builds a parallel
venv without touching the running one — it is written for exactly this, and guards on
`hostname = precision-t5810`.

**Read the tuning outcome before choosing a version.** That README records:
> *"OUTCOME (2026-08-19): the upgrade LOST, the tuning WON. vLLM 0.27.1 measured slower
> (5.2 tok/s) than the installed 0.14.0 (6.2). Turning CUDA graphs ON for 0.14.0 gave
> 27.7 tok/s, ~4.4×."*

That measurement was taken on the *previous* model, so it does not automatically transfer
to `Qwen3.8-27B-FP8` — but it means "just reinstall 0.27.1" is not obviously the right
call, and the CUDA-graphs setting matters more than the version.

**Model weights are safe:** `/data/models/Qwen3.8-27B-FP8` is intact at 29 GB, alongside
the 35B-A3B, the Coder-14B, and the embedding/reranker models.

### 3.2 🔴 The `vllm` OpenRC unit is stale *and actively dangerous*

`/etc/init.d/vllm` (dated Jun 7) would, if anyone ran it:
- launch from `/opt/pscode/vllm-serve-env/` — **a path that no longer exists**;
- serve `qwen2.5-coder-32b-instruct-awq` from `/home/chris/models/` — **the wrong model**;
- bind **`--port 8004`** — **colliding with labrouter, the stable contract port.**

So the one unit named `vllm` cannot work and would break the contract port if it did.
It should be rewritten to match reality or deleted outright.

### 3.3 🟠 `labrouter` has no supervisor

It is in the default runlevel (so it survives reboot), but its init script sets
`command_background="yes"` with **no `supervisor=` line** — it is `start-stop-daemon`
managed, and the running process is PPID 1. `respawn_max=5` is present but inert without
a supervisor. **If labrouter crashes, nothing restarts it**, and it is the single
chokepoint every chat request passes through.

### 3.4 🟠 `embed-service` and `verifier-service` — bounded respawn, no logging

Unchanged from yesterday's audit and still the most likely *next* silent outage:

| Unit | respawn_max | logging | blast radius |
|---|---|---|---|
| `embed-service` | 5 | **none** | **Total outage — no embeddings means no retrieval, and there is no fail-open path** |
| `verifier-service` | 5 | **none** | Faithfulness stops silently (chat unaffected) |
| `ollama` | 5 | has log | verifier's backend |
| `qdrant` | 8 | has log | already burned by this once — its comments record *"respawn_max exceeded → service latched off"* |
| `rerank-service` | 0 | has log | fixed |

`qdrant` hit this exact failure and was fixed in isolation; the lesson never propagated.

### 3.5 🟡 Monitoring still cannot see any of this

`/health` proves only that the proxy process is alive. Everything above — a zombie vLLM,
a dead reranker, broken streaming — is invisible to the 5-minute aggregator, the canary,
and the dead-man's switch. **This is why the outage on the 29th went unnoticed.**

### 3.6 🟡 Deploy stamp is stale
`DEPLOY_GIT_SHA=0b10cae` while running code is newer, so the version endpoint misreports.

---

## 4. The pattern behind all of it

Four separate incidents this week share one root: **critical-path processes that nothing
supervises, whose failure is silent.**

| | what happened | how it was found |
|---|---|---|
| reranker | stopped; retrieval silently degraded to cosine | noticed days later, by accident |
| vLLM | installation deleted under a live process | only when streaming broke |
| model rename | frontend hardcoded a model id that vanished | total outage, monitors green |
| embed/verifier | bounded respawn + no logs | not yet — this is the next one |

The common fix is not more services. It is: **supervise everything on the critical path,
give every unit a log, and probe the system end-to-end rather than process-by-process.**

---

## 5. Recommended order

1. **Rebuild the vLLM venv** (`psaios/tools/t5810-vllm/01-build-venv.sh`) — parallel,
   touches nothing running. Removes the "one process death from an unrecoverable outage"
   condition. Decide 0.14.0-with-CUDA-graphs vs 0.27.1 using the psaios measurements.
2. **Synthetic generation probe in the health aggregator** — one real question, assert a
   non-empty answer with sources. Would have caught every incident above.
3. **Fix/delete `/etc/init.d/vllm`**, then cut the running server over to a supervised
   unit at a maintenance moment. This also restores streaming.
4. **`respawn_max=0` + logging** on `embed-service`, `verifier-service`, `labrouter`;
   add a `supervisor=` line to labrouter.
5. **Reconcile CLAUDE.md** against §1 (see §6).
6. Deploy stamp; then the deferred quality work (context window at 32K, thinking A/B).

Items 1–2 are the ones that change the risk profile. The rest is hygiene.

---

## 6. Documentation drift

`CLAUDE.md` currently states, and is wrong about:

| Claim | Reality |
|---|---|
| Qwen2.5-Coder-14B + pscode LoRA | `Qwen3.8-27B-FP8` (LoRA never used in prod; see ledger) |
| 16K context | 32,768 |
| vLLM on `:8004` | labrouter on `:8004`; vLLM on `:8007` |
| Reranker "CPU on T5810" / asrock GPU | asrock GPU — T5810 `:8006` is dead |
| — | **`labrouter` is not mentioned at all** |
| — | **compress service `:8788` is not mentioned at all** |
| 62 docs / 35 docs, 94 chunks | 94 chunks / 34 docs (verify at reindex) |

`FLEET-ENDPOINTS.md` on the T5810 also notes cwdotcom's docs wrongly claim MiniLM-L6 for
the embedder — that one was already corrected here, but it shows the drift runs both ways.

**Recommendation:** rewrite CLAUDE.md's architecture section from §1 of this document, and
add a pointer to `FLEET-ENDPOINTS.md` as the upstream source of truth for the lab lane, so
the two stop diverging.
