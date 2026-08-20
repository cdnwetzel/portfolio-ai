"""
Query classification for Tier 4: route to meta (instant), on-topic (full RAG), or off-topic (redirect).

- meta: personality/system questions ("who are you", "how does this work")
- on-topic: portfolio/technical questions (full RAG pipeline)
- off-topic: external knowledge ("current events", "weather", etc.)
"""


def classify_query(query: str) -> str:
    """Classify query as 'meta' | 'on_topic' | 'off_topic'.

    Returns:
        'meta': personality/meta questions (instant response, no RAG)
        'on_topic': portfolio/technical questions (full RAG pipeline)
        'off_topic': questions outside the portfolio (redirect, no RAG)
    """

    query_lower = query.lower()

    # Meta queries: personality, system capabilities, meta questions.
    # "What do you know" / "what am I supposed to do" style phrasings were missing
    # and fell through to the off-topic default, so a visitor asking the chat for
    # help got told their question was outside the portfolio (2026-08-19).
    meta_keywords = [
        "who are you",
        "what are you",
        "tell me about yourself",
        "about this system",
        "about this chat",
        "how does this work",
        "how does it work",
        "what can you help",
        "what can you do",
        "what can i ask",
        "what can i do",
        "what do you know",
        "what should i ask",
        "what am i supposed to",
        "what is this",
        "what's this",
        "how do i use",
        "your capabilities",
    ]
    for kw in meta_keywords:
        if kw in query_lower:
            return "meta"

    # On-topic keywords: portfolio, projects, infrastructure, technical topics
    on_topic_keywords = [
        "avd",
        "migration",
        "vmware",
        "sap",
        "compliance",
        "soc2",
        "infrastructure",
        "gpu",
        "reranker",
        "qdrant",
        "homelab",
        "t5810",
        "asrock",
        "gentoo",
        "openrc",
        "project",
        "case study",
        "experience",
        "built",
        "designed",
        "developed",
        "engineered",
        "implemented",
        "scaled",
        "optimized",
        "security",
        "hardening",
        "automation",
        "kubernetes",
        "docker",
        "linux",
        "systems",
        "infrastructure",
        "networking",
        "cloud",
        "disaster recovery",
        "backup",
        "virtualization",
        "performance",
        "troubleshooting",
    ]
    for kw in on_topic_keywords:
        if kw in query_lower:
            return "on_topic"

    # Explicitly external subjects: redirect without spending a GPU call.
    # This list is the ONLY route to off_topic now — see the default below.
    off_topic_keywords = [
        "weather",
        "news",
        "current events",
        "politics",
        "president",
        "election",
        "stock price",
        "crypto",
        "bitcoin",
        "recipe",
        "horoscope",
        "translate",
        "write me a poem",
        "tell me a joke",
    ]
    for kw in off_topic_keywords:
        if kw in query_lower:
            return "off_topic"

    # Default: ON-topic. This was previously off_topic, which made the router a
    # safety mechanism it was never able to be: the keyword list had no entry for
    # "chris", so "what can you tell me about chris" — the most likely opening
    # question on a portfolio site — got redirected (2026-08-19).
    #
    # Hallucination is NOT gated here. api-proxy.py's RAG guardrail refuses when the
    # top retrieval score is below RAG_MIN_SCORE, which is the real grounding check
    # and applies to everything reaching this path. The router is a cost optimization
    # (skip the GPU on obvious junk), so its default should be permissive and its
    # explicit off-topic list should carry the redirects.
    return "on_topic"


# Hardcoded responses for meta and off-topic paths.
#
# Both carry a FOLLOWUPS block so the canned paths render suggestion chips like a
# real answer does. The frontend already parses this (useChat.js parseFollowups)
# and strips it from the displayed text — no client change needed. Without it these
# paths were a dead end: the visitor got told "no" and handed nothing to click.
_STARTER_FOLLOWUPS = (
    '\nFOLLOWUPS:["What has Chris built?",'
    '"Tell me about the GPU home lab setup",'
    '"What consulting and MSP experience does Chris have?"]'
)

META_RESPONSE = (
    "I'm an AI that knows Chris Wetzel's work—infrastructure he's built, projects he's solved, "
    "career experience he's documented. This chat runs on his homelab. "
    "Ask me about specific projects from his portfolio, infrastructure decisions, case studies, or technical approaches. "
    "I can tell you about the AVD migration, the homelab setup, systems work, or design decisions."
) + _STARTER_FOLLOWUPS

OFF_TOPIC_RESPONSE = (
    "I only know Chris Wetzel's professional work—the infrastructure he's built, the projects "
    "he's shipped, and the technical decisions behind them. I don't have anything useful to say "
    "about that one. Here's what I can actually dig into:"
) + _STARTER_FOLLOWUPS

# Returned when retrieval finds nothing relevant enough (api-proxy.py RAG guardrail).
NOT_DOCUMENTED_RESPONSE = (
    "I don't have that documented in my knowledge base. Try one of these instead:"
) + _STARTER_FOLLOWUPS
