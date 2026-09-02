# UPS shutdown integration for the T5810 — STAGED, NOT YET INSTALLED

**Status 2026-09-01:** the 1500 VA UPS is fitted and carrying the box (measured 642 W at the
plug, ~64 % of a 1000 W unit). What is *not* done is the half that protects the data.

```
$ lsusb                  # on the T5810
(no UPS device)
$ which upsc apcaccess
(none installed)
```

So right now the T5810 has **battery runtime but no automatic shutdown**. Per
`plans/ups-sizing-2026-09-01.md` §4, that converts an abrupt-cut risk into a *slower*
abrupt-cut risk: an unattended box that runs the battery flat still ends in exactly the
uncontrolled power loss the UPS was bought to prevent, just later.

## Blocked on one physical action

**Plug the UPS's USB data cable into the T5810.** Nothing here can be installed or tested
until that exists — `lsusb` must show the UPS before NUT has anything to talk to.

## Then, in order

1. `emerge -av sys-power/nut` (CPU-only build; does not touch the GPUs or vLLM).
2. Confirm the driver binds: `lsusb` shows the UPS, then `upsc ups@localhost` returns
   `battery.charge` / `ups.status`.
3. Install `ups-shutdown.sh` (below) as the `SHUTDOWNCMD`.
4. **Pull the plug on purpose, once.** An untested shutdown path is a belief, not a control.

## Why the shutdown ORDER matters here

A plain `halt` is not good enough on this box. Three things are holding state that a hard cut
corrupts, and they must come down in this order:

1. **`vllm-qwen38` first.** It holds a 29 GB model across two GPUs with TP workers that are
   *separate processes*. Killing the API server alone orphans them holding ~19 GB VRAM each
   (see `home/vllm-service/`). Stop it as a service so the reaper runs.
2. **`qdrant` next.** It has the entire retrieval index open. A half-written collection is
   the expensive failure — the KB has to be rebuilt from the committed corpus.
3. **Then halt**, which flushes the Gentoo root filesystem.

The verifier's `verdicts.db` lives on the asrock, not here; that box needs its own answer.

## Sizing note for whoever revisits this

Runtime follows the *average* draw (~152 W), not the 642 W peak, so a 1500 VA unit holds this
box far longer than a peak-based estimate suggests. The shutdown threshold should be set on
**battery charge / runtime remaining**, not on a timer — the load varies by ~4x between idle
and a generation burst, so any fixed timer is wrong at one end or the other.

---

# Shutting down the OTHER nodes too

The T5810 will be the only box with a data link to the UPS, so it has to tell the rest of the
fleet. The obvious approach is "passwordless sudo over SSH from the T5810." **NUT already
solves this, and its own mechanism is better here.**

## Use NUT's native master/slave, not SSH + sudo

NUT is built as a client/server protocol for precisely this:

- **T5810 = master.** Runs `upsd` (the server that talks to the UPS over USB) plus `upsmon` in
  **master** mode. It shuts down *last*, after its slaves have reported they are done.
- **asrock and any other node = slave.** Each runs only `upsmon` in **slave** mode, pointed at
  `upsd` on the T5810 over the LAN. When the master signals battery-low, each slave shuts
  *itself* down, locally, as root — because `upsmon` is already running as root on that box.

Nothing needs to reach across the network *as root*. Each node shuts itself down; the T5810
only broadcasts state.

### Why this is worth preferring over SSH + passwordless sudo

- **No root-equivalent trust path between boxes.** Passwordless sudo from the T5810 to every
  other node means a compromise of the T5810 is a compromise of the whole fleet. That matters
  more here than on a typical LAN: **the T5810 is the terminus of the SSH tunnel from the
  public VPS.** It is the most internet-exposed machine in the house, and it is exactly the one
  the fan-out design would hand fleet-wide root to. NUT's slaves grant only "tell me the UPS
  state," which is not a privilege worth stealing.
- **No fan-out script to hang.** An SSH loop over N hosts runs on a battery clock. One
  unreachable node with a 30-second connect timeout eats runtime that the *local* shutdown
  needed. `upsmon` slaves act in parallel and independently.
- **Ordering is a first-class feature.** `upsmon` master waits for slaves to disconnect before
  halting itself (`HOSTSYNC`, `FINALDELAY`). Hand-rolling that ordering over SSH is where these
  scripts usually go wrong.
- **It survives the T5810 being the thing that died.** A slave that loses its master's socket
  can be configured to act on its own rather than wait forever for an SSH command that is never
  coming.

Access control is `upsd.users` on the T5810 (a slave user with `upsmon slave`) plus
`LISTEN 10.0.1.x 3493`. Keep `upsd` bound to the LAN, never to a public interface — it is not
an internet-facing service, and neither is anything else on this box except through the tunnel.

## RESOLVED: both boxes are on the same 1500 VA UPS

This was the open question, and the answer is the good one — **the T5810 and the asrock are
both on the new 1500 VA / 1000 W unit.** (The old 330 W / 550 VA unit was kept for unrelated
devices at 116 W and is not part of this.)

That collapses the hard part of the design. **One battery, one clock.** Both machines lose
power at the same instant and their remaining runtime is the same number, so a single
`upsd` on the T5810 is an authoritative signal for both — not a proxy for someone else's
battery. The master/slave layout above is simply correct here:

- **T5810** — `upsd` (USB) + `upsmon` **master**. Halts last.
- **asrock** — `upsmon` **slave** over the LAN. Halts itself first; it is the cheaper box to
  lose, because both of its services are fail-open in the proxy.

Shut the asrock down **early and without hesitation**. While it is down the site still
answers: the reranker degrades to cosine top-5 and the verifier is skipped entirely. Every
second of battery it stops consuming is a second the T5810 gets to unload a 29 GB model and
close a Qdrant collection — which is the thing that actually corrupts.

### Sharing a UPS also means sharing the wattage

**Measured at the plug: 642 W for both boxes together under load — 64 % of 1000 W.**
Comfortable. The two peak together (the judge grades every answer the T5810 writes), so that
is already the concurrent case. GPU side, both boxes sampled at 1 Hz during one E2E probe:
T5810 **330.0 W**, asrock **63.5 W**.

Scaling those GPU figures — estimates, not readings — both GPUs pegged (asrock to its 180 W
cap, 5950X toward 142 W PPT) is about **870 W / 87 %**, and adding a return to the T5810's
200 W cap reaches roughly **950 W / 95 %**. Under rating, but that is the whole remaining
margin.

**So: avoid heavy lab inference on the asrock while the site is serving.** That box hosts
`llama3.3:70b`, `qwen2.5-coder:32b` and `gpt-oss:20b`; a 70B on a 16 GB card spills to CPU/RAM
and loads the 5950X at the same time. A UPS at 87 % when new is effectively past 100 % after a
few years of battery ageing.

**Meter the two boxes separately with the second KP125M** — not for the total, which is
measured, but for the split. Nothing currently attributes the 642 W between them, and an
earlier revision of these notes double-counted the asrock precisely because of that gap.

## What the asrock needs to stop cleanly

Less than the T5810, but not nothing:

- `verifier-service` writes `verdicts.db` (SQLite). That is the state worth protecting here.
- `ollama` holds the 14B judge; `rerank-service` holds the cross-encoder. Neither has
  persistent state that a hard cut corrupts, but both should stop before the DB does not.

Order: `verifier-service` → `ollama` → `rerank-service` → halt. Both the reranker and the
verifier are **fail-open** in the proxy, so the site keeps answering while they are down. That
is the whole reason this node can be shut down aggressively and the T5810 cannot.
