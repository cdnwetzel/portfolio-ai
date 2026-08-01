# gentoo-machines — Multi-Machine Gentoo Configuration Repo

## What It Is

`gentoo-machines` is my personal infrastructure-as-code repository for managing a fleet of Gentoo Linux machines. Every machine has a dedicated directory with hardware-specific kernel configuration, build profile, and documented reasoning for every non-obvious choice.

**Repo:** https://github.com/cdnwetzel/gentoo-machines  
*(Private — contains hardware-specific config)*

---

## The Problem It Solves

Gentoo's power is also its problem: every machine can be configured perfectly for its hardware, but "perfectly configured" is easy to lose track of across a fleet. `gentoo-machines` is the answer — a version-controlled record of what's running, why, and how to reproduce it from a blank disk.

Machines don't drift silently because changes are committed. If I rebuild the T5810 after a hardware failure, the kernel config, Portage profile, and install procedure are all in git.

---

## Machine Fleet

| Machine | Hardware | Status |
|---|---|---|
| **T5810** | Dell Precision, 2× RTX A4500 (NVLink), Xeon E5-2699v4 (22C/44T) | Active — AI inference (vLLM), primary GPU server |
| **OptiPlex 3090 SFF** | Dell OptiPlex 3090 SFF, RTX A1000 (8GB) | Active — secondary GPU workstation |
| **ASRock B550** (AMD build) | Ryzen 9 5950X (Zen 3, 16C/32T), 64GB DDR4-3200, RTX 5060 Ti 16GB, Intel AX200 WiFi, I225-V 2.5GbE | Active — heavy compile and parallel workloads; also hosts the portfolio chat's out-of-band faithfulness verifier (Qwen2.5-14B on GPU via Ollama, port 8007), reached from the VPS through the T5810 tunnel |
| **Dell XPS 15 9510** | Intel Core i7-11800H (Tiger Lake H), NVIDIA RTX 3050 Ti (Optimus/PRIME) | Active — dev laptop, hybrid GPU |
| **Beelink MINI S** | Intel Jasper Lake / Tremont, no AVX/AVX2 | Active — always-on low-power tasks |
| **Surface Pro 6** | Intel 8th-gen, Marvell 88W8897 WiFi, 2736×1824 PixelSense | Active — portable dev, HiDPI setup |
| **MacBook Pro 12,1** | Intel Broadwell, BCM43602 WiFi, Cirrus CS4208 audio | Retired to macOS — full Gentoo configs maintained as reference |
| **NUC 11** | Intel i5 NUC 11 | Profiled; OS not installed |
| **Surface Pro 9** | Intel Core i7-1255U | Profiled; not built |
| **Dell Precision 7960** | Xeon W5-3433 (Sapphire Rapids), RTX Pro 6000 Blackwell (96GB) + RTX 5080 Blackwell, 128GB DDR5 ECC | Reference/profiled — highest-spec hardware harvested for config |

All running machines use Gentoo Linux with OpenRC (not systemd). Target kernel: 6.18 LTS series.

**Why OpenRC over systemd:** it's a deliberate choice, not dogma. OpenRC's dependency-based init is small, transparent, and shell-scriptable — easy to read the exact start/stop logic for a GPU inference service, tune startup ordering (e.g. NVLink precondition checks before vLLM starts), and debug without a binary journal. On single-purpose, hand-tuned machines like these, that transparency and minimalism is worth more than systemd's feature breadth. systemd is a fine default for fleets that need its ecosystem; for this homelab, OpenRC keeps the stack legible and lightweight. (The cloud VPS, by contrast, runs Ubuntu + systemd — the right tool there.)

---

## Repository Structure

```
gentoo-machines/
├── machines/
│   ├── t5810/
│   │   ├── kernel_config.sh      # NVLink NV4, PCIe, CUDA, GPU memory
│   │   ├── make.conf             # Gentoo build profile, CFLAGS, USE flags
│   │   ├── services/             # OpenRC init files (vllm-qwen, qdrant)
│   │   └── notes.md
│   ├── optiplex-3090-sff/
│   │   ├── kernel_config.sh      # RTX A1000, BIOS AHCI mode required
│   │   ├── make.conf
│   │   └── notes.md
│   ├── amd-build/                # ASRock B550, Ryzen 9 5950X
│   │   ├── kernel_config.sh      # znver3, amd-pstate, k10temp, AMD IOMMU
│   │   ├── make.conf             # -march=znver3, -j32
│   │   └── notes.md
│   ├── dell-xps-15-9510/
│   │   ├── kernel_config.sh      # Tiger Lake, PRIME render offload
│   │   ├── make.conf
│   │   └── notes.md
│   ├── beelink-mini-s/
│   │   ├── kernel_config.sh      # Tremont, no AVX, suspend fully disabled
│   │   ├── make.conf             # -march=tremont
│   │   └── notes.md
│   ├── surface-pro-6/
│   │   ├── kernel_config.sh      # SURFACE_AGGREGATOR, mwifiex_pcie, iptsd
│   │   ├── make.conf
│   │   └── notes.md
│   └── ...
├── shared/
│   ├── package.use               # Common USE flags across fleet
│   ├── package.accept_keywords   # Common ~amd64 accepts
│   ├── portage-env/              # low-memory.conf for constrained machines
│   └── world                    # Shared package set (desktop + toolchain)
└── tools/
    ├── harvest.sh
    ├── deep_harvest.sh
    ├── machine-profile.sh
    ├── kernel-config-template.sh
    ├── generate-config.sh
    ├── generate-install.sh
    ├── verify-install.sh
    ├── build-kernel-remote.sh
    ├── update-system.sh
    ├── kconfig-lint.sh
    └── test-generate-install.sh
```

---

## Tools Directory — Fleet Automation Pipeline

The `tools/` directory is where most of the engineering effort lives. The tools form a pipeline from bare hardware to running Gentoo install:

### Discovery Phase

**`harvest.sh`** — Hardware discovery across 15 categories (PCI devices, USB, ACPI tables, CPU features, memory config, storage layout, network interfaces, display, GPU, audio). Emits structured output used by every downstream tool.

**`deep_harvest.sh`** — Deeper companion to harvest.sh. Captures: loaded module database (modprobed-db), I2C device enumeration, actual firmware filenames from dmesg, NVIDIA driver/CUDA version, and input device topology. Used for subtle hardware-specific kernel options that basic PCI enumeration misses.

**`machine-profile.sh`** — Shared library that parses harvest output and sets 30+ structured feature flags: `CPU_VENDOR`, `HAS_INTEL_GPU`, `INTEL_GPU_GEN`, `WIFI_DRIVER`, `AUDIO_TYPE` (SOF vs HDA), `IS_LAPTOP`, `HAS_TB` (Thunderbolt), `HAS_ISH`, `SUSPEND_S3`, `CHASSIS_TYPE`, and more. All downstream generators consume these flags rather than re-parsing hardware data.

### Generation Phase

**`kernel-config-template.sh`** — Auto-generates a starting `kernel_config.sh` from harvest/profile output. Emits a 26-phase skeleton with correct options pre-filled and documented rationale stubs for human review. Runs `kconfig-lint.sh` automatically after generation to catch symbol errors before any human touches the file. Reduces time-to-correct-kernel from hours to under 30 minutes on new hardware.

**`generate-config.sh`** — Invokes the Claude CLI to analyze harvest data against a base machine config and generate three outputs: a complete `.config`, a tuned `make.conf`, and a `HARDWARE.md` summary. This is direct Claude-as-infrastructure-tool integration — AI analyzes hardware output and generates the Portage profile.

**`generate-install.sh`** — Creates three-phase automated Gentoo install scripts (bootstrap, base system, machine-specific) with machine-specific feature gates. Architecture is ~70% universal logic + ~30% machine-specific config. Phase 11 is the primary divergence point per machine. Scripts are idempotent and resumable. Turns a fresh disk into a running Gentoo install with correct kernel in ~2 hours.

**`test-generate-install.sh`** — Regression test harness for the generator with synthetic harvest fixtures (intel-sata-desktop, amd-nvme-nvidia-desktop, apple-broadwell-laptop). Uses assert_grep / assert_no_grep / assert_syntax helpers to verify feature gate behavior across machine archetypes.

### Validation Phase

**`kconfig-lint.sh`** — Static kernel config validator. Checks `kernel_config.sh` files for ~19,000 kernel symbols across 5 error classes (dangerous combinations, missing dependencies, conflicting options, invalid SOF hierarchy, driver/firmware pairing). Integrated into kernel-config-template.sh and generate-install.sh Phase 2 (chroot); can also run standalone before any compile.

**`verify-install.sh`** — Post-reboot deep verification across 8 sections (kernel, hardware detection, services, network, storage, GPU, audio, power). Auto-detects which machine it's running on via DMI and applies the machine-specific checklist. Exits with a structured pass/fail report.

### Maintenance

**`update-system.sh`** — Named subcommands: `fetch`, `world`, `config-update`, `check`, `prepare`, `build`, `install`, `verify`, `clean`. Cross-series kernel updates auto-detect and switch from oldconfig to full `kernel_config.sh` regeneration. Tracks temporary Portage workarounds in a `PORTAGE_WORKAROUNDS` registry. Old kernels kept at keep-current-plus-2 policy (`eclean-kernel -n 3`). Conservative: aborts on USE flag conflict rather than resolving silently.

**`build-kernel-remote.sh`** — Cross-compilation and SSH deploy. Builds a kernel on the T5810 or B550 (44T/32T respectively) and transfers to constrained machines (Beelink, NUC) where native compilation would take hours or exceed thermal limits.

---

## T5810 — Notable Kernel and Hardware Details

The T5810 is the most complex machine in the fleet due to the AI inference workload:

- **CPU:** Intel Xeon E5-2699v4 — 22 cores / 44 threads, Broadwell-EP. At `-j44`, kernel 6.18 builds in ~5 minutes; a full `@world` update (250 packages) with `--jobs=6 --load-average=44` takes ~90 minutes. Peak RAM during Node.js/V8 compile: ~48GB.
- **NVLink topology:** `nvidia-smi topo -m` reports `NV4` (4-link NVLink bridge) between the two A4500s — 56 GB/s per direction, 112 GB/s aggregate. Required for tensor-parallel vLLM (TP=2); without it CUDA sees two isolated GPUs.
- **GPU history:** Originally shipped with 2× GTX 1050 Ti (Pascal). Upgraded to 2× RTX A4500 + NVLink bridge specifically to get 40GB pooled VRAM for TP=2 inference — no single card without NVLink could match that capacity at a similar price point.
- **NVIDIA driver:** A4500 (Ampere) uses the current nvidia driver series. The T5810 also previously ran a GTX 1050 Ti (Pascal) — Pascal requires the 580.xx legacy branch (security patches through October 2028) because NVIDIA 590+ dropped Pascal/Maxwell/Volta entirely.
- **Portage tmpfs:** 46GB `PORTAGE_TMPDIR` on tmpfs with a `notmpfs.conf` `package.env` override for packages (chromium, LLVM, Rust, firefox-bin) that exceed that budget.
- **sysctl tuning:** `vm.swappiness=5`, `dirty_ratio=40`, `max_map_count=1048576`, `pid_max=131072`, `threads-max=524288` — tuned for large parallel builds and LLM inference memory patterns.

---

## ASRock B550 (AMD Build) — Notable Details

- Ryzen 9 5950X config: `-march=znver3`, `amd-pstate` governor, `k10temp` CPU monitoring, `ccp` (AMD Security Processor), `piix4_smbus`, AMD IOMMU — explicitly distinct from Intel configurations (no Intel MEI, no intel_pstate, no intel_idle).
- 64GB DDR4-3200: enough RAM that `PORTAGE_TMPDIR` tmpfs is set to 24GB without risk of eviction during most package builds.
- First AMD machine in the fleet; the B550 build demonstrated that Gentoo's `-march=znver3` tuning produces measurably faster binaries than generic x86-64 for compile-heavy workloads.

---

## XPS 15 9510 — Hybrid GPU (PRIME)

Tiger Lake-H with Intel UHD iGPU + NVIDIA RTX 3050 Ti (Optimus). Uses `prime-run` wrapper for PRIME Render Offload. Key kernel options: `i915.enable_guc=3` boot param, `nvidia.NVreg_DynamicPowerManagement=0x02`. A local kernel patch adds Tiger Lake CPU IDs to the `intel_idle` driver table — Dell's BIOS only exposes 3 C-states via ACPI instead of the 8 native SKL-family states; upstream intentionally omits client CPUs from `intel_idle` since Ice Lake, so the patch is local-only with rationale documented.

---

## Surface Pro 6 — Non-Obvious Requirements

The Surface Pro 6 required the most out-of-tree work of any machine in the fleet:

- **WiFi:** Marvell 88W8897 (`mwifiex_pcie`), not Intel. Requires pre-suspend module unload and post-resume reload + NetworkManager cycling to survive s2idle — managed by `wifi-recover.sh` and `wifi-reload.sh`.
- **Touchscreen:** `iptsd` daemon (Intel Precise Touch and Stylus) with custom udev rules and configuration. Plus `idle-hint-bridge.sh` to inhibit idle during touch input.
- **HiDPI:** 2736×1824 PixelSense display at 150% scaling requires GDK_SCALE, Xft.dpi, LightDM greeter scaling, xrandr-dpi.desktop autostart, and XFCE display profile. `restore-desktop.sh` auto-detects DMI product name and applies machine-specific HiDPI config.
- **SURFACE_AGGREGATOR:** Required for battery, keyboard, and most hardware features. `SURFACE_AGGREGATOR` → `SURFACE_AGGREGATOR_TABLET_SWITCH` → `SURFACE_AGGREGATOR_REGISTRY` → peripheral submodules — missing any one silently breaks hardware.

---

## OptiPlex 3090 SFF — BIOS Gotcha

Ships with SATA controller in Intel RST/RAID mode by default. Linux cannot see the NVMe drive until the BIOS is switched to AHCI mode — there's no OS-level workaround. Documented in notes.md as step 0 before any install attempt.

---

## Beelink MINI S — Always-On Design

Jasper Lake / Tremont architecture: no HT, no AVX, no AVX2. `CPU_FLAGS_X86` and `-march=tremont` are genuinely distinct from every other Intel machine in the fleet. elogind drop-in fully disables all sleep/suspend targets — this machine is the always-on mini PC and must never auto-suspend.

---

## MacBook Pro 12,1 (Retired)

Full Gentoo support was built and maintained: `applesmc` (35 sensors), `mbpfan` fan control, `bcm5974` Force Touch trackpad, `hid_apple fnmode`, `brcmfmac` BCM43602 WiFi, Cirrus CS4208 audio with `model=mbp11` quirk, Thunderbolt 2 (Falcon Ridge), keyboard backlight via SMC. Now retired to macOS as a secondary machine, but the configs are maintained as a reference for Apple hardware Gentoo patterns.

---

## Portage Engineering

**Tmpfs strategy:** Each machine has a tuned `PORTAGE_TMPDIR` tmpfs sized to available RAM: 4GB (Surface Pro 6, Beelink), 24GB (XPS 9510), 46GB (B550, T5810). A `notmpfs.conf` `package.env` override sends oversized packages (chromium, LLVM, Rust, firefox-bin) to disk. Portage silently appends `/portage/` to `PORTAGE_TMPDIR`, so the mount path must account for that.

**ccache:** Configured as a Portage build accelerator at `/var/cache/ccache/` owned by `root:portage` (mode 2775). Known pitfall: `/tmp/` subdirectory at 2755 (not group-writable) causes all `nvidia-drivers` builds to fail silently in the Portage sandbox.

**package.use ordering:** When the same package appears in multiple files under `/etc/portage/package.use/`, Portage processes them alphabetically and the last file wins. A bug where `shared/` file (alphabetically after `precision-t5810`) overrode a machine-specific `-kernel-open` flag was caught by `kconfig-lint.sh`. Now machine-specific files are named with `zzz-` prefix to ensure they win.

**MAKEOPTS gotcha:** Portage does NOT evaluate shell commands in `make.conf`. `MAKEOPTS="-j$(nproc)"` causes "bad substitution" errors on every `econf`. Thread count must be hardcoded. (`nproc` expressions are fine in `kernel_config.sh` which runs as a bash script directly.)

**SOF audio detection:** `machine-profile.sh` sets `AUDIO_TYPE=sof|hda` and `SOF_CHIP` from CPU generation. `kernel-config-template.sh` emits the correct SOF hierarchy (`SND_SOC_SOF_TOPLEVEL` → Intel → PCI → chip) vs HDA path based on this. A bug where 3 invalid SOF symbols propagated to 6 machine configs was caught by `kconfig-lint.sh` and systematically fixed.

---

## No-Initramfs Design

All production machines build root-path drivers (NVMe/AHCI/SATA, ext4, VFAT) as built-in (`=y`) to avoid needing dracut/initramfs. Constraint: any driver that requires firmware from `/lib/firmware/` must be `=m` (module), not `=y`, because firmware can't load before root is mounted. This applies to `i915`, `mwifiex_pcie`, `brcmfmac`, and all wireless drivers across the fleet.

---

## Philosophy

**Hardware-aware, not one-size-fits-all.** The same `MAKEOPTS` that saturates the T5810's 44 threads would OOM-kill the Beelink on a large package. The configs reflect the actual use case of each machine.

**Documentation through code.** Comments answer why, not what. `CONFIG_DRM_NOUVEAU=n` is self-documenting; the comment explaining it's required because nouveau doesn't support NVLink SLI is what matters a year later.

**AI in the toolchain.** `generate-config.sh` invokes Claude CLI to synthesize hardware harvest data into kernel and Portage configuration. The pipeline uses AI where synthesis is hard (translating raw PCI IDs and ACPI tables into correct kernel symbol combinations) and keeps humans in the loop for review.

**Version control as memory.** Every kernel change is committed with rationale. `git bisect` on kernel configs is surprisingly effective when a previously-working machine starts misbehaving after an update.

---

## Related

- **T5810 homelab:** See `homelab_t5810.md` for the full AI inference stack
- **OpenRC service files:** `machines/t5810/services/` contains `vllm-qwen` and `qdrant` OpenRC init files
