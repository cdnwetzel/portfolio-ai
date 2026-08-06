# Why Gentoo

People ask why I run Gentoo in 2026 when every fleet tutorial assumes Ubuntu or RHEL.

Short answer: because my home infrastructure is single-purpose, hand-tuned hardware, and
Gentoo rewards exactly that. Every machine in my fleet compiles from source with a kernel
configuration built for its specific hardware — no generic driver bundle, no services I
didn't ask for. The T5810's kernel knows about its NVLink bridge and nothing else.

The deeper answer is about legibility. Gentoo's power is also its problem: every machine
can be configured perfectly, but "perfectly configured" is easy to lose track of. My answer
is the `gentoo-machines` repository — infrastructure-as-code for the whole fleet. Every
machine has a directory with its kernel config, build profile, and documented reasoning for
every non-obvious choice. If the T5810 dies tomorrow, I rebuild it from git, not from memory.

**Why OpenRC over systemd:** deliberate, not dogma. OpenRC's init is small, transparent,
and shell-scriptable — I can read the exact start/stop logic for a GPU inference service,
tune startup ordering (NVLink precondition checks before vLLM starts), and debug without a
binary journal. On single-purpose machines, that transparency beats systemd's feature
breadth. The cloud VPS runs Ubuntu + systemd — right tool there.

**The philosophy in one line:** comments answer *why*, not *what*. `CONFIG_DRM_NOUVEAU=n`
is self-documenting; the comment explaining *why* (nouveau doesn't support NVLink) is what
matters a year later.

It's not for every shop. It's for people who want to understand every layer of what they
run. That's the point.
