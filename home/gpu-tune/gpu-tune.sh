#!/bin/bash
# GPU tuning for the 2x RTX A4500 inference pair (precision-t5810).
#
# REPLACES the old mine-tune.sh, which applied a crypto-MINING efficiency profile
# (-pl 130, -lgc 1200) to a box that serves LLM inference. Under decode load that
# profile dragged the SM clock to 705-810 MHz at 100% util and only ~50C: the
# cards were power-starved, not thermally limited.
#
# Measured 2026-08-31 (bench-vllm.sh, 256 tok, temp=0, single stream, qwen3.8-27b):
#     130W + locked 1200 MHz ... 29.43 tok/s   <- the old mining profile
#     150W + unlocked .......... 32.57 tok/s   67/65 C
#     165W + unlocked .......... 33.43 tok/s   71/70 C   <- CHOSEN (the knee)
#     180W + unlocked .......... 33.87 tok/s   75/73 C
#     200W + unlocked .......... 34.23 tok/s   79/77 C   <- 1C from abort, and SM
#                                                           clocks had ALREADY begun
#                                                           backing off (1845 vs 1860)
# 165W keeps 97.7% of the 200W throughput with an 8C thermal margin instead of 1C.
# Do not raise this without re-running ~/tuning/02c-t5810-soak.sh.
#
# NOTE: power/clock settings cannot cause or prevent VRAM exhaustion. VRAM free
# measured identical (840/842 MiB) at 130/155/165/180/200W. The anti-wedge levers
# are vLLM's --gpu-memory-utilization, --max-model-len, --max-num-seqs and
# cudagraph_capture_sizes -- see /etc/conf.d/vllm-qwen38.
nvidia-smi -pm 1
nvidia-smi -pl 165
nvidia-smi -rgc          # clocks UNLOCKED (was: -lgc 1200)
