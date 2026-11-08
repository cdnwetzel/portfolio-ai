# pxx v2.4.0 Release: A Local-First Alternative to Hosted AI Coding Agents

*LinkedIn post by Chris Wetzel, published 2026-08-07. https://www.linkedin.com/posts/chris-wetzel_aiengineering-opensource-enterpriseit-activity-7491475918889291776-Pm-A*

Every hosted AI coding agent has one requirement that never makes the pricing page: your source code ships to their cloud first.

I've spent months building the alternative in public. Today it's formally out: pxx v2.4.0, MIT licensed, live on PyPI.

The Problem Nobody Prices In
• Devin and its peers run your source on the vendor's infrastructure. That's not a settings toggle. It's the construction.
• If your environment is regulated, air-gapped, or IP-sensitive, the entire category is off the table before capabilities even come up.

→ That's not a feature gap a roadmap can close. It's the architecture.

What I Built Instead
• pxx is a local-first autonomous coding runtime. It plans, edits, runs your tests, reviews the diff, and stops.
• It runs on hardware you own: one modest box (about $1,200), fully air-gapped. Local models via Ollama or vLLM, or any endpoint you control.
• No vendor in the loop. No telemetry. No data egress.

→ The agent loop you already know, minus the step where your code leaves the building.

The Part Your Auditor Will Ask About
• Host-enforced gates the model cannot subvert, no matter what it generates.
• A hash-chained, tamper-evident audit log you can verify after every run.
• MIT licensed: yours to read, run, modify, fork, and own. Harden the enforcement to your own compliance regime.

→ No lock-in, and no bet on a vendor's roadmap or survival.

The Honest Lane
• pxx is not trying to out-code frontier agents at scale. It can't, and that's fine.
• When the binding constraint is capability, use the most capable agent you're allowed to. Those tools are excellent.
• When the constraint is sovereignty, auditability, or ownership, pxx is built for exactly that slice.

→ Different constraints, different tools. Each has its place.

The Bottom Line
Trying a hosted agent starts with sending your codebase to someone else's cloud. You can pilot pxx air-gapped this afternoon and read every line of the enforcement code while it runs.

Your Turn: What's actually keeping autonomous coding agents out of your environment: security review, data residency, procurement, or nobody has pushed for one yet?

♻️ Repost for the teams whose code can't leave the building
✅ Follow me, Chris Wetzel, for enterprise security from the field

#AIEngineering #OpenSource #EnterpriseIT #InfoSec #LocalFirst #BuildInPublic #KeepTheReceipts
