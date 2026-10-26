# Fleet tuning scripts (2026-08-31)

Measured tuning for the three boxes cwdotcom actually runs on: the T5810 (2x A4500),
the asrock B550 (RTX 5060 Ti), and the M4 Mac Mini. Results and reasoning:
[`plans/homelab-inference-tuning-2026-08-31.md`](../../plans/homelab-inference-tuning-2026-08-31.md).

Every script logs to `~/tuning-logs/` on the box it runs on, keeps a `*-latest.log`
symlink, and takes `--rollback`. Nothing is persistent until `05-persist.sh` runs.

| script | box | root | what |
|---|---|---|---|
| `00-measure.sh` | T5810 | no | full before/after suite; probes all three boxes |
| `01-t5810-freebies.sh` | T5810 | yes | KSM off + CPU governor `performance` |
| `02-t5810-power-stepup.sh` | T5810 | yes | 130→155→200 W stepped, y/N between steps |
| `02b-t5810-find-knee.sh` | T5810 | yes | power sweep at unlocked clocks, finds the efficiency knee |
| `02c-t5810-soak.sh` | T5810 | yes | sustained-load thermal soak at a chosen wattage |
| `05-persist.sh` | T5810 | yes | make it survive reboot; `--verify` asserts LIVE state |
| `06-ttft-bench.sh` | T5810 | for `--ab` | TTFT vs prompt size, cold-start cost, old-vs-new A/B |
| `ttft_probe.py` | T5810 | no | helper for 06; streams and times first token |
| `00-mini-measure.sh` | mini | no | Mini-local before/after: tok/s, load time, swap, GPU residency |
| `08-mini-models-to-internal.sh` | mini | no | move ollama models USB -> internal NVMe (3.6x) |
| `09-vllm-experiments.sh` | T5810 | yes | one vLLM flag experiment: apply, restart, verify, measure, auto-revert |
| `exp_probe.py` | T5810 | no | workload probes for 09 — repeated-prefix TTFT and quoting decode |
| `03-asrock-freebies.sh` | asrock | yes | governor, ollama flash-attn + q8_0 KV, keep-alive 60s→30m |
| `04-mini-freebies.sh` | mini | for step D | ollama flash-attn/KV/parallel, Metal wired limit |

## Two rules these encode

**Assert against live state, never the file you edited.** `05-persist.sh --verify` reads
`nvidia-smi` and `/sys`, not its own output. A config write plus a clean restart is not
evidence a setting took — see `psaios/docs/t5810-vllm-cudagraph-tuning-2026-08-19.md`,
where a phase script edited a config, restarted, benchmarked, and had changed nothing.

**Never edit a script while it is running.** Bash reads by byte offset; patching a
running script shifts everything under it and it dies mid-run with a syntax error.
This happened during the 06 run on 2026-08-31.
