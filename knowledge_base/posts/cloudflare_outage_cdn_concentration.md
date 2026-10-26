# One Company Took Down 20% of the Web (Cloudflare Outage, Nov 18 2025)

The internet didn't break this morning. One company did. And it took 20% of the web with it. ‼️

At 6:20 AM ET today, Cloudflare went down. X went dark. ChatGPT stopped responding. Shopify stores vanished.

Multiple vendors I work with experienced indirect downtime. Their "highly available" architectures failed because their CDN failed.

Did you know 80% of all CDN traffic flows through ONE company?


𝗧𝗵𝗲 𝗦𝗰𝗮𝗹𝗲 𝗡𝗼𝗯𝗼𝗱𝘆 𝗥𝗲𝗮𝗹𝗶𝘇𝗲𝘀
• 24 million websites use Cloudflare worldwide
• 80% of all CDN traffic passes through their infrastructure
• 30% of Fortune 500 companies rely on their services

→ One "unusual traffic spike" caused widespread 500 errors globally
→ Took 3+ hours to fully resolve


𝗪𝗵𝗮𝘁 𝗪𝗲𝗻𝘁 𝗗𝗼𝘄𝗻
• X, ChatGPT, Claude AI, Shopify, Indeed, McDonald's app
• Not a DNS issue. Not an attack. Just "unusual traffic"
• Their dashboard and API also failed - couldn't even monitor it
• Customers got generic 500 errors with zero transparency


𝗧𝗵𝗲 𝗦𝗶𝗻𝗴𝗹𝗲 𝗣𝗼𝗶𝗻𝘁 𝗼𝗳 𝗙𝗮𝗶𝗹𝘂𝗿𝗲 𝗣𝗿𝗼𝗯𝗹𝗲𝗺
• We obsess about multi-cloud, multi-region, multi-AZ
• Then route ALL traffic through one CDN provider
• No CDN redundancy = no real redundancy

→ Your five 9's uptime architecture has a single point of failure in front of it
→ Most teams have zero CDN failover strategy


𝗪𝗵𝗮𝘁 "𝗥𝗲𝘀𝗼𝗹𝘃𝗲𝗱" 𝗔𝗰𝘁𝘂𝗮𝗹𝗹𝘆 𝗠𝗲𝗮𝗻𝘀
• Fix implemented 3+ hours later
• Root cause: "Spike in unusual traffic" (zero technical details)
• Third time Cloudflare has had major outage in 18 months

→ "Unusual traffic spike" is the new "configuration error"


𝗧𝗵𝗲 𝗨𝗻𝗰𝗼𝗺𝗳𝗼𝗿𝘁𝗮𝗯𝗹𝗲 𝗧𝗿𝘂𝘁𝗵
• We moved from on-prem single points of failure to cloud single points of failure
• CDN was supposed to make things MORE resilient
• Instead, we concentrated risk into fewer vendors

→ Multi-CDN strategy exists but cost and complexity beat resilience every time


𝗪𝗵𝗮𝘁 𝗬𝗼𝘂 𝗖𝗮𝗻 𝗔𝗰𝘁𝘂𝗮𝗹𝗹𝘆 𝗗𝗼
• Implement multi-CDN with DNS failover
• Have a "Cloudflare is down" runbook ready
• Monitor CDN health separately from your application
• Don't just accept "unusual traffic" as root cause

→ Most teams have never tested CDN failover - the time to plan is NOT during an outage


𝗧𝗵𝗲 𝗕𝗼𝘁𝘁𝗼𝗺 𝗟𝗶𝗻𝗲
We spent decades learning not to put all our eggs in one basket. Then we put 80% of internet traffic through one CDN provider. This morning's outage wasn't an attack. It wasn't malicious. It was just Tuesday.


𝗬𝗼𝘂𝗿 𝗧𝘂𝗿𝗻: Does your DR plan account for your CDN going down?


♻️ Repost this if you spent this morning explaining to stakeholders why "the internet" was down
✅ Follow me, Chris Wetzel, for infrastructure reality checks from the field
