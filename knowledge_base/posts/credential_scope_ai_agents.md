# Credential Scope: The Real AI Agent Risk

An AI agent didn't delete the database. The credential did.

I read a story this week about a team building an agent to automate infrastructure. Nine seconds in, the agent called volumeDelete on production. Wiped it clean.

The headline was "AI system destroys database." The architecture truth: the credential had permission. If it didn't, the bad decision is a no-op.

## Trigger Vs Tools

Everyone talks about the agent's decision. "Why did it delete?" "Did the safety rules fail?" "How did the prompt let this happen?"

Those are the wrong questions. The agent didn't do anything it wasn't authorized to do. It did exactly what its credentials let it do, which was the problem.

## The Enforcement Layer

If the credential the agent ran under did not have volumeDelete permission on that database, the agent couldn't call it. Period. Prompt rules are advisory. IAM is enforced.

Prompt safety means nothing if the credential is scoped wrong. It's like putting a bouncer at the door while the back window is open.

## What Nobody Is Scoping

Most teams building agents right now are running them under one of three credentials:
- Personal token (carries your full access)
- Service account with admin role (because it was fastest at midnight)
- Whatever was easiest to spin up before the demo

None of those are credentials. They're liability bets.

Least-privilege for agents means: service account with read-only to prod by default, separate credentials for write operations, smallest set of tools the task actually needs, audit trail that captures what the agent called and when.

## The Audit Gap

After the bad decision fires, the question is always "what did it actually do?" Cloud audit logs catch the API call. They don't catch the reasoning.

If the agent runs as you, the audit log says you deleted the database. If it runs as a scoped service account, the log says the agent did, under that credential, with that tool, at that time. One answers the question. The other gets your team blamed.

## The Real Risk

The AI is not the risk. The credential scope is.

Same problem I keep flagging on the Copilot governance side. Same architecture. Different vendor. Different tool. Same failure mode: something has access, something inherits that access, nobody audited what changed.

---

Be honest. The agent your team is building right now, what is it running as?

- Your personal token
- A service account that was scoped two months ago and never re-reviewed
- A service account with admin role because that was the fastest path
- Or the answer nobody wants to type out loud: nobody on the team can tell you for sure
