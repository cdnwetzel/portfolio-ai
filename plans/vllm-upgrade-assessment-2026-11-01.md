# vLLM upgrade assessment: 0.27.1 vs 0.28–0.32 (2026-11-01)

Desk research only: release notes, GitHub issues/PRs, forum, PyPI metadata, and a grep of
this repo. **Nothing here was measured on the T5810.** Issue numbers below were re-checked
with `gh` on 2026-11-01 (exist, open, titles match).

## Verdict

1. **Stay on 0.27.1 for now.** There is an open, unfixed regression report on *our exact
   model, checkpoint and GPU architecture* in 0.31 and 0.32 (#63505). The release notes'
   speed wins for our architecture are real but unmeasured on Ampere.
2. **Do MTP k=4 on 0.27.1 next.** It's the cheapest likely gain and has the best adjacent
   evidence (below). Don't combine it with an upgrade: one variable at a time.
3. **If and when we upgrade, test 0.28.0 before 0.32.0.** 0.28 carries the Qwen3.5 fused MTP
   kernel and predates both risky 0.29 default changes (Model Runner V2, FlashInfer
   all-reduce). #63505 reports 0.28.0 as *correct* on our model on sm_86.
4. **Muse Glimmer 30B is parked.** Thinking can't be disabled (only a "Reasoning strength"
   system-prompt line), which conflicts with the RAG role, and one model serves both roles here.

## Release status (checked 2026-11-01)

| version | date | status |
|---|---|---|
| 0.27.1 | 2026-08-11 | **live**; no 0.27.2 exists |
| 0.28.0 | 2026-08-26 | released |
| 0.29.0 | 2026-09-09 | released |
| 0.30.0 | 2026-09-22 | released |
| 0.31.0 | 2026-10-05 | released |
| 0.32.0 | 2026-10-18 | latest on PyPI |
| 0.33.0 | — | **git tag only** (pushed 2026-11-01 after rc0–rc3). No GitHub release, no notes, not on PyPI |

## Dependencies: the upgrade is lighter than usual

| | 0.27.1 (live) | 0.32.0 |
|---|---|---|
| torch | ==2.13.0 | ==2.13.0 (**unchanged**) |
| Python | ≥3.10 | ≥3.11 (venv is 3.12.13) |
| transformers | ≥5.5.3 | ≥5.16.1, <5.20 (we have 5.16.1) |
| flashinfer | 0.6.16.post3 | 0.7.0.post1 (JIT rebuild at first start; needs the g++-14 workaround the launcher already sets) |
| venv size | 7.6 GB | similar; 685 GB free |

A side-by-side venv makes rollback a one-line `VLLM_VENV` change in conf.d.

## Could help (unmeasured on sm_86)

- **0.28**: fused CUDA post-conv MTP decode kernel for Qwen3.5 GDN (#51674); GDN gates
  aligned with speculative tokens (#51812); adaptive budget for speculative scheduled
  tokens (#51725), which may address the "max_num_scheduled_tokens=2048" warning;
  Qwen3.5 text-only checkpoint fixes (#50734, #50355).
- **0.29**: fused GDN MTP for all Qwen head ratios (#52539); padded FULL cudagraph dispatch
  for uniform decode under spec decode (#53407, MRV2), aimed at our silent FULL→PIECEWISE
  hazard; hybrid prefill checkpoints, 9–25% TTFT (#52789).
- **0.31**: fix for a throughput cliff when `max_num_seqs` isn't a multiple of 8 (#57355).
  We run 4.
- **0.32**: dynamic K for MRV2 autoregressive speculators (PR #57053, 1.2–1.3x kernel
  speedup, synthetic); Mamba/GDN prefill checkpoints with MTP + prefix caching (#59759, #60797).

## Could break

| risk | versions | relevance | mitigation |
|---|---|---|---|
| **#63505**: Qwen3.8-27B-FP8 on sm_86: illegal memory access with prefix caching, gibberish without; "regression since v0.28.0"; both runners | 0.31, 0.32 | **our model + arch** (but PP=3, not TP=2) | don't use 0.31+ until fixed or disproven on TP=2 |
| **#59987**: `--disable-custom-all-reduce` no longer falls back to NCCL; FlashInfer and symm-mem all-reduce stay on | 0.29+ | **our flag**; custom AR is disabled precisely because it breaks graph capture on this pair | `VLLM_ALLREDUCE_USE_FLASHINFER=0 VLLM_ALLREDUCE_USE_SYMM_MEM=0`; fix PR #60011 open |
| Model Runner V2 default (#53183); MRV1 deprecated, removal targeted ~0.32 | 0.29+ | MTP + hybrid + FULL graphs on sm_86 is untested in the notes | check the log for which runner actually loads; A/B both if V1 still exists |
| **#55766**: NaN logits after a prefix-cache hit near a block boundary, Qwen3.5/3.8 + MTP k=3 | reported 0.28; repro on 0.32 (V1 runner only) | **our config** | whether 0.27.1 is affected is unknown |
| `max_tokens` becomes an upper bound, not a reservation (#57035) | 0.32 | proxy asks 2,048 on ~14K prompts at 49K ctx, so no effect | none needed |
| `reasoning_content` output removed (#50624) | 0.28 | proxy reads only `content` (`api-proxy.py:529`) | none needed |
| flag renames: `--enable-mamba-fine-grained-prefix-cache`, mamba cache mode `all`, `tokenizer_mode=slow`, `VLLM_TEST_FORCE_FP8_MARLIN` | 0.29–0.31 | none appear in our launcher, conf.d or scripts (grepped) | none needed |

## Open bugs that affect us on ANY version, 0.27.1 included

- **#49918** (open since 2026-07-26; fix PR #47123 unmerged): a prompt of exactly
  `1 + num_speculative_tokens` tokens is treated as uniform decode, so the FULL spec-verify
  graph skips the GDN state write and the output is deterministic garbage. At k=3 that's a
  4-token prompt; at k=4, 5 tokens. cwdotcom can't hit it: every chat request carries the
  ~600-token system prefix. Raw `/v1/completions` callers through labrouter could. A
  4-token probe would confirm it on our box.
- **PR #50021** (open): unbounded GDN spec-decode index can crash the engine under
  multi-turn load. No release fixes it yet.
- **#63593** (open, 0.32): on Qwen3.8-27B, MTP with forced reject diverges from target-only
  output at **K ≥ 5**; K ≤ 3 clean. This caps how deep k should go.

## Evidence for MTP k=4 on 0.27.1

club-3090 discussion #1024 (github.com/noonghunna/club-3090/discussions/1024): **0.27.1**,
2x RTX 3090 TP=2 (Ampere, same generation as ours), Qwen3.8-27B W4A8.

| MTP depth | narrative tok/s | code tok/s |
|---|---|---|
| n=3 | 66.7 | 84.5 |
| **n=4** | **76.4 (+15%)** | **105.6 (+25%)** |
| n=5–6 | flat | flat |

Adjacent, not identical: W4A8 instead of FP8, 3090 instead of A4500. With #63593's K ≥ 5
divergence, **k=4 is the sensible ceiling**. Our own extrapolation from k=2 → k=3 predicted
~+10–13% on the bench. Promotion still has to beat k=3 on real site turns (47 cold / 60–75
warm) and pass the same 50-generation quality gate, because each extra draft token slows
every step whether accepted or not.

Setup: add an `mtp4` mode to `scripts/tuning/09-vllm-experiments.sh` with
`VLLM_CUDAGRAPH_SIZES=[1,2,4,5,8,10,15,20]` (multiples of 5 up to 4×5). The launcher
refuses to start otherwise.

## Upgrade test plan (when there is a reason)

1. Build `/opt/pscode/vllm-serve-env-0.28.0` alongside the current venv. Production untouched.
2. In a window: point `VLLM_VENV` at it, add
   `VLLM_ALLREDUCE_USE_FLASHINFER=0 VLLM_ALLREDUCE_USE_SYMM_MEM=0` (harmless on 0.28, needed
   on 0.29+), restart.
3. Assert from live state: resolved cudagraph mode FULL_AND_PIECEWISE, capture sizes, MTP
   resolved, which model runner, all-reduce backend PYNCCL.
4. Gates: `bench-vllm.sh 8007 3` (check it returns non-empty, since it uses `/v1/completions`),
   4-token probe (#49918), repeat_sample 50, graded eval. Compare to 0.27.1 baselines.
5. Revert by switching `VLLM_VENV` back if anything fails.
6. Only then consider 0.32 (or 0.33 once it has notes), and only after #63505 is resolved or
   disproven on TP=2.

## Watch list (add to the quarterly challenger screen)

#63505, #59987 / PR #60011, #49918 / PR #47123, #55766, #63593, PR #50021, and the
0.33.0 release notes once published.

## Muse Glimmer 30B notes

Supported since vLLM 0.28 (#51655); recipe drafter `meta-models/Muse-Glimmer-30B-assistant`
with `{"method":"dflash","num_speculative_tokens":15}`. FP8-block checkpoint
`RedHatAI/Muse-Glimmer-30B-FP8-block` is 32.8 GB, tight for 2x 20 GB with KV, and untested
on Ampere. Thinking can't be disabled (discuss.vllm.ai thread 2970; `enable_thinking` does
not apply). Parked for the RAG role.
