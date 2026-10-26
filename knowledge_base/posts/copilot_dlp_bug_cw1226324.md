# Copilot DLP Bug CW1226324

"Confidential" labels. DLP policies. Copilot read your emails anyway.

Microsoft just patched it. But for two months, it was live in production.

## The Bug

Bug ID CW1226324. Reported January 21. Fixed mid-February.

- Copilot Chat ignored sensitivity labels on emails
- Copilot Chat ignored DLP policies designed to prevent exactly this
- Drafts and sent items labeled "Confidential" were summarized anyway

→ Your governance controls were in place. Copilot bypassed them.

## The Scope

This wasn't a niche edge case. It hit enterprise customers across:

- Outlook
- Word
- Excel
- PowerPoint

The "Work" tab in Copilot Chat was pulling confidential content that your DLP policies explicitly said it shouldn't touch.

→ Two months. Every M365 Copilot enterprise customer. Worldwide.

## The Spin

Microsoft's statement: "This did not provide anyone access to information they weren't already authorized to see."

Translation: Since you can already see your own emails, what's the problem?

The problem: Copilot summarizes. Copilot surfaces. Copilot makes findable what was buried. That's literally why you set the labels.

→ "You already had access" misses the entire point of data classification.

## The Bigger Picture

72% of S&P 500 companies now cite AI as a material risk in regulatory filings.

Not "might be a risk." Material risk. The kind lawyers make you disclose.

And this bug just showed why. Your security controls only work if the AI respects them.

→ You can't govern what doesn't follow your rules.

## The Bottom Line

You did everything right. Labels applied. DLP configured. Policies in place.

Copilot ignored all of it.

This is the scenario we've been warning about. Now it's not hypothetical.

---

Did your org get hit by this? Check your Copilot Chat history from January.
