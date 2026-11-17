# Lab — 2026-11-16: local model builds a sand simulator, verified end to end

Proof artifacts for the local-inference capability test run on 2026-11-16 against the
home vLLM stack (Qwen3.8-27B-FP8, TP=2 on the T5810's dual A4500s, served as
`local/qwen3.8-27b` on port 8007). Preserved per `plans/demo-surface-plan-2026-11-16.md`
(M3 step 0) so the evidence survives independently of the machine that produced it.

## What happened

Both models were given the identical task through the identical harness — a Kimi Code
CLI session driven over ACP (`kimi acp`), tools auto-approved, no human edits:

> Create a real-life sand simulator (HTML/CSS/JS). Wall around the playground.
> 400x400 px playground, 4x4 px grains. Grains roll down and pile up. Hold left mouse
> button to add sand.

| | local/qwen3.8-27b (T5810) | kimi-code/k3.1-pro (managed) |
|---|---|---|
| Agentic turn time | 161s | 55s |
| Harness functional checks | 5/5 pass | 5/5 pass |
| Artifact | `local-model-qwen38/` | `baseline-k31-pro/` |

Verification (`harness/verify-sim.mjs`): each build was loaded in headless Chrome via
CDP; real `Input.dispatchMouseEvent` left-button holds poured sand at the cursor;
palette-free pixel-variance analysis of canvas strips plus screenshots proved
pour-at-cursor, fall-after-release, and bottom piling. Evidence per build (screenshots
at initial / while-holding / settled stages + machine-readable check results) is under
`evidence/<build>/`.

## File map

- `harness/acp-drive.mjs` — ACP driver: spawns `kimi acp`, creates a session, pins the
  model, sends the task, auto-approves tool permissions. Args: `<model-alias> <workdir>`.
- `harness/verify-sim.mjs` — CDP verifier: headless-Chrome behavioral checks + PNG
  screenshots + `results.json`. Args: `<sim-directory-name>` under `~/ai/super-agent/`
  (paths are parameterized; adjust when re-running).
- `local-model-qwen38/`, `baseline-k31-pro/` — the three-file sims each model wrote.
- `evidence/` — screenshots and `results.json` per build (all checks passed, no page
  errors).

## Re-running

Requires: `kimi` CLI with a provider for the model alias, `google-chrome-stable`,
node >= 22. The verifier's screenshot output paths and the driver's workdir are
hardcoded to the 2026-11-16 run — adjust the constants at the top of each script.
