# Linux System Administration Background

**Role:** Chris Wetzel — this is my own hands-on Linux systems-administration background.

## Overview

26 years of hands-on Linux systems administration across enterprise and personal production infrastructure — kernel-level customization, multi-machine configuration management, large-scale migrations, and distributed-systems operations. The through-line is **hardware-aware, declarative, automated infrastructure**: understand the hardware, tune the OS specifically for it, and make the whole thing reproducible from version control.

---

## Flagship: gentoo-machines — a declarative automation framework

Designed, engineered, and maintain **gentoo-machines**, an open-source automation framework and repository built to eliminate trial-and-error from classic Gentoo Linux deployments. It's a custom programmatic ecosystem that auto-generates everything a bare-metal Gentoo build needs from a machine's actual hardware:

- **Automated hardware-harvesting scripts** that profile each machine's real hardware.
- A **19,000-symbol static kernel-config validator (`kconfig-lint.sh`)** that catches invalid or missing kernel options *before* a build, not after a failed one.
- Auto-generation of **tuned kernel configs, Portage build parameters, and 3-phase bare-metal installation scripts** from that hardware profile.
- A **state-saving 10-phase system-upgrade orchestration tool (`update-system.sh`)** that safely automates Portage syncs, configuration merging, and proprietary NVIDIA module rebuilds — with automated rollback when something breaks.

The framework is **declarative**: each machine's hardware and the rationale for every non-obvious choice live in version control, so a build is reproducible rather than improvised. It is deployed, cross-compiled, and maintained across a **diverse bare-metal production fleet** running modern LTS kernels:

- **Multi-GPU AI/ML compute bench** — Dell Precision T5810, dual RTX A4500 (NVLink), serving vLLM inference
- **AMD Ryzen workstation** — ASRock B550 / Ryzen 9 5950X (Zen 3), heavy parallel compile (also hosts the portfolio chat's faithfulness verifier)
- **Hybrid-GPU laptop** — Dell XPS 15 9510 (Intel iGPU + NVIDIA, PRIME offload)
- **Resource-constrained mini-PCs** — e.g. Beelink MINI S (Jasper Lake, no AVX/AVX2)
- plus additional profiled machines

Cross-compilation is part of the design: kernels are built on the high-core-count machines (T5810 / B550) and deployed to constrained ones where native compilation would be too slow.

*(For the technical deep-dive — the scripts, per-machine configs, and lint rules — see `gentoo_machines.md`.)*

---

## Core Competencies

### Distribution Expertise
- **Gentoo Linux** — primary OS for personal infrastructure: stage3 builds, custom per-hardware kernel compilation, Portage, OpenRC, performance tuning (the gentoo-machines framework above).
- **RHEL / CentOS / Fedora** — enterprise environments: RPM, SELinux policy, systemd.
- **Ubuntu / Debian** — cloud and dev infrastructure (the portfolio chat's public VPS runs Ubuntu): APT, systemd.

### Kernel Configuration & Optimization
Per-hardware kernel tuning, with each machine's `kernel_config.sh` documenting *why* options are set (no cargo-cult configuration):
- **T5810** (dual A4500): NVLink, PCIe, CUDA, GPU memory, tensor-parallel vLLM.
- **Ryzen 9 5950X**: Zen 3 (`-march=znver3`) tuning for high-core-count compile.
- **XPS 15 9510**: hybrid-GPU (PRIME), Tiger Lake power management, a local `intel_idle` patch.
- **Mini-PCs**: Jasper Lake / Tremont (no AVX/AVX2), power efficiency.

### Automation & Reproducibility
- The gentoo-machines `tools/` ecosystem: hardware discovery, kernel-config validation/generation, the 10-phase `update-system.sh`, health monitoring.
- Designed for portability across machines with varying configurations.
- **Python** and **SQL** for data processing, migration validation, and reporting.
- Infrastructure-as-code in **Git** — every kernel change committed with its rationale.

### Security & Compliance
- SELinux policy for sensitive workloads; LUKS disk encryption; SSH key-based hardening; multi-zone firewalling.
- SOC 2 Type II compliance operations (see the SOC 2 case study).

---

## Infrastructure Philosophy

1. **Hardware-aware configuration** — tune the OS to the actual hardware, not a generic profile.
2. **Documentation through code** — scripts and configs explain *why*, not just *what*.
3. **Automated validation** — catch errors (e.g. kernel config) before deployment, fleet-wide.
4. **Cross-architecture thinking** — tuning principles transfer across Intel, AMD, and specialized systems.
5. **Local-first and reproducible** — keep critical infrastructure under your own control, and make it rebuildable from version control.

---

## Related Linux-Heavy Projects

Hands-on Linux is the backbone of several documented projects (each has its own case study):

- **Graphic-design-studio virtualization migration** — bare-metal macOS X Server → Dell PowerEdge + EqualLogic SAN + VMware vSphere (Windows / Ubuntu VMs).
- **SMB BCDR rollouts** — standardized single-host VMware ESXi + dedicated BCDR appliances with hybrid-cloud failover.
- **SAP Business One global deployment**, **Azure Virtual Desktop migration**, **Microsoft 365 email migrations**, and **SOC 2 Type II** compliance.
