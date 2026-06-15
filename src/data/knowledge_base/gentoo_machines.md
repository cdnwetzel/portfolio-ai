# gentoo-machines — Multi-Machine Gentoo Configuration Repo

## What It Is

`gentoo-machines` is my personal infrastructure-as-code repository for managing a fleet of Gentoo Linux machines. Every machine in my homelab has a dedicated directory with hardware-specific kernel configuration, build profile, and documented reasoning for every non-obvious choice.

**Repo:** https://github.com/cdnwetzel/gentoo-machines  
*(Private — contains hardware-specific config; excerpts shared on LinkedIn)*

---

## The Problem It Solves

Gentoo's power is also its problem: every machine can be configured perfectly for its hardware, but "perfectly configured" is easy to lose track of across multiple machines. `gentoo-machines` is the answer — a version-controlled record of what's running, why, and how to reproduce it.

Machines don't drift silently because changes are committed. If I rebuild the T5810 after a hardware failure, the kernel config is in git.

---

## Machine Fleet

| Machine | Hardware | Status |
|---|---|---|
| **T5810** | Dell Precision, 2× RTX A4500 (NVLink), Xeon E5-2697 | Active — AI inference (vLLM), GPU workloads |
| **Surface Pro 6** | Intel 8th-gen, Gentoo built and running | Active — portable dev |
| **AMD build** | Custom, Ryzen 9 5950X (Zen 3), 16-core | Active — heavy compile workloads |
| **NUC 11** | Intel i5 NUC 11 | Profiled (kernel_config.sh documented); OS not installed |
| **Surface Pro 9** | Intel Core i7-1255U | Profiled; not built |

All running machines use Gentoo Linux with OpenRC (not systemd). Custom kernels compiled per-machine.

---

## Repository Structure

```
gentoo-machines/
├── machines/
│   ├── t5810/
│   │   ├── kernel_config.sh      # NVLink, PCIe Gen4, CUDA, GPU memory opts
│   │   ├── make.conf             # Gentoo build profile, CFLAGS, USE flags
│   │   └── notes.md              # Hardware quirks, what broke, what fixed it
│   ├── surface-pro-6/
│   │   ├── kernel_config.sh      # Touchscreen, wifi, battery, power mgmt
│   │   ├── make.conf
│   │   └── notes.md
│   ├── amd-build/
│   │   ├── kernel_config.sh      # Ryzen 9 5950X Zen3 opts, high-core compile
│   │   ├── make.conf
│   │   └── notes.md
│   └── nuc11/
│       ├── kernel_config.sh      # Profiled; power efficiency, compact (OS not installed)
│       └── notes.md
└── tools/
    ├── update-system.sh          # Coordinated emerge updates across the fleet
    └── ...                       # Hardware discovery, kernel validation, backup
```

---

## kernel_config.sh Design

Each `kernel_config.sh` is a shell script that documents kernel options with **explanations**, not just values. The comment answers "why is this option set?" rather than repeating what the option does.

Example pattern (T5810):
```bash
# NVIDIA NVLink — required for tensor-parallel vLLM across both A4500s
# Without this, CUDA sees two isolated GPUs, not a NVLink pair
CONFIG_DRM_NOUVEAU=n         # Disable nouveau; use proprietary nvidia driver
CONFIG_MODULES=y              # Modules required for nvidia.ko loading
```

This prevents cargo-cult configuration: future me (or anyone else reading the repo) knows *why* each option exists and can make informed decisions when kernel versions change or hardware gets replaced.

---

## T5810 Kernel Config — Notable Choices

The T5810 is the most complex machine in the fleet due to the AI inference workload:

- **NVLink enabled:** Allows the two A4500s to share memory and operate as a single tensor-parallel unit (required for vLLM TP=2)
- **Nouveau disabled:** Proprietary NVIDIA driver handles NVLink; nouveau doesn't support it
- **IOMMU enabled:** For clean GPU memory isolation
- **CUDA device support:** `nvidia.ko` loads at boot for immediate GPU availability
- **Memory overcommit tuned:** For large model weights (13.94 GiB per GPU)
- **OpenRC init:** Not systemd — Gentoo's OpenRC gives precise control over service start order (vLLM must start after CUDA module load and after network is up for SSH tunnel)

---

## tools/update-system.sh

Coordinated update script for running `emerge --update @world` across machines with:
- Dependency pre-resolution (checks before committing)
- Kernel recompile + automated smoke test after kernel updates
- Service restart orchestration with health checks
- Rollback procedure (previous kernel preserved in `/boot/`)
- Audit log of every update run (used for compliance reference)

The script is conservative: it would rather abort and ask than attempt to resolve a USE flag conflict silently.

---

## Surface Pro 6 Kernel Notes

The Surface requires several out-of-tree patches and non-obvious options:
- `SURFACE_AGGREGATOR`: The Surface Aggregator Module is required for battery, keyboard, and many hardware features — not mainlined in all kernels
- **WiFi driver**: Intel wireless card requires specific firmware; easy to miss during kernel compilation
- **Suspend/resume**: S3 sleep has quirks on Surface hardware; workaround committed to notes.md
- Surface Pro 9 was profiled (hardware documented, kernel_config.sh written) but Gentoo was not installed on it

The Surface is a good example of why per-machine kernel configs matter: a generic kernel that works fine on server hardware will fail silently on Surface (WiFi appears to work until first suspend cycle, then dies).

---

## Philosophy

**Hardware-aware, not one-size-fits-all.** The same USE flag that speeds up the T5810's compilation (multithreaded GPU work) wastes memory on the NUC8i7 (passive cooling, lower TDP). The configs reflect the actual use case of each machine, not a shared template.

**Documentation through code.** Comments in kernel_config.sh answer why, not what. "CONFIG_DRM_NOUVEAU=n" is self-documenting; "*# Required for NVLink tensor parallelism — nouveau doesn't support NVLink SLI*" is what you actually need after a year away from the config.

**Version control as memory.** Every kernel change is committed. When something breaks, `git bisect` on kernel configs is surprisingly effective.

---

## Related

- **T5810 homelab:** See `homelab_t5810.md` for the full AI inference stack running on this hardware
- **vLLM service config:** GPU_UTIL=0.93 required for vLLM v0.14.0 KV cache with 16K context; ENFORCE_EAGER=1 (CUDA graphs OOM even at 0.93)
- **OpenRC service files:** `/etc/init.d/vllm-qwen` and `/etc/init.d/qdrant` live in gentoo-machines repo under `machines/t5810/services/`
