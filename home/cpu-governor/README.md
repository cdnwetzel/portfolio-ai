# CPU governor service (T5810)

Installs to `/etc/init.d/cpu-governor`, enabled in the `default` runlevel.

Pins all 44 CPUs to the `performance` governor **before** the services that depend on it.

## Why it is on the chat critical path

The box ships with `userspace`, which pins every thread at `scaling_min` — 1200 MHz of 2200 —
forever, because nothing ever sets a speed. Measured 2026-08-31:

| | `userspace` | `performance` |
|---|---|---|
| embed service :8005 (bge-base, **CPU-only**) | 45 ms | **24 ms** |
| Qdrant search | 2.0 ms | **1.0 ms** |

Both are in the retrieval path of every single query. Losing this roughly doubles retrieval
latency, silently.

## Why it is a service and not an /etc/local.d script

Identical root cause to `home/gpu-tune/` — and this one was **masked during diagnosis**.

`local` declares `after *`, so it waits for every service in the runlevel, including
`vllm-qwen38`, which sits in `starting` for minutes while it loads FP8 weights and captures
CUDA graphs. `local` never gets its turn, so nothing in `/etc/local.d` runs at boot.

The trap: when this was checked, all 44 CPUs read `performance` and it looked fine. They read
that way **only because `local` had been started by hand minutes earlier**, while diagnosing
the GPU cap. The troubleshooting created the healthy state it then observed. On a clean boot
the governor stays at `userspace`.

**Lesson worth more than the fix: a state you produced while investigating is not evidence.**
Check what a *cold* path does, not what the box looks like after you have poked it.

## Verifying — no reboot needed

Re-entering a runlevel starts *stopped* services and leaves *started* ones alone, so vLLM is
untouched and the site stays up:

```bash
for g in /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor; do echo userspace > "$g"; done
rc-service cpu-governor stop
openrc default
cat /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor | sort | uniq -c   # expect 44 performance
```

Run 2026-09-04: 44 × `userspace` → runlevel started the service unprompted → 44 ×
`performance`, logged to `/var/log/cpu-governor.log`, `vllm-qwen38` still `started`.

Ordering confirmed in OpenRC's dependency tree rather than by reading the file:

```
embed-service  iafter: bootmisc,cpu-governor
qdrant         iafter: bootmisc,cpu-governor
vllm-qwen38    iafter: bootmisc,cpu-governor,gpu-tune
```

The service **verifies the result rather than the writes** — it counts CPUs still not on
`performance` and fails if any remain.

## Still in /etc/local.d, deliberately not converted

`fstrim-weekly.start` and `nessus-nft.start` have the same problem and also do not run at
boot. Neither is on the cwdotcom critical path, so they are recorded here rather than changed:
converting services nobody asked about is how unrelated breakage gets introduced.
