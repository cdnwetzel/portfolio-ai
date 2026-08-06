# Cloudflare Day 2: The Hardcoded Constant That Cost Millions (Nov 19 2025)

Cloudflare just published one of the best post-mortems I've read in years.

But buried in the technical details is a lesson every engineer needs to hear.

**The culprit? A hardcoded constant: 200**

Here's what happened:

Yesterday's 3-hour outage that took down 80% of the internet's CDN wasn't caused by a sophisticated attack or infrastructure failure.

It was caused by a Rust module with a hardcoded limit of 200 machine learning features.

When a database permissions change caused the Bot Management feature file to double in size, the code hit that limit and panicked.

→ No graceful degradation
→ No circuit breaker
→ No bounds checking
→ Just: `thread panicked: called Result::unwrap() on an Err value`

And suddenly, Cloudflare, Turnstile, Workers KV, and Cloudflare Access were returning 5xx errors globally.

**Why does this happen to the best engineering teams?**

Because every system has technical debt. Every codebase has that "we'll fix it later" hardcoded limit.

Cloudflare didn't lack talented engineers. They didn't lack monitoring. They didn't lack tests.

They had the same thing we all have: **edge cases that seemed safe until they weren't.**

**The real lesson:**

• Hardcoded limits are time bombs
• Graceful degradation > hard failures
• Configuration files need the same validation as user input
• Kill switches should exist for every critical feature

Cloudflare's transparency here is exceptional. They detailed:
- The exact database query that caused duplicates
- The specific Rust panic message
- The incorrect initial assumption (DDoS attack)
- Four specific prevention measures

**This is how you do incident response.**

But it's also a reminder: If Cloudflare—with world-class SRE, monitoring, and redundancy—can have a hardcoded constant cause a global outage...

What hardcoded limits are lurking in your production code right now?

---

**First Comment (Post Immediately):**

The hardcoded `200` limit was in place because "it made sense at the time" based on historical ML feature counts.

Sound familiar?

I've written dozens of these. "MAX_CONNECTIONS = 100", "BUFFER_SIZE = 1024", "TIMEOUT = 30"

The difference: Cloudflare's serves 80% of the internet's traffic. Mine serve... significantly less. 😅

What's your favorite "seemed reasonable at the time" constant that came back to haunt you?
