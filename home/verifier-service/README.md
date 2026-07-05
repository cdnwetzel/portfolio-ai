# verifier-service — faithfulness verifier

Out-of-band, fail-open judge for the portfolio RAG chat. For each completed answer it
scores whether every claim is supported by the chunks that were actually retrieved,
stores a verdict, and exposes rolling metrics + a review queue. See the full spec:
[`plans/verifier-faithfulness-layer.md`](../../plans/verifier-faithfulness-layer.md).

**Target host:** the spare Ryzen 9 5950X / RTX 3060 Ti box — **not** the T5810 (its
A4500s are full serving vLLM). Mirrors the `home/rerank-service/` pattern.

## Files
| File | Role |
|---|---|
| `verifier_core.py` | Pure logic — FOLLOWUPS strip, refusal detection, lenient JSON parse, scoring. Unit-tested, no model needed. |
| `verifier.py` | FastAPI service — `/verify` `/metrics` `/review` `/health`; judge call + SQLite store + throughput valve. |
| `verifier-service.openrc` | OpenRC unit (Gentoo). For systemd, see below. |
| `fixtures.json` | §8.1 judge-accuracy cases (faithful / hallucinated / contradicted / refusal / paraphrase). |
| `run_fixtures.py` | Runs fixtures against a live `/verify` — the judge's own gate. |
| `test_verifier_core.py` | `pytest` unit tests for the pure logic (13 tests, run in CI). |

## Setup
```bash
# On the spare box: pull the judge model (Ollama, low-friction on one 8 GB card)
ollama pull qwen2.5:7b-instruct-q4_K_M

# From the repo root (SSH access to the box):
VERIFIER_HOST=chris@<RYZEN_LAN_IP> ./home/setup-verifier.sh
```
Config via env (or `/etc/conf.d/verifier-service`): `JUDGE_BACKEND` (ollama|openai),
`JUDGE_URL`, `JUDGE_MODEL`, `THRESHOLD` (0.8), `SAMPLE_RATE` (1.0), `MAX_INFLIGHT` (2),
`DB_PATH`, `RETENTION_DAYS` (90), `VERIFIER_DEBUG_CAPTURE` (off).

## What's stored (keeps the "not stored or logged" claim honest)
The `verdicts` table holds **scores only** — an opaque `request_id`, the timestamp, the
faithfulness score, the flag, claim counts, judge model, latency. **No query, answer, or
claim text.** The score is a durable, queryable metric; the conversation that produced it
is not persisted. A legacy DB with the old text columns is migrated to the lean schema on
startup (`_migrate_legacy`), and `VACUUM` + `secure_delete` physically scrub the purged
text from the file. Set `VERIFIER_DEBUG_CAPTURE=1` **only** to reproduce a specific
hallucination — it retains query/answer/claims in a separate `debug_captures` table.
Keep it off in production.

## Judge model — independence matters
The judge **must not be the 14B that wrote the answer** (echo bias — a same-family judge
penalizes assertive answers and can grade a *more* faithful version *worse*; firm review
`bl89`). A different 7–8B model on the spare box satisfies this by construction. Keep it.

## Wiring into the chat (default OFF)
1. The proxy hook already exists in `cloud/api-proxy.py` (`_fire_verify`, fire-and-forget
   after `done`). It is a **no-op until `VERIFIER_URL` is set** in the api-proxy unit.
2. Add the SSH tunnel forward `-L 127.0.0.1:8007:<RYZEN_LAN_IP>:8007` to
   `cloud/systemd/portfolio-ai-tunnel.service` **only after** the box IP is pinned and
   reachable (an unresolvable `-L` kills the whole tunnel).
3. Set `Environment=VERIFIER_URL=http://127.0.0.1:8007` in `api-proxy.service`.

## Testing (spec §8)
- **Pure logic:** `pytest home/verifier-service/test_verifier_core.py` (no model).
- **Judge accuracy (§8.1):** `python3 home/verifier-service/run_fixtures.py --url http://<box>:8007`.
- **Fail-open (§8.2):** stop the service / unset `VERIFIER_URL` → chat must be unchanged.
- **Latency invariant (§8.3):** `scripts/selftest.py` smoke before/after wiring — unchanged.

## systemd alternative
If the box runs systemd, install this instead of the OpenRC unit:
```ini
[Unit]
Description=Faithfulness Verifier (portfolio RAG)
After=network.target
[Service]
User=chris
ExecStart=/home/chris/miniforge3/bin/python3 /opt/verifier-service/verifier.py
Restart=always
RestartSec=10
[Install]
WantedBy=multi-user.target
```
