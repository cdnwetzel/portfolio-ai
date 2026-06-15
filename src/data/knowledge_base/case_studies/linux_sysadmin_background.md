# Linux System Administration Background

## Overview
My Linux system administration experience spans 26+ years managing production infrastructure across enterprise environments. This background encompasses kernel-level customization, multi-machine configuration management, large-scale migrations, and distributed systems operations.

## Core Competencies

### Linux Distribution Expertise
- **Gentoo Linux**: Primary OS for personal infrastructure. Deep expertise in stage3 builds, custom kernel compilation for specific hardware, portage package management, and performance optimization.
- **RHEL/CentOS/Fedora**: Managed in enterprise environments with RPM package management, SELinux policies, and systemd service architecture.
- **Ubuntu/Debian**: Deployed in cloud environments and development infrastructure. APT package management and Upstart/systemd configuration.
- **Custom build environments**: Built and maintained custom Gentoo Linux configurations for specific hardware deployments (T5810 GPU server, ASRock B550 / Ryzen 9 5950X, Dell XPS 15 9510, Beelink MINI S, Surface Pro 6). NUC 11 and Surface Pro 9 profiled; OS not installed on those.

### Kernel Configuration & Optimization
Configured Linux kernels across multiple hardware architectures:
- **Precision T5810** (dual RTX A4500 GPUs): NVLink, PCIe Gen4, CUDA device support, GPU memory management, tensor parallelism for vLLM inference.
- **Surface Pro 6** (Intel): Power management, touchscreen, wifi drivers, battery optimization for portable workloads. (Surface Pro 9 profiled but not built.)
- **Custom AMD build** (Ryzen 9 5950X): Zen 3 architecture optimizations, high-core-count compile workloads.
- **NUC 11** (Intel i5): Compact system optimization, power efficiency. (Profiled; OS not installed.)

Each machine maintains a tailored `kernel_config.sh` explaining *why* specific options are set for that hardware. This prevents cargo-cult configuration and documents the relationship between hardware capabilities and kernel options.

### Multi-Machine Management at Scale
Managed 50+ machines across multiple continents using a framework where each machine has:
- Dedicated directory under `machines/{machine-name}/` containing:
  - `kernel_config.sh` (kernel options + explanations)
  - `make.conf` (Gentoo build profile)
  - Hardware inventory and compatibility notes
  - Machine-specific patches and workarounds
  
This structure enables:
- Rapid OS deployment on new hardware (stage3 + custom kernel in <2 hours)
- Kernel updates across the fleet with hardware-aware patches
- Documentation of what works for each system and why

### System Updates & Maintenance
Developed and maintained `tools/update-system.sh` for coordinated system updates across multiple machines:
- Handles Gentoo emerge updates with dependency resolution
- Kernel recompilation and automated testing
- Service restart orchestration with zero-downtime where possible
- Rollback procedures when updates break critical functionality
- Audit logging for compliance tracking

### Infrastructure Migrations & Consolidation
Led 50+ server migrations including:
- **VMware P2V Infrastructure Redesign**: Consolidated 50+ physical servers into virtual infrastructure, achieving 60% hardware cost reduction and 63% operational expense reduction
- **SAP Business One Integration**: Coordinated deployment across 5 warehouses spanning 4 continents (North America, Europe, Asia, Oceania) with multi-region failover
- **AVD Migration**: Migrated 120+ on-premises VDI users to Azure Virtual Desktop across 3 continents with <2% downtime

### Disaster Recovery & High Availability
Implemented disaster recovery planning with proven metrics:
- RTO (Recovery Time Objective): <4 hours for critical systems
- RPO (Recovery Point Objective): <1 hour for database systems
- Cross-region failover tested quarterly with documented runbooks
- Automated backup verification and restore testing

### Automation & Scripting
Created custom shell scripts for infrastructure automation:
- `tools/` directory contains well-commented scripts for:
  - System updates (`update-system.sh`)
  - Kernel configuration validation and generation
  - Hardware discovery and inventory
  - Service health monitoring and alerting
  - Backup orchestration and verification
- All scripts designed for portability across Gentoo machines with varying configurations
- Python scripting for data processing, migration validation, and reporting

### Compliance & Security
Implemented:
- **SOC2 Type II compliance** across infrastructure operations
- SELinux policy configuration for sensitive workloads
- Disk encryption strategies (LUKS for sensitive data)
- SSH hardening with key-based authentication
- Firewall rules and iptables configuration for multi-zone networks
- Regular security audits and vulnerability patching schedules

### Modern Infrastructure Tooling
Experience with:
- **Container orchestration**: Docker for application deployment, vLLM serving for LLM inference
- **Vector databases**: Qdrant for semantic search and RAG pipelines
- **Monitoring**: Custom health check scripts (systemd/OpenRC integration)
- **Backup systems**: Automated backup validation and restore procedures
- **Version control**: Git for infrastructure-as-code and configuration management

## Infrastructure Philosophy

1. **Hardware-aware configuration**: Don't use one-size-fits-all configs. Understand the hardware and tune the OS specifically for it.
2. **Documentation through code**: Shell scripts and configs should explain *why* decisions were made, not just what they do.
3. **Automated testing**: Changes should be tested automatically before deployment across the fleet.
4. **Cross-architecture thinking**: Skills transfer between different hardware types — the principles of kernel tuning apply across Intel, AMD, ARM, and specialized systems.
5. **Local-first operations**: Keep critical infrastructure under your control when possible. Understand the layers from hardware to kernel to userspace.

## Projects Demonstrating Linux Sysadmin Expertise

### Gentoo Infrastructure (Ongoing)
Personal infrastructure running 5+ machines on Gentoo Linux with custom kernels for each architecture. Each machine independently maintained with documented configuration rationale. Serves as a continuous learning platform for kernel optimization, driver development, and system hardening.

### VMware P2V Migration
Consolidated 50+ physical servers to virtualized infrastructure, requiring:
- Detailed hardware inventory and capacity planning
- Custom Linux kernel tuning for VM guests
- Network re-architecture for consolidated infrastructure
- Application compatibility testing across migrations

### Multi-Region SAP Deployment
Coordinated Linux infrastructure for SAP Business One across 5 global warehouses:
- Network setup for multi-continent connectivity
- Database server configuration for high-availability replication
- Performance tuning for transaction processing workloads
- Compliance with data residency requirements per region

### Azure Virtual Desktop Migration
Managed infrastructure side of VDI migration for 120+ users:
- Hybrid cloud networking (on-premises to Azure)
- Linux-based infrastructure supporting Windows VDI environment
- Performance monitoring and optimization
- Cross-region failover for disaster recovery

---

*This document synthesizes experience from Gentoo infrastructure management, kernel configuration work across multiple hardware types, and enterprise-scale infrastructure projects. For specific projects, see related case studies.*
