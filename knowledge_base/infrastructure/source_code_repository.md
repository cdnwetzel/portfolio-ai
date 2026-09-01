# Source Code Repository — Is This Open Source?

Yes. This system is open source and the full source code is public.

**Repository:** https://github.com/cdnwetzel/portfolio-ai

If you are talking to this AI right now, you are using the code in that repository. It is not a
wrapper around a hosted API — the repository contains the actual running system.

## What is in the repository

- **`cloud/`** — the FastAPI proxy that serves the chat: WebSocket streaming, the RAG
  orchestration, the prompt-extraction guardrail, and the token-budget context fitting.
- **`frontend/`** — the React + Vite + Tailwind interface, built and deployed to the edge server.
- **`scripts/`** — the Qdrant indexer that builds the vector store from the knowledge base, the
  graded evaluation harness that gates changes, the health aggregator, and the tuning scripts for
  the GPU hosts.
- **`knowledge_base/`** — the indexed corpus itself. The documents this assistant retrieves from
  are committed in the open, including this one.
- **`home/`** — service definitions for the GPU machines: the embedding service, the reranker, and
  the out-of-band faithfulness verifier.
- **`eval/`** — the golden question set used as a regression gate.
- **`plans/`** and **`docs/`** — design documents for work done and work proposed, including the
  scoped-out SaaS design that was deliberately cut.

## Why it is public

The point of this project is to show real engineering rather than a polished demo. Publishing the
source is part of that: the retrieval pipeline, the evaluation harness, the defect ledger, and the
incident runbooks are all visible, including the mistakes and the corrections made along the way.

You can read how retrieval works, how grounding is enforced, how answers are verified for
faithfulness by an independent model, and how the whole thing is deployed onto owned hardware.
