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

#### Verification (done 2026-08-30 — every alternative explanation ruled out)

Asked to be certain before acting, so each claim was tested rather than inferred:

| Hypothesis | Test | Result |
|---|---|---|
| `/opt/pscode` merely **unmounted**, data recoverable | `mount`, `/etc/fstab` | **Ruled out.** No mounts under `/opt` or `/data`, no fstab entries. `/opt/pscode` does not exist as a directory. |
| Directory exists but unreadable | `ls -ld /opt/pscode` | **Ruled out.** `No such file or directory`. `/opt` mtime is **Aug 26 21:01** — ~33 min *after* vLLM started (20:28). |
| anyio broken for some other reason (version skew, bad install) | live traceback | **Ruled out.** Traceback resolves inside the deleted path. |
| Wider damage than anyio | all distinct `No module named` in log | **Only** `anyio._backends`. 493 occurrences, no other missing module. |

**The exact failure chain, from `/var/log/qwen38/writer.log`:**
```
starlette/responses.py:273  __call__                    ← StreamingResponse
starlette/_utils.py:85      create_collapsing_task_group
anyio/_core/_tasks.py:200   create_task_group
anyio/_core/_eventloop.py:206 get_async_backend         ← dynamic import
importlib/__init__.py:90    import_module
ModuleNotFoundError: No module named 'anyio._backends'
```
Every frame resolves under `/opt/pscode/vllm-serve-env-0.27.1/`, and the interpreter
frames under `/opt/pscode/.local/share/uv/python/cpython-3.12.13-.../`. Both are gone.
This is the `StreamingResponse` path specifically, which is exactly why streaming fails
while `/v1/models` and non-streaming completions still work. **Diagnosis confirmed.**

#### The running configuration — preserved here because it exists nowhere else

This was reconstructed from `/proc/96627/cmdline`. **If that process dies, this is lost.**
Recording it is the single cheapest risk reduction available:

```
vllm serve /data/models/Qwen3.8-27B-FP8
  --served-model-name qwen3.8-27b
  --host 0.0.0.0 --port 8007
  --tensor-parallel-size 2
  --gpu-memory-utilization 0.93
  --max-model-len 32768
  --max-num-seqs 4
  --gdn-prefill-backend triton
  --reasoning-parser qwen3
  --enable-auto-tool-choice --tool-call-parser qwen3_coder
  --disable-custom-all-reduce
  --compilation-config {"cudagraph_capture_sizes":[1,2,4,8]}
  --limit-mm-per-prompt {"image":0,"video":0}
  --trust-remote-code
```

Note `--compilation-config` — **CUDA graphs are already enabled**, so the psaios tuning
win is applied and does not need re-deriving.

#### Recovery — viable, but the cutover is a one-way door

Prerequisites verified present: `uv` at `/usr/bin/uv`, the `pscode` user (uid 992, in
`video`), and **893 GB free**. `../psaios/tools/t5810-vllm/01-build-venv.sh` builds a
parallel venv, guards on `hostname = precision-t5810`, and touches nothing running.

**But two facts make the cutover irreversible, and they were not obvious:**

1. **No GPU headroom for a parallel instance.** Both A4500s have **~697 MiB free** of
   20,470 MiB (`--gpu-memory-utilization 0.93`). A second vLLM cannot be started to test
   against — the new server can only be validated by *replacing* the old one.
2. **No fallback backend.** labrouter's other slots (`:8008` 35B-A3B, `:8009` pscode-14b)
   are **not running**. There is nothing to route to during a cutover.

Therefore: **stopping the current vLLM cannot be undone** — there is no venv on disk to
restart it from, and no second GPU slot to prove a replacement works first. The window is
a genuine generation outage lasting a 29 GB model load.

**Version choice — do NOT follow the psaios README reflexively.** It recommends 0.14.0
with CUDA graphs over 0.27.1, but that was measured on `qwen2.5-coder`. The running
config uses `--reasoning-parser qwen3`, `--tool-call-parser qwen3_coder` and
`--gdn-prefill-backend triton`, which are 0.27.x-era flags, and the model is FP8. **Rebuild
0.27.1 to match what is running.** Downgrading would likely not support this model at all.

**Safe sequencing:**
- *Phase 1 — zero risk, do anytime:* build the 0.27.1 venv alongside; verify with
  `python -c "import vllm, anyio._backends"`. Proves the venv is complete without
  touching the GPU or the running server.
- *Phase 2 — needs a maintenance window:* write a correct supervised OpenRC unit (see
  §3.2), stop the zombie, start under supervision, verify streaming, run the self-test.

#### Phase 1 — ✅ COMPLETE 2026-08-30, verified at each step

The psaios script could **not** be used as-is: `_common.sh` sets
`OLD_VENV=/opt/pscode/vllm-serve-env` and `01-build-venv.sh` dies on
`[ -d "$OLD_VENV" ]` at line 13 — the guard fires precisely because the thing it guards
against has already happened. Its *method* was followed manually instead.

| Step | Action | Verification |
|---|---|---|
| 1 | Read scripts, find the blocker | `OLD_VENV` guard + missing `PSCODE_HOME` |
| 2 | `install -d -o pscode -g pscode -m 0755 /opt/pscode` | owns correctly; write-tested as `pscode` |
| 3 | `uv python install 3.12` | CPython **3.12.13** installed |
| 4 | `uv venv --python 3.12 …-0.27.1.new` | interpreter 3.12.13, prefix correct |
| 5 | `uv pip install vllm==0.27.1` | 7.6 GB, exit 0 |
| 6 | Import verification | **PASS** — see below |
| 7 | Confirm production untouched | pid 96627 alive (4d), GPU 696/698 MiB free, site HTTP 200 |

**Step 6 results — the decisive check:**
```
vllm  0.27.1                    (matches the running server exactly)
torch 2.13.0+cu130   cuda_available=True devices=2
anyio 4.14.2  ->  _backends._asyncio imports OK   <== the exact production failure
create_task_group + get_async_backend: OK
starlette 1.6.0   fastapi 0.136.3
```

**Gotcha for anyone repeating this:** `uv` walks up from the CWD and hits root-only
`/root/uv.toml` (`Permission denied`) when invoked via `sudo -u pscode` from `/root`.
Run it with `cd /opt/pscode` first. Also, modern `anyio` has no `__version__` attribute —
use `importlib.metadata.version("anyio")`, or a verification script fails on its own
`print` and looks like a build failure when the build was fine.

**The venv is deliberately left at `…-0.27.1.new`, NOT the canonical path.** Renaming it
into `/opt/pscode/vllm-serve-env-0.27.1` while the zombie runs would put that path back on
the live process's `sys.path`, and its next lazy import would load
`anyio._backends._asyncio` from the **new** anyio (4.14.2) into a process whose
`anyio._core` is already resident from the **old, unknown-version** anyio. That might
silently fix streaming — or produce a subtle cross-version mismatch inside a process
serving users. Not worth it. **The rename belongs in the cutover, with vLLM stopped.**

> **If the zombie dies before cutover:** recovery is
> `mv /opt/pscode/vllm-serve-env-0.27.1{.new,}` then start with the §3.1 command line.
> The unrecoverable-outage condition is now gone; only the rename stands between a dead
> process and a working restart.

#### 3.1.1 — Protecting the 4.4x CUDA-graph tuning across the restart

**This is the highest-value thing to not break, and it is silent when broken.** The box
is fast because of measured tuning, not defaults
(`../psaios/docs/t5810-vllm-cudagraph-tuning-2026-08-19.md`). Three flags must survive
*together*; losing any one collapses throughput to roughly a quarter, and the server keeps
answering — just slowly. Neither `/health` nor the self-test would notice.

| # | Element | Why it is required |
|---|---|---|
| 1 | **CUDA graphs ON** (no `--enforce-eager`) | the 4.4x itself |
| 2 | `--disable-custom-all-reduce` | custom AR **breaks graph capture** on this 2x A4500 NVLink pair (upstream vLLM bug, not an A4500 quirk) |
| 3 | `--compilation-config {"cudagraph_capture_sizes":[1,2,4,8]}` | vLLM captures ~70 sizes by default and capture memory scales with the count — this is why every `gpu-memory-utilization` still OOMed until it was capped |

Historical measurements (14B, 0.14.0): eager **6.2 / 6.3** → graphs on **27.7 / 28.1 /
27.3 / 26.5** tok/s. Output byte-identical at temp=0, so it is pure throughput with no
quality trade.

**Verified 2026-08-30:** all three flags are present in the running process's argv **and**
in the replacement launcher's argv, which diffs byte-identical (29/29 args). The
`--compilation-config` JSON is exactly why the launcher exists rather than
`command_args`: OpenRC's word-splitting would strip its double quotes, and vLLM would fall
back to default capture sizes — silently losing element 3 and, with it, the tuning.

**Measured baseline before any cutover** (256 tok, temp=0, single stream, `ignore_eos`,
`home/vllm-service/bench-vllm.sh`):

| session | tok/s |
|---|---|
| run A | 29.6 / 29.3 / 29.3 |
| run B | 28.4 / 27.8 / 27.4 |

**Accept band: ~27–30 tok/s.** Some run-to-run variance is normal. A result near **6–7
tok/s means the graph tuning was lost**, not that the box is busy — check the three flags
before anything else. `bench-vllm.sh` prints their presence alongside the number so a slow
result is immediately diagnosable.

**Gate the cutover on this:** benchmark before, benchmark after, and if the after-number
is outside the band, the restart is not "done" regardless of what the self-test says.

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

1. **Rebuild the vLLM venv at 0.27.1** (`psaios/tools/t5810-vllm/01-build-venv.sh`) —
   parallel, zero risk, touches nothing running. This alone removes the "one process death
   from an unrecoverable outage" condition, which is the whole point. Match 0.27.1; see
   §3.1 on why the README's 0.14.0 recommendation does not apply to this model.
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
