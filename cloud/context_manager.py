"""
Pure functions for chat context management.
Extracted here so they can be unit-tested without the full FastAPI stack.
"""
from datetime import date

MAX_PROMPT_CHARS = 4000
MAX_HISTORY_CHARS = 24000


def compact_history(messages: list, max_chars: int = MAX_HISTORY_CHARS) -> list:
    """Drop oldest user/assistant pairs until total content length <= max_chars.

    System message (if present) is always preserved at index 0.
    Returns a new list; does not mutate the input.
    """
    messages = list(messages)
    total = sum(len(m.get("content", "")) for m in messages)
    while total > max_chars and len(messages) > 2:
        start = 1 if messages[0].get("role") == "system" else 0
        if start + 1 >= len(messages):
            break
        removed = messages.pop(start)
        total -= len(removed.get("content", ""))
        if start < len(messages) and messages[start].get("role") == "assistant":
            removed = messages.pop(start)
            total -= len(removed.get("content", ""))
    return messages


def inject_system_prompt(messages: list, system_prompt: str) -> list:
    """Prepend a system message if none is already present."""
    if any(m.get("role") == "system" for m in messages):
        return messages
    return [{"role": "system", "content": system_prompt}] + messages


def prompt_too_long(content: str, max_chars: int = MAX_PROMPT_CHARS) -> bool:
    return len(content) > max_chars


# ---------------------------------------------------------------------------
# Token-aware context budget utilities
# ---------------------------------------------------------------------------

import os
from typing import Optional

# Total context budget for vLLM. Default 14384 leaves ~2K tokens for the
# model's response under a 16K context window.
MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "14384"))
RESERVE_RESPONSE_TOKENS = int(os.getenv("RESERVE_RESPONSE_TOKENS", "2048"))

_tokenizer = None  # type: ignore


def get_tokenizer():
    """Lazy-load the Qwen tokenizer; return None if it fails to load."""
    global _tokenizer
    if _tokenizer is None:
        try:
            from transformers import AutoTokenizer

            _tokenizer = AutoTokenizer.from_pretrained(
                "Qwen/Qwen2.5-14B-Instruct",
                trust_remote_code=True,
            )
        except Exception:
            _tokenizer = False  # sentinel: failed to load
    return _tokenizer if _tokenizer is not False else None


def count_tokens(text: str) -> int:
    """Count tokens using the model tokenizer; fall back to chars/4."""
    if not text:
        return 0
    tokenizer = get_tokenizer()
    if tokenizer:
        try:
            return len(tokenizer.encode(text, add_special_tokens=False))
        except Exception:
            pass
    return max(1, len(text) // 4)


def compact_history_by_tokens(messages: list, max_tokens: Optional[int] = None, keep_recent: int = 4) -> list:
    """Drop oldest user/assistant pairs until history fits within a token budget.

    Preserves the system message at index 0 if present.
    Also preserves at least `keep_recent` recent user/assistant turns for multi-turn coherence.

    Args:
        messages: list of message dicts with 'role' and 'content'
        max_tokens: token budget (default: 1/3 of MAX_CONTEXT_TOKENS)
        keep_recent: minimum number of recent turns to preserve (default: 4)
    """
    if max_tokens is None:
        max_tokens = MAX_CONTEXT_TOKENS // 3

    messages = list(messages)
    total = sum(count_tokens(m.get("content", "")) for m in messages)

    # Determine how many message pairs to preserve at the end
    # (system message + keep_recent * 2 for user/assistant pairs, minimally)
    min_keep_idx = 0
    if messages and messages[0].get("role") == "system":
        min_keep_idx = 1

    # Calculate the minimum number of messages to keep (system + recent turns)
    # Each recent turn is typically 2 messages (user + assistant)
    recent_keep_count = min(keep_recent * 2, len(messages) - min_keep_idx)
    min_keep_idx = max(1 if messages and messages[0].get("role") == "system" else 0,
                       len(messages) - recent_keep_count)

    # Drop oldest messages until we fit the budget, but never drop below min_keep_idx
    while total > max_tokens and len(messages) > min_keep_idx + 1:
        start = 1 if messages[0].get("role") == "system" else 0
        if start >= len(messages) - 1:
            break
        removed = messages.pop(start)
        total -= count_tokens(removed.get("content", ""))
        if start < len(messages) and messages[start].get("role") == "assistant":
            removed = messages.pop(start)
            total -= count_tokens(removed.get("content", ""))
    return messages


def truncate_text_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text so it consumes at most max_tokens."""
    if max_tokens <= 0:
        return ""
    tokenizer = get_tokenizer()
    if tokenizer:
        try:
            ids = tokenizer.encode(text, add_special_tokens=False)
            if len(ids) <= max_tokens:
                return text
            return tokenizer.decode(ids[:max_tokens], skip_special_tokens=True)
        except Exception:
            pass
    return text[: max_tokens * 4]


def format_doc_block(title: str, source: str, content: str) -> str:
    """Return the markdown block exactly as it appears in the system prompt."""
    return f"\n\n### {title} ({source})\n{content}"


def fit_context_docs(
    docs: list,
    system_prefix: str,
    system_suffix: str,
    history_messages: list,
    user_query: str,
    max_tokens: int = MAX_CONTEXT_TOKENS,
    reserve_response_tokens: int = RESERVE_RESPONSE_TOKENS,
) -> list:
    """Select retrieved docs and truncate the last one to fit the token budget.

    Returns a new list of docs; the last doc may have its content truncated.
    """
    history_text = "\n".join(m.get("content", "") for m in history_messages)
    fixed_tokens = (
        count_tokens(system_prefix)
        + count_tokens(system_suffix)
        + count_tokens(history_text)
        + count_tokens(user_query)
        + reserve_response_tokens
    )
    remaining = max_tokens - fixed_tokens
    if remaining <= 0:
        return []

    selected = []
    for doc in docs:
        title = doc.get("title", "Unknown")
        source = doc.get("source", "")
        content = doc.get("content", "")

        block = format_doc_block(title, source, content)
        block_tokens = count_tokens(block)

        if block_tokens <= remaining:
            selected.append({**doc})
            remaining -= block_tokens
        else:
            # Try to fit a truncated version of this chunk, accounting for the
            # structural markdown overhead of the title/source wrapper.
            overhead = count_tokens(format_doc_block(title, source, ""))
            adjusted_remaining = remaining - overhead
            if adjusted_remaining > 0:
                truncated = truncate_text_to_tokens(content, adjusted_remaining)
                if truncated:
                    selected.append({**doc, "content": truncated})
            break

    return selected


def estimate_answer_length(query: str) -> int:
    """Estimate appropriate max_tokens for an answer based on query length/complexity.

    Short questions get short answers to avoid verbose responses.
    Long questions get more tokens for thorough explanation.

    Args:
        query: the user's question

    Returns:
        Recommended max_tokens for generation
    """
    query_words = len(query.split())

    if query_words <= 5:
        # Very short question: "What GPU?" -> brief answer (256 tokens ~100-150 words)
        return 256
    elif query_words <= 15:
        # Medium question: "Tell me about the AVD migration" -> substantial answer (1024 tokens ~400-500 words)
        return 1024
    else:
        # Long/complex question -> full answer with details (2048 tokens ~800-1000 words)
        return 2048


def server_facts_block(birthdate: str = "", today: "date | None" = None) -> str:
    """Deterministic, server-computed facts injected into the system prompt on every
    RAG turn. Recomputed per request, so never stale.

    Why this exists (DEFECT_LEDGER #1, live 2026-08-22): asked "how old is Chris",
    the model pattern-matched the KB's ubiquitous "26 years of experience" onto age
    and answered "Chris Wetzel is 26 years old" — the KB has no age statement at all,
    so retrieval had nothing true to offer. Age is computed HERE, not by the model:
    LLM date arithmetic is unreliable, and a static "Chris is N" fact in the KB goes
    stale on his birthday. Only the computed age reaches the prompt; the birthdate
    itself is config and never becomes prompt text.

    `birthdate` is ISO "YYYY-MM-DD"; empty or unparseable omits the age line.
    Positive facts only — never write a wrong value here even to negate it.
    """
    today = today or date.today()
    lines = [f"- Today's date is {today.isoformat()}."]
    if birthdate:
        try:
            dob = date.fromisoformat(birthdate)
        except ValueError:
            dob = None
        if dob is not None:
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            lines.append(f"- Chris Wetzel is {age} years old as of today.")
    return (
        "\nSERVER FACTS (computed by the server at request time — always current; "
        "trust these over retrieved documents):\n" + "\n".join(lines) + "\n"
    )
