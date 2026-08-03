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

    # Meta queries: personality, system capabilities, meta questions
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

    # If starts with "what did you" or "how did you", likely on-topic
    if query_lower.startswith("what did you") or query_lower.startswith("how did you"):
        return "on_topic"

    # If starts with "tell me about" and isn't obviously off-topic, on-topic
    if query_lower.startswith("tell me about"):
        # Exception: if it's about general topics, off-topic
        if any(w in query_lower for w in ["ai news", "current", "weather", "news", "politics"]):
            return "off_topic"
        return "on_topic"

    # Default: off-topic (safer to redirect than hallucinate)
    return "off_topic"


# Hardcoded responses for meta and off-topic paths
META_RESPONSE = (
    "I'm an AI that knows Chris Wetzel's work—infrastructure he's built, projects he's solved, "
    "career experience he's documented. This chat runs on his homelab. "
    "Ask me about specific projects from his portfolio, infrastructure decisions, case studies, or technical approaches. "
    "I can tell you about the AVD migration, the homelab setup, systems work, or design decisions."
)

OFF_TOPIC_RESPONSE = (
    "That's outside my portfolio. I'm here to talk about Chris's professional work—"
    "infrastructure, projects, technical decisions, case studies. "
    "Ask me about something he's documented, and I'll give you the real details."
)
