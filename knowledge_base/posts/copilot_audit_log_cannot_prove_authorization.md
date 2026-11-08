# Copilot's Audit Log Cannot Answer the Question Legal Will Ask

*LinkedIn post by Chris Wetzel, published 2026-08-12. https://www.linkedin.com/posts/chris-wetzel_aigovernance-microsoftcopilot-m365-activity-7493292133680992256-qVMs*

Microsoft logs every file Copilot opens. That log still cannot answer the question Legal is going to ask.

Most governance programs stop at "audit logging is enabled." Here is what that actually buys you, and what it does not.

What The Log Actually Captures
• Who prompted, when, and which files, sites, and messages Copilot pulled to build the answer.
• The retrieved-resource detail is in there, not just the prompt text
• Credit where it is due. Microsoft did not skip this part.

→ You can prove what Copilot retrieved. That much works.

The Question It Cannot Answer
• The log tells you Copilot returned the compensation file to someone in Finance.
• It does not tell you whether that person was ever supposed to have access to it.
• Answering that requires the permission state exactly as it stood at that moment, and SharePoint does not keep one you can query.

→ You can prove what happened. You cannot prove whether it should have.

The Clock Nobody Started
• Standard audit retention is 180 days. Anything longer is a licensing decision somebody has to have already made.
• Permission problems surface late, usually when someone finally reads what they retrieved months ago.
• By then the folder has been reorganized, the group membership has changed, and the sharing link is gone.

→ The evidence expires on a schedule. The exposure does not.

A Log You Trust Versus A Log You Verify
• Every AI audit trail in your tenant is the vendor's record of what the vendor's system did.
• You are not verifying that record. You are trusting it.
• When I built my own AI runtime, I made the audit hash chained and tamper evident specifically so it could be checked by someone who does not trust me.

→ Worth knowing which of the two you are holding before you are in a room with lawyers in it.

The Bottom Line
Enabling audit logging is not governance. It is the ability to describe an incident you could not prevent and cannot fully reconstruct.

Your Turn: If Legal asked you today to prove whether one specific Copilot answer was authorized, what stops you first? The retention window. The permission history nobody kept. The licensing tier. Or the fact that this belongs to nobody on the org chart.

♻️ Repost if your org has "audit logging enabled" in a compliance doc somewhere.
✅ Follow me, Chris Wetzel, for the governance questions that only get asked after the incident.

#AIGovernance #MicrosoftCopilot #M365 #DataSecurity #Compliance #InfoSec
