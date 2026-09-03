# Home Lab: Dell Precision T5810 GPU Server

## Hardware

**Machine:** Dell Precision T5810 Workstation
**Location:** Home office, Trenton, NJ
**Connectivity:** Verizon FIOS symmetric fiber (~386↓ / 439↑ Mbps measured)

### GPU Configuration
- **2× NVIDIA RTX A4500.**

  | | |
  |---|---|
  | VRAM per card | **20 GB** GDDR6 |
  | **Total VRAM across both cards** | **40 GB** |

  Those are the only two VRAM numbers for this machine: 20 GB on each card, 40 GB in
  total. VRAM is the GPUs' working memory for model weights and KV cache. It is not system
  RAM and not disk capacity — those are separate, and the machine has plenty of both (see
  CPU & Memory and Storage below).
- **Usable VRAM:** 20,470 MiB per card — the full ~20 GB is available because ECC is **disabled** (a deliberate trade-off that reclaims the ~1.25 GB/card ECC overhead — ~2.5 GB total across the pair — for vLLM's KV cache)
- **NVLink bridge:** NV4 topology (4-link bridge), required for tensor-parallel vLLM TP=2;
  without NVLink, CUDA sees two isolated GPUs. Its speed is **56 GB/s per direction
  (112 GB/s aggregate)** — note the **per second**: that is a *transfer rate between the
  two cards*, and it is not a quantity of memory. The VRAM figures are the 20 GB / 40 GB
  above.
- **GPU power cap: 165 W per card** (of a 200 W rating), applied at boot by
  `/usr/local/bin/gpu-tune.sh`. The SM clock is unrestricted to its 2100 MHz maximum. This is
  a deliberate tuning choice, not a limit: measured 33.4 tok/s at 71 °C versus 34.2 at 79 °C
  for the full 200 W, i.e. 97.7 % of the throughput for an 8 °C thermal margin. (Repeated here
  as well as under GPU tuning below: a "what is the GPU power cap" question lands on this
  hardware section, and retrieval returns at most two chunks per document.)
- **Power supplies:** **two PSUs run at the same time.** The Dell 825 W internal PSU powers the
  workstation, and an external Corsair ATX 3.0 1000 W PSU supplies supplemental GPU rails via a
  SATA sync/trigger board that switches it on with the Dell. The Dell unit remains in place and
  in use; the Corsair is additional capacity, not a swap.

### CPU & Memory
- **CPU:** Intel Xeon E5-2699v4 — 22 cores / 44 threads, Broadwell-EP
- **Memory:** 256 GB DDR4 ECC (total system RAM) — ample headroom to run the CPU embedder, and Qdrant alongside vLLM with no GPU-VRAM contention
- **Build performance:** kernel 6.18 at `-j44` in ~5 min; full `@world` (250 packages) in ~90 min; peak RAM during Node.js/V8 compile ~48GB (a workload spike, not the machine's total)
- **PCIe:** Gen 3 slots for dual-GPU installation

### Storage
- **Yes, the T5810 has onboard storage** — internal drives inside the workstation chassis,
  like any normal workstation. They hold the Gentoo root filesystem, the Qwen3.8-27B-FP8
  model weights (~29 GB) that vLLM loads at startup, and the Qdrant collection.
- The machine boots and runs entirely from its own internal drives. Exact drive capacities
  are not documented here; the correct answer to "how much disk does it have?" is that the
  capacity isn't recorded, **not** that the machine lacks storage.

### Operating System
- **OS:** Gentoo Linux (custom compiled kernel) — the home server runs **Gentoo**, not Ubuntu
- **Init:** OpenRC (**not** systemd)
- **Services:** managed via rc-service, rc-update, /etc/conf.d/ environment files
- **Do not confuse the two servers:** the **home server (T5810)** runs **Gentoo Linux + OpenRC**;
  the separate **cloud VPS** (`cwetzel.com`) runs **Ubuntu + systemd**. The asrock B550 verifier
  box also runs Gentoo/OpenRC. Only the public cloud VPS is Ubuntu/systemd.

---

## Two Distinct GPU Machines — Do Not Conflate

The GPU home lab is **two separate machines with different hardware**:

- **T5810** (primary AI server): Dell Precision, **Xeon E5-2699v4 (22C/44T)**, **two RTX A4500
  GPUs joined by an NVLink bridge**. Runs vLLM inference serving **Qwen3.8-27B-FP8** with
  tensor parallelism across both cards.
- **asrock B550** (verifier node): **AMD Ryzen 9 5950X (16C/32T), 64 GB**, **a single RTX 5060
  Ti (16 GB)**. Runs the out-of-band faithfulness verifier.

The **A4500 NVLink pair belongs to the T5810**; the **single 5060 Ti belongs to the asrock B550**.
They are not the same box, and their CPUs differ (Intel Xeon vs AMD Ryzen 9). Never attribute one
machine's GPU or CPU to the other.

### asrock B550 — verifier + reranker node
It runs **two different things, and they are constantly confused with each other.** They are not
the same model, not the same size, and not the same job:

| | Reranker | Faithfulness judge |
|---|---|---|
| Model | **`bge-reranker-base`** — a small cross-encoder, a few hundred MB | **Qwen2.5-14B-Instruct** — a 14-billion-parameter LLM |
| Port | 8006 | 8007 |
| Job | scores retrieved chunks for relevance, picks the best 5 of 15 | reads a finished answer and scores whether each claim is supported |
| When | *before* the answer is written | *after* the answer is written |

**The reranker is `bge-reranker-base`.** It is a small cross-encoder, roughly 1.3 GB of VRAM.
**The judge is Qwen2.5-14B-Instruct**, and it is the reason the 5060 Ti needs 16 GB — the judge
holds about 11.7 GB. Two separate models, two separate ports, two separate jobs.

- **OS:** Gentoo Linux / OpenRC
- **Role:** runs two independent services on its RTX 5060 Ti:
  - `rerank-service` (port 8006) running **`bge-reranker-base`** — a small cross-encoder,
    about 1.3 GB of VRAM. It ranks retrieved chunks. It is not a large language model.
  - `verifier-service` (port 8007) running **Qwen2.5-14B-Instruct** via Ollama as an
    *independent* faithfulness judge — about 11.7 GB of VRAM, and a different model family
    from the one that writes answers, to avoid self-grading bias. The 14B parameter count
    belongs to this judge.
  The judge runs on the **RTX 5060 Ti** (GPU). After every answer, the
  cloud proxy fire-and-forgets the answer + its retrieved chunks here; the judge scores whether
  each claim is supported. Fail-open: if this box is down, the chat is unaffected.
- **Reachability:** reached from the cloud VPS through the *same* SSH tunnel that terminates on
  the T5810 — the T5810 routes port 8007 to the asrock box over the home LAN.

So generation runs on the **T5810 (Xeon + A4500 pair)** and continuous grounding-verification runs
on the **asrock B550 (Ryzen 9 + RTX 5060 Ti)** — two distinct GPU boxes, one home lab.

---

## AI Inference Stack

### vLLM (Primary LLM Serving) — current as of 2026-09-01
- **Service name:** `vllm-qwen38` (OpenRC, supervised). The older `pscode-vllm` unit is retired.
- **Model:** **Qwen3.8-27B-FP8**, served as `qwen3.8-27b`
- **vLLM version:** 0.27.1
- **Port:** 8007 — a *backend slot*, not the port callers use. See labrouter below.
- **Tensor Parallel:** both A4500s, TP=2 over the NVLink bridge
- **Context window:** **32,768 tokens**
- **GPU memory utilization:** 0.93 (0.95 OOMs on this box)
- **CUDA graphs:** **ENABLED** — this is the single biggest performance decision on the box.
  See "GPU tuning" below. An older revision of this page said `enforce_eager=1`; that was the
  previous 14B configuration and is no longer true.

### labrouter — the stable contract port
- **Port:** 8004, and this is what the cloud VPS tunnel forwards for generation.
- **Why it exists:** models are swapped *behind* labrouter, so changing which model serves the
  site never requires touching the cloud server. Backend slots sit on 8007 (Qwen3.8-27B-FP8),
  8008 and 8009. Nothing binds a model directly on 8004.

### GPU tuning — where the throughput comes from
Measured on this hardware, not inherited defaults:
- **~33 tokens/sec** generation on the 27B, single stream. The same box ran ~6 tok/s before
  tuning — a **~4.4x** improvement that came from CUDA graphs, not from new hardware.
- Three settings produce it and must survive together: CUDA graphs on (no `--enforce-eager`),
  `--disable-custom-all-reduce` (custom all-reduce *breaks* graph capture on this A4500 NVLink
  pair), and a **capped** set of captured batch sizes (`[1,2,4,8]` — vLLM captures ~70 by
  default and capture memory scales with the count, which caused OOM at every utilization
  setting until it was capped).
- **Power cap: 165 W per card** (default is 200 W), set at boot. Measured trade-off:
  130 W → 29.4 tok/s, 150 W → 32.6, **165 W → 33.4 at 71 °C**, 200 W → 34.2 at 79 °C. 165 W
  keeps 97.7% of the throughput with an 8 °C thermal margin instead of 1 °C. It replaced an
  older *crypto-mining* efficiency profile that was power-starving the cards.
- **Power draw:** ~28 W total at idle with the model resident; **~330 W total under load**
  (both cards at the cap). Whole machine is roughly 150 W idle / 520 W under inference.

### Qdrant Vector Database
- **Service name:** `qdrant` (OpenRC)
- **Port:** 6333 (LAN only)
- **Storage:** `/home/chris/qdrant-data/`
- **Collection:** `documents` — 768-dim cosine similarity vectors
- **Content:** ~100 chunks indexed from case studies, resume, infrastructure notes and posts

### Embedding Service
- **Model:** `BAAI/bge-base-en-v1.5` (sentence-transformers)
- **Device:** CPU (keeps GPU free for LLM inference)
- **Port:** 8005 (LAN only)
- **Dimensions:** 768-dim vectors

---

## Cloud Architecture (T5810 ↔ cwetzel.com)

The T5810 is a home server with LAN-only services. The home internet uplink is **Verizon FIOS**
symmetric fiber (measured ~386↓ / 439↑ Mbps on a local NJ node) — the high, symmetric upload is
what makes hosting inference from home practical, comfortably carrying the SSH-tunnelled traffic.
The T5810 is made accessible to the internet via a persistent SSH tunnel from the cloud server:

```
User Browser → HTTPS → cwetzel.com (Ubuntu VPS)
  Cloud: Apache (SSL/WSS) + FastAPI api-proxy (port 8000)
    ↓ SSH Tunnel (reverse forward)
  T5810: labrouter (8004) -> vLLM backends, Qdrant (6333), Embeddings (8005)
    ↓ tunnel also forwards :8007 → asrock verifier (home LAN)
```

**Tunnel service:** `portfolio-ai-tunnel.service` (systemd on cloud server)
- Forwards cloud ports 8004, 6333, 8005 → T5810; 8016 → asrock:8006 (reranker); 8007 → asrock (judge)
- Auto-restarts on disconnect

**Cloud server** (`cwetzel.com`, Ubuntu):
- Apache (SSL termination, static serving, WSS reverse proxy)
- FastAPI `api-proxy.py` (port 8000)
- Handles WebSocket connections, RAG pipeline, FOLLOWUPS injection

---

## Operational Notes

### Why Gentoo?
Gentoo allows full kernel customization for the T5810 hardware: NVLink driver support, PCIe power management tuning, CUDA driver integration, and system-wide USE flags for minimal overhead. Each machine in my fleet has a dedicated `kernel_config.sh` documenting why specific options are set.

### GPU Service Stability
- Only one vLLM service can run at a time (both GPUs needed per instance)
- Previously had two competing vLLM services, which caused OOM and GPU dirty-state crashes
  requiring a physical PSU power cycle. Resolution: exactly one vLLM backend runs at a time.
- Every service on the critical path is supervised with **unlimited respawn** and writes a log.
  A bounded respawn cap does not fail gracefully — it latches a service OFF permanently after a
  transient problem, which is how several outages here started.
- LightDM (display manager) disabled headless — no GUI needed, saves ~200 MB VRAM

### PSU Configuration
External 1000W Corsair ATX 3.0 PSU powers supplemental GPU rails via a SATA sync board that triggers when the Dell's internal PSU powers on. This has been stable for months including with more power-hungry cards (RTX Pro 6000 Blackwell tested). The 2/7 amber blink POST issue was traced to dirty GPU state from software OOM, not PSU timing.

---

## Why I Built This

The T5810 serves as my personal AI inference platform: real GPU compute, real data, real infrastructure problems. The goal was to build something portfolio-worthy that demonstrates both the AI/ML side (vLLM, RAG, embeddings) and the infrastructure side (Gentoo kernel tuning, service management, SSH tunnel architecture, cloud-edge hybrid). Everything running here is production infrastructure, not a demo.

Monthly operating cost: ~$20 (cloud VPS) + electricity. Zero GPU cloud spend.
