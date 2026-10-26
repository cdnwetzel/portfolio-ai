# Archive — the multi-tenant SaaS scaffold

These documents describe a system that **was never shipped**, and are kept on purpose.

The project began as a multi-tenant portfolio SaaS: per-tenant row-level security, JWT +
API-key auth, Stripe usage billing, PostgreSQL with Alembic migrations, a Docker/Compose
deployment. Roughly a phase of that was built — the code lived in `src/` — and then the
scope was cut. What runs today at [dev.cwetzel.com](https://dev.cwetzel.com) is a
**single-tenant portfolio RAG chat**: no database, no auth, no billing, no tenants.

The scaffold's *code* is preserved on the **`legacy/saas-scaffold`** branch. These are its
*documents*. Nothing here describes the running system.

## Why keep them?

Deleting them would tidy the repo and erase the more useful signal: that the scope was cut
deliberately, in writing, rather than quietly abandoned. `06-billing.md` is a complete Stripe
integration design for a product that correctly never got built. Knowing when to stop is part
of the work.

## What's current instead

| For | Read |
|---|---|
| What the system is, and how RAG flows through it | [`../02-architecture.md`](../02-architecture.md) |
| How it's tested | [`../03-test-plan.md`](../03-test-plan.md) |
| How it's deployed and operated | [`../../DEPLOYMENT.md`](../../DEPLOYMENT.md), [`../../OPERATIONS.md`](../../OPERATIONS.md) |
| Overview | [`../../README.md`](../../README.md) |

## Contents

- `01-prd.md`, `01-architecture.md` — SaaS product requirements and architecture
- `02-backend-setup.md`, `03-frontend-setup.md` — scaffold setup guides (`src/`, Vite dashboard)
- `04-infrastructure.md`, `05-deployment.md` — WireGuard, Docker Compose, CI/CD deploy
- `06-billing.md` — Stripe products, webhooks, usage-based invoicing
- `07-checklist.md` — SaaS launch checklist
- `PROJECT_STATUS.md`, `IMPLEMENTATION_ROADMAP.md`, `READY_TO_EXECUTE.md`, `FRAMEWORK_ALIGNMENT.md`
  — planning and status snapshots from the SaaS phase
- `DEPLOYMENT_READY.md` — a 2026-06-07 go-live snapshot. Not SaaS-era, but its numbers are stale
  (MiniLM embedder, pre-re-chunk KB size, the reverted 32B trial), so it sits here rather than
  reading as current state.

- `infra/wg-cloud.conf`, `infra/wg-home.conf` — WireGuard peer configs. The design called for a
  WireGuard overlay between the VPS and the home server; an SSH tunnel shipped instead, and
  WireGuard was never installed. The key fields were always placeholders. Kept as the record of a
  transport that lost.

Numbering note: the archived `01-architecture.md` and `../02-architecture.md` are unrelated
documents that collided in an old numbering scheme. Neither describes the running system —
`../02-architecture.md` is the Gate-1 design (WireGuard, Llama 2 70B) and says so at the top.
