# Home-lab inference tuning — 2026-08-31

**Boxes:** precision-t5810 (2x RTX A4500 NVLink, Xeon E5-2699v4, 256 GB), asrock B550
(RTX 5060 Ti 16 GB, Ryzen 9 5950X), M4 Mac Mini 16 GB.
**Scripts:** [`scripts/tuning/`](../scripts/tuning/). **Logs:** `~/tuning-logs/` on each box.

## Result

| metric | before | after | |
|---|---|---|---|
| decode (256 tok, temp=0, single stream) | 29.43 tok/s | **33.2** | +12.8% |
| TTFT, 2,778-token prompt | 1,329 ms | **902 ms** | −32% |
| prefill | 478–489 ms/1k | **325–337 ms/1k** | −32% |
| embed `:8005` (bge-base, CPU) | 45 ms | **24 ms** | −47% |
| Qdrant top-15 search | 2.0 ms | **1.0 ms** | −50% |

Roughly **450 ms off the front of every turn**, and a 26 s turn becomes ~23 s.

## What was wrong

`/etc/local.d/nvidia-mining.start` ran `/usr/local/bin/mine-tune.sh` at every boot:

```
nvidia-smi -pl 130      # card default is 200 W
nvidia-smi -lgc 1200    # max SM clock is 2100 MHz
```

A crypto-miner's hashrate-per-watt profile applied to an inference box. Measured under
100% decode load: **SM dragged to 705–810 MHz, power pinned at 127 W against the 130 W
cap, temperature only 48–52 °C.** Power-starved, not thermally limited.

Separately the CPU governor was `userspace` — which, with no setter daemon, pins every
thread at `scaling_min` (1200 of 2200 MHz) forever. And KSM was on, sharing **0 pages
after 164 full scans** on a 251 GB box with no VMs.

**Power and clock caps cannot cause or prevent VRAM exhaustion.** The cap was believed to
protect against wedging; VRAM free measured identical (840/842 MiB) at 130/155/165/180/200 W.
The real anti-wedge levers are vLLM's `--gpu-memory-utilization`, `--max-model-len`,
`--max-num-seqs` and `cudagraph_capture_sizes`, all already in force.

## The power curve

Stepped with the clock lock held so power was the only variable, then unlocked:

| config | tok/s | peak SM | peak power | peak temp |
|---|---|---|---|---|
| 130 W, locked 1200 | 29.43 | 705–810 sustained | 127/124 (capped) | 54/49 |
| 155 W, locked 1200 | 32.47 | 1200 | 144/133 | 58/52 |
| 200 W, locked 1200 | 32.43 | 1200 | 145/134 | 60/54 |
| 150 W, unlocked | 32.57 | 1860/1890 | 150/150 | 67/65 |
| **165 W, unlocked** | **33.43** | 1860/1875 | 167/165 | **71/70** |
| 180 W, unlocked | 33.87 | 1860/1860 | 180/180 | 75/73 |
| 200 W, unlocked | 34.23 | **1845/1860** ↓ | 200/200 | **79/77** |

155 → 200 W with the lock held changed nothing (32.47 → 32.43): power stopped being the
constraint at ~155 W and the clock lock took over. Unlocking is what mattered.

**165 W chosen.** It keeps 97.7% of the 200 W throughput at 71/70 °C instead of 79/77 °C.
At 200 W the SM clock is *lower* than at 150 W (1845 vs 1860) — GPU Boost backing off as
temperature rises. The last 0.8 tok/s costs 4 °C and buys ~180 ms on a 256-token answer.

**Soak:** 10 min continuous at 165 W → mean 32.85 tok/s over 77 requests, steady state
**33.2**, peak 78 °C, temps and clocks both plateaued. Every thermal flag stayed
`Not Active` throughout; the only active throttle reason was `sw_power_cap`, i.e. the
limit we chose. (The mean is understated — live test traffic batched alongside the soak
for ~60 s, during which aggregate throughput rose to ~60 tok/s across two requests.)

## Why prefill gained 2.5x what decode gained

Decode at batch 1 is **memory-bandwidth-bound**. A4500 is 640 GB/s against a ~14.5 GiB
shard per card, so the roofline is ~44 tok/s; memory clock was already maxed at 7601 MHz
and never moved. 29.43 → 33.2 took it from 67% to 79% of that ceiling, and there is no
hardware headroom left — 200 W is the card's hard limit.

Prefill is **compute-bound**, and the SM clock roughly doubled. Hence −32%.

We had been optimising against the metric that responded least.

## Dead ends (measured, not assumed)

- **Clock floor for cold starts.** Idle SM is 210 MHz, so a bursty first request looked
  like it should pay a ramp. Measured: **COLD 900 ms vs WARM 896 ms — a 3 ms penalty.**
  The ramp completes inside the first milliseconds of a ~900 ms prefill. `-lgc 900,2100`
  would cost idle watts for nothing. Dropped.
- **tmpfs for model weights.** Cold start is 505 s of which **282 s is torch.compile** —
  compute, not I/O. Warm start is 22 s. There is no I/O to remove. Also: do **not** put
  `~/.cache/vllm` (3.5 GB of `torch_compile_cache`) on tmpfs — it would turn every reboot
  into a cold start. `/var/tmp/portage` is already a 128 GB tmpfs.
- **`max_tokens` on short queries.** Flagged `Adaptive max_tokens: 2048 for 42-char query`
  as a bug; it is a deliberate fix (`b6efc2e`). A cap is a ceiling, not a brevity control —
  lowering it truncates mid-sentence rather than producing concision.

## asrock B550 (RTX 5060 Ti) — one large win, two nulls

**Judge model eviction was costing 16.2 s per verify.** `/etc/conf.d/ollama` set
`OLLAMA_KEEP_ALIVE="60s"` while the docs claimed 30m. On sparse portfolio traffic the
11.4 GB judge was evicted between nearly every query, so essentially *every* verify paid
a full model reload. Measured with a forced unload (`keep_alive:0`), then three calls:

| call | wall |
|---|---|
| COLD (after forced unload) | **18.81 s** |
| WARM | **2.58 s** |
| WARM | **2.58 s** |

Now `30m`. This matters beyond latency: the `done` frame tells the client a verdict is
coming and the socket waits for it. A 19 s verdict lands after the reader has moved on;
a 2.58 s one lands while the answer is still on screen.

**Null results, recorded as such:**

- **CPU governor `powersave` → `performance`.** Rerank went 15.0 → 13.6 → 14.7 ms with
  `min` stuck at 13.1–13.2 throughout — noise. Unlike the T5810, nothing was broken here:
  `userspace` on the T5810 pins threads at `scaling_min` forever, whereas `powersave` under
  `amd-pstate` is a normal dynamic governor that already boosts under load.
- **`OLLAMA_KV_CACHE_TYPE=q8_0` (+ flash-attn).** Judge VRAM 11,380 MiB before,
  **11,376 MiB** after. A 4 MiB delta is noise; it bought nothing at this context size.

Kept both (harmless), but `03`'s value is the keep-alive fix alone.

## Where the time actually goes

A real 26-second turn: **~1 s retrieval, ~25 s generating 800+ tokens.** TTFT is 902 ms.
Generation length is ~96% of the wall clock, and no GPU setting touches it. The largest
remaining lever is the **system prompt** — 825 tokens → 400 saves ~12 s, four times
everything won here, at zero hardware cost. That is a voice/quality change gated by the
graded eval, not a perf tweak.

## Remaining, ranked

1. **Answer length via the system prompt** (~12 s/turn) — gate on `scripts/eval_graded.py`.
2. **Symm-mem all-reduce.** `--disable-custom-all-reduce` (needed for graph capture) leaves
   the engine on `PYNCCL`, the slowest option for the small messages decode generates:
   `Using ['PYNCCL'] ... out of potential ['NCCL_SYMM_MEM', ..., 'SYMM_MEM', 'PYNCCL']`.
   Try `VLLM_ALLREDUCE_USE_SYMM_MEM=1`. Graph-capturable, unlike custom AR.
3. **Prefix caching.** `enable_prefix_caching=False` at every engine init, hit rate 0.0%
   always. The launcher never passes a flag, `CacheConfig` defaults it `True`, the RISC-V
   gate doesn't apply, and "Disabling prefix caching" is logged **zero** times. Unexplained —
   worth one experiment with an explicit `--enable-prefix-caching`, since the constant
   system prefix is shared by every request including single-turn ones.
4. **ngram speculative decoding.** No draft model, no extra VRAM; RAG quoting is the
   ideal workload. `plans/rag-improvements.md` §2.3 ruled out only the *draft-model* variant.
5. **labrouter availability — ACCEPTED RISK, do not reopen.** `:8008`/`:8009` are down and
   the fallback loop lives only in the non-streaming branch, so it never applies to cwdotcom.
   Decision (Chris, 2026-08-31): this is a home lab, not a product with an SLA. A single
   backend is the accepted design. Recorded so it stops being re-raised as a finding.
6. **Mac Mini `04`** — 21.6 tok/s is 85% of its ~25.5 roofline; ~4 tok/s exists in total.
   The real issue is memory: 858 MB of active swap, and `qwen3-coder:30b` is 18 GB on a
   16 GB machine.

## M4 Mac Mini — attempted, invalidated, deferred

The 2026-08-31 run produced **no usable data**, for two independent reasons. Recorded
because both are easy to repeat.

1. **Ollama never restarted, so the new env was never in effect.** The script was run
   under `sudo`, which makes `launchctl bootout gui/$UID` resolve to `gui/0` instead of
   the user's `gui/501`; the `launchctl load` fallback no-opped because the job was
   already loaded. The process stayed pid 40470 throughout. Confirmed afterwards by
   reading the live process environment — `OLLAMA_FLASH_ATTENTION`, `OLLAMA_KV_CACHE_TYPE`
   and `OLLAMA_NUM_PARALLEL` were absent from the running process despite being present
   in the plist. **Printing the plist proves only that a file was written.**
2. **The machine was busy.** `photolibraryd` at 138–182% CPU plus `coreduetd`,
   `corespotlightd` and `suggestd`, load average 4.1 rising to 5.9. The same model that
   measured 21.6 tok/s earlier in the evening measured 13.8–14.2 during the storm. That
   35% drop was ambient load, not a regression, and it confounded step D as well
   (13.3/11.9 tok/s at a raised wired limit is not evidence the change hurt).

`iogpu.wired_limit_mb` was returned to 0. Nothing from this run is kept.

**Script hardening applied afterwards** (`scripts/tuning/04-mini-freebies.sh`,
`00-mini-measure.sh`): refuse to run under sudo; assert the ollama PID actually changed
after restart and abort if not; read the live process environment rather than the plist;
warn and prompt when load average >= 2. Both verified to parse under the Mini's
**bash 3.2** with BSD userland — the box has no `timeout`, `gtimeout`, `gsed` or `gawk`,
and needs `stat -f%z` / `sed -i ''` rather than the GNU forms.

### Follow-up 2026-08-31 (later): models moved off the USB drive

The storm was self-inflicted and temporary — the Photos library had just been moved to the
external volume, so Spotlight and Photos were re-indexing it. Once it settled (load 5.9 -> 1.3)
the box became measurable, and the storage layout turned out to be backwards.

`~/.ollama/models` was a **symlink** to `/Volumes/MiniExt1TB/AI/ollama/models`, an enclosure on
**USB 3.2 Gen 2, not USB4** — both 40 Gb/s Thunderbolt ports read "No device connected". Measured
on the same 8.4 GB blob, reading the external copy first so any cache advantage favoured it:

| | throughput | 6 GB read |
|---|---|---|
| external (USB 3.2 Gen 2) | **612 MB/s** | 10.0 s |
| internal NVMe | **2,215 MB/s** | 2.8 s |

**3.6x.** Models moved to internal (`scripts/tuning/08-mini-models-to-internal.sh`); the 22 GB
Photos library deliberately stays external as cold archival data. That also ends the bus
contention — `photoanalysisd` scanning 22 GB no longer competes with model loads.

`qwen3-coder:30b` deleted: 18 GB on a 16 GB machine, it could never fit. 17 GB reclaimed, and
every remaining model now fits in RAM.

**Two measurement traps hit here, both recorded because they nearly produced false results:**

1. **The symlink would have made rsync copy a directory into itself** — and the src-vs-dst blob
   count check would have PASSED, because they were the same directory. The script now resolves
   both paths with `pwd -P` and refuses when they match.
2. **The before/after load benchmark measured page cache, not disk.** Unloading a model from
   Metal does not evict it from the filesystem cache, so both arms read from RAM and reported
   0.83 s vs 0.85 s — no difference, on a change that is genuinely 3.6x. On a 16 GB machine the
   practical gain therefore appears only on cold starts (post-reboot, or after cache pressure),
   not on every load.

Side effect worth noting: the restart finally applied the ollama env stranded in the plist since
the earlier failed run — `FLASH_ATTENTION=1`, `NUM_PARALLEL=1`, `KV_CACHE_TYPE=q8_0` are now live
in the process, confirmed by reading `ps eww`, not the plist.

**Still deferred:** the throughput benchmark. Expectations remain low: 21.6 tok/s is ~85% of the
~25.5 tok/s roofline for a 4.7 GB q4 model on M4's ~120 GB/s, so roughly 4 tok/s exists
in total. The reason to run it is memory — 858 MB of active swap, and `qwen3-coder:30b`
at 18 GB on a 16 GB machine — not throughput.

## Method notes

- **Assert against live state, never the file you edited.** `05-persist.sh --verify` reads
  `nvidia-smi` and `/sys`. A config write plus a clean restart is not evidence.
- **Cool between A/B arms.** GPU Boost lowers clocks with temperature well before any
  thermal flag trips, so an un-cooled second arm is biased against itself.
- **Never edit a running script.** Bash reads by byte offset; patching one mid-run shifts
  everything under it. Cost one 06 run.
- **Check the machine is idle before measuring.** Ambient load cost a whole Mini run.
- **Verify the live process, not the config file.** A written plist, a restarted unit and
  a passing health check together still do not prove a setting took effect.
- **`git fetch` before concluding anything about drift.** A "deployed commit missing from
  the repo" finding, and a long list of "stale docs", were both a 19-commit-behind local
  checkout. Production and repo matched byte-for-byte the whole time.
