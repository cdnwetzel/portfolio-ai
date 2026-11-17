# Demo surface — receipts, /inside, and /lab (2026-11-16/17)

The portfolio site does not just describe its stack — it shows it. Three surfaces,
all live at dev.cwetzel.com since 2026-11-17:

## Per-answer receipts (chat)

Every grounded answer carries receipts inline, below the text:

- **Sources (N)** — expandable, with Qdrant relevance scores: the exact chunks the
  answer was grounded in.
- **⚡ timing line** — time-to-first-token (retrieval + prefill), decode tok/s, total
  seconds. Proof the answer was generated live on the home hardware.
- **✓ verdict line** — after the answer, a separate judge model on a second machine
  (Qwen2.5-14B on the asrock B550) re-reads every claim against the cited chunks and
  reports a faithfulness score with counts (e.g. "93% · 6/7 claims supported").
  Flagged answers show an amber warning instead. The judge runs out-of-band: the
  answer is already delivered, chat is never blocked, and a judge outage degrades
  the line to "could not complete" — never an error. Verdicts are persisted
  server-side (append-only JSONL) so they can be re-fetched after page reloads.

## /inside — live stack status

A public status page probing every component through the tunnel: vLLM (with a
model-id contract check — a healthy endpoint serving the wrong model shows
"degraded", the exact 2026-08-29 failure mode), Qdrant, embedder, reranker, and the
faithfulness judge, plus a 24h histogram of judge verdicts. Fail-open gray states:
an unreachable component shows "unreachable", never red, because the chat rides
through single-component failures by design.

## /lab — the local model builds a sand simulator

Receipts for an agentic capability test (2026-11-16). The home model
(Qwen3.8-27B-FP8, the same one answering chats) and a managed flagship (K3.1 Pro)
were each given the identical task through an identical agent harness: build a
falling-sand simulator (HTML/CSS/JS, walled 400x400 playground, 4x4px grains, pour
on left-mouse-hold). Both builds were verified in a real headless browser — real
mouse events, pixel-level analysis of pour/fall/pile behavior — and both sims are
playable live from the lab page.

Head-to-head, stated explicitly because the two builds are easy to confuse:

- **LOCAL MODEL (Qwen3.8-27B, home):** per-grain color variation, efficient
  offscreen-buffer rendering, stricter diagonal physics (grains cannot tunnel
  through corners). Its wall is a **visual CSS frame around the canvas — not
  simulated physics**.
- **MANAGED BASELINE (K3.1 Pro):** implemented the wall as **physical wall cells
  inside the simulation grid**; pointer-event input handling; single-tone sand with
  simpler per-cell rendering.
- **Speed:** the baseline was ~3x faster wall-clock (55s vs 161s agent turn).
- **Functional checks:** BOTH builds passed every check (pour-on-hold, fall after
  release, piling at the bottom).

Do not mix these up: the in-simulation wall belongs to the BASELINE (K3.1 Pro);
the local model's wall is visual-only. The local model's edge was rendering polish
and physics strictness, not wall handling.

Full harness, screenshots, and comparison: /lab.html and
docs/lab/2026-11-16-local-model-build in the repo.

## Why this matters for evaluating the site

A wrapper around a cloud API produces the same visible surface this site had before
2026-11-17: a chat box. The receipts are the difference — they make the owned
infrastructure (home GPUs, second-box judge, RAG grounding) verifiable by the
visitor instead of asserted. The /lab exhibit extends the same standard to agentic
work: claims about the local model come with the harness output that proves them.
