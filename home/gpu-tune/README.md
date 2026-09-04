# GPU tuning for the T5810 A4500 pair

Two files, both live on the T5810 and captured here because production has drifted ahead of
this repo before and it cost real time:

| Repo file | Installs to | Role |
|---|---|---|
| `gpu-tune.sh` | `/usr/local/bin/gpu-tune.sh` | applies persistence mode, the **165 W** cap, unlocked clocks |
| `gpu-cap-check.sh` | `/usr/local/bin/gpu-cap-check.sh` | every 5 min: verifies the cap, **reapplies and logs** if it has drifted |
| `gpu-tune.openrc` | `/etc/init.d/gpu-tune` | OpenRC service: waits for the driver, applies, **verifies**, logs; ordered `before vllm-qwen38` |

## The 165 W cap is a tuning choice, not a limit

Measured on this hardware (`bench-vllm.sh`, 256 tok, temp=0, single stream):

| Cap | tok/s | Temp |
|---|---|---|
| 130 W + clock locked to 1200 MHz | 29.43 | the old crypto-mining profile |
| 150 W | 32.57 | 67/65 °C |
| **165 W** | **33.43** | **71/70 °C — chosen, the knee** |
| 180 W | 33.87 | 75/73 °C |
| 200 W | 34.23 | 79/77 °C — 1 °C from abort, SM clocks already backing off |

165 W keeps 97.7 % of the 200 W throughput for an 8 °C thermal margin instead of 1 °C.

## Why this is an OpenRC service and not an /etc/local.d script

**2026-09-03: it was a local.d script, and it silently never ran.** Found by rebooting to
verify an unrelated fix — the cards came up at their 200 W default while every document said
the cap was "set at boot".

The first diagnosis was wrong, and the way it was wrong is the useful part. The obvious guess
was a race: local.d runs before the NVIDIA driver is ready, `nvidia-smi` fails, nothing
notices. A wait-and-retry wrapper was written for that. **It changed nothing** — and the
reason was visible in the evidence: after the next boot there was *no log at all*. Not a
logged failure, no log. The script had never executed. A wrapper that fails would have
written a line; silence meant the mechanism, not the timing.

The real cause is two problems, and the second is the one that matters:

1. **`local` declares `after *`** — it waits for *every* service in the runlevel.
   `vllm-qwen38` takes minutes to start (FP8 weight load + CUDA-graph capture), so `local`
   never got its turn. Nothing in `/etc/local.d` ran — not `gpu-tune`, not `cpu-governor`.
2. **Even if it had eventually run, the ordering was backwards.** It would have applied the
   cap *after* vLLM was already up and had captured its CUDA graphs at 200 W. A cap has to be
   set before the consumer starts, not eventually.

Hence an explicit ordered service: `nvidia-persistenced` → `gpu-tune` → `vllm-qwen38`,
declared with `need nvidia-persistenced` and `before vllm-qwen38`. Verified in OpenRC's own
dependency tree rather than by reading the file:

```
depinfo_90_service='vllm-qwen38'
depinfo_90_iafter_1='gpu-tune'
```

The service also **waits for the driver** (retries `nvidia-smi -L` for 60 s) and **verifies
the result rather than the exit code** — it re-reads `power.limit` and fails the service if
it did not get 165 W, writing `/var/log/gpu-tune.log` either way. `rc_logger="YES"` is set in
`/etc/rc.conf` so the next boot failure leaves a boot log behind.

**This mattered.** At the 200 W default these cards sit at 79 °C, which the tuning notes
record as 1 °C from thermal abort, and they draw ~70 W more than the figure the UPS budget
was measured against.

**Lesson worth keeping:** `/etc/local.d` is not a boot mechanism for anything another service
depends on. It runs after everything, so it cannot order itself before anything.

## Verifying

Do not read the script. Reboot, then:

```bash
rc-status | grep gpu-tune                                  # expect started
tail -3 /var/log/gpu-tune.log                              # expect a timestamp from THIS boot
nvidia-smi --query-gpu=power.limit --format=csv,noheader   # expect 165.00 W, 165.00 W
/opt/vllm-service/bench-vllm.sh 8007 3                     # expect ~33-34 tok/s
```

### Verifying the runlevel actually starts it — without a reboot

The failure this service replaced was not "it ran and failed", it was **"the runlevel never
started it"** (`local` declares `after *` and starved behind vLLM's multi-minute start). That
specific property can be tested without rebooting, because re-entering a runlevel starts
*stopped* services and leaves *started* ones alone — so vLLM is untouched and the site stays
up:

```bash
rc-service gpu-tune stop
nvidia-smi -pl 200          # put it back to the driver default
openrc default              # re-enter the runlevel
rc-service gpu-tune status  # expect: started
nvidia-smi --query-gpu=power.limit --format=csv,noheader   # expect 165 W
```

Run 2026-09-03: the runlevel started `gpu-tune` unprompted, the cap went 200 → 165, the log
recorded it, and `vllm-qwen38` stayed `started` throughout. Zero downtime.

**What this does and does not prove.** It proves the service is correctly registered and that
runlevel processing reaches it — the actual defect. It does not exercise cold-boot timing,
where the NVIDIA driver may not be ready yet; that is covered by the service's own 60-second
`nvidia-smi -L` retry, and bounded regardless by the 5-minute drift check below.

## The cap is now self-healing, which is what makes it safe to stop worrying about

The boot-time service is the primary control, but it had to be treated as unproven until a
real boot exercises it. So there is a second, independent control: `gpu-cap-check.sh` runs
every 5 minutes from `/etc/cron.d/power-metrics` and:

- exits silently when both cards read 165 W,
- otherwise logs the drift to `/var/log/gpu-cap-check.log`, **reapplies the profile**, and
  logs the resulting value.

That bounds the exposure. Even in the worst case — the boot service somehow does not run —
the cards sit at 200 W for at most five minutes rather than indefinitely, and it leaves a
record saying so. Verified by resetting the cap to 200 W and running it: detected, reapplied,
confirmed 165 W.

This is deliberately belt-and-braces rather than a replacement. The service fixes the cause
(ordering); the cron catches the case where the cause was misdiagnosed. Given this defect was
*already* misdiagnosed once — the first fix assumed a driver race and changed nothing — a
second, differently-shaped control is proportionate.
