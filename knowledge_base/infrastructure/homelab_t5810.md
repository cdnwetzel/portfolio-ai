# Home Lab: Dell Precision T5810 GPU Server

## Hardware

**Machine:** Dell Precision T5810 Workstation
**Location:** Home office, Trenton, NJ
**Connectivity:** 300 Mbps fiber (Comcast Business)

### GPU Configuration
- **2× NVIDIA RTX A4500** (20 GB GDDR6 each, 40 GB total)
- **NVLink bridge:** NV4 topology (4-link bridge) — 56 GB/s per direction, 112 GB/s aggregate. Required for tensor-parallel vLLM TP=2; without NVLink, CUDA sees two isolated GPUs
- **Usable VRAM:** ~19,190 MiB per card after ECC overhead
- **Power:** Dell 825W internal PSU (primary) + external Corsair ATX 3.0 1000W PSU via SATA sync/trigger board for GPU supplemental power

### CPU & Memory
- **CPU:** Intel Xeon E5-2699v4 — 22 cores / 44 threads, Broadwell-EP
- **Build performance:** kernel 6.18 at `-j44` in ~5 min; full `@world` (250 packages) in ~90 min; peak RAM during Node.js/V8 compile ~48GB
- **PCIe:** Gen 3 slots for dual-GPU installation

### Operating System
- **OS:** Gentoo Linux (custom compiled kernel)
- **Init:** OpenRC (not systemd)
- **Services:** managed via rc-service, rc-update, /etc/conf.d/ environment files

---

## AI Inference Stack

### vLLM (Primary LLM Serving)
- **Service name:** `pscode-vllm` (OpenRC)
- **Model:** `qwen2.5-coder-14b-instruct` (served as `qwen2.5-coder-14b-pscode`)
- **Port:** 8004 (LAN only — not exposed to internet)
- **Tensor Parallel:** Both A4500s in tensor-parallel mode (TENSOR_PARALLEL_SIZE=2)
- **Context window:** 16,384 tokens (PSCODE_MAX_MODEL_LEN=16384)
- **GPU utilization target:** 93% (PSCODE_GPU_UTIL=0.93; 0.90 too tight for vLLM v0.14.0 KV cache at 16K context; 0.95 OOM with CUDA graphs)
- **Enforce eager:** Enabled (PSCODE_ENFORCE_EAGER=1) — disabling would enable CUDA graphs for faster inference at cost of ~1 GB VRAM

### Qdrant Vector Database
- **Service name:** `qdrant` (OpenRC)
- **Port:** 6333 (LAN only)
- **Storage:** `/home/chris/qdrant-data/`
- **Collection:** `documents` — 768-dim cosine similarity vectors
- **Content:** ~65 chunks indexed from LinkedIn posts, case studies, resume, KB documents

### Embedding Service
- **Model:** `BAAI/bge-base-en-v1.5` (sentence-transformers)
- **Device:** CPU (keeps GPU free for LLM inference)
- **Port:** 8005 (LAN only)
- **Dimensions:** 768-dim vectors

---

## Cloud Architecture (T5810 ↔ cwetzel.com)

The T5810 is a home server with LAN-only services. It's made accessible to the internet via a persistent SSH tunnel from the cloud server:

```
User Browser → HTTPS → cwetzel.com (Ubuntu VPS)
  Cloud: Apache (SSL/WSS) + FastAPI api-proxy (port 8000)
    ↓ SSH Tunnel (reverse forward)
  T5810: vLLM (8004), Qdrant (6333), Embeddings (8005), Reranker (8006)
    ↓ tunnel also forwards :8007 → asrock (10.0.1.115) verifier
```

**Tunnel service:** `portfolio-ai-tunnel.service` (systemd on cloud server)
- Forwards cloud ports 8004, 6333, 8005, 8006 → T5810 LAN; 8007 → asrock
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
- Previously had two competing services (`vllm` 32B AWQ + `pscode-vllm` 14B) which caused OOM and GPU dirty-state crashes requiring physical PSU power cycle
- Resolution: disabled 32B service, kept only `pscode-vllm` in default runlevel
- LightDM (display manager) disabled headless — no GUI needed, saves ~200 MB VRAM

### PSU Configuration
External 1000W Corsair ATX 3.0 PSU powers supplemental GPU rails via a SATA sync board that triggers when the Dell's internal PSU powers on. This has been stable for months including with more power-hungry cards (RTX Pro 6000 Blackwell tested). The 2/7 amber blink POST issue was traced to dirty GPU state from software OOM, not PSU timing.

---

## Why I Built This

The T5810 serves as my personal AI inference platform: real GPU compute, real data, real infrastructure problems. The goal was to build something portfolio-worthy that demonstrates both the AI/ML side (vLLM, RAG, embeddings) and the infrastructure side (Gentoo kernel tuning, service management, SSH tunnel architecture, cloud-edge hybrid). Everything running here is production infrastructure, not a demo.

Monthly operating cost: ~$20 (cloud VPS) + electricity. Zero GPU cloud spend.
