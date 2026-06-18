"""
Pure functions for chat context management.
Extracted here so they can be unit-tested without the full FastAPI stack.
"""

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


def compact_history_by_tokens(messages: list, max_tokens: Optional[int] = None) -> list:
    """Drop oldest user/assistant pairs until history fits within a token budget.

    Preserves the system message at index 0 if present.
    """
    if max_tokens is None:
        max_tokens = MAX_CONTEXT_TOKENS // 3

    messages = list(messages)
    total = sum(count_tokens(m.get("content", "")) for m in messages)
    while total > max_tokens and len(messages) > 2:
        start = 1 if messages[0].get("role") == "system" else 0
        if start + 1 >= len(messages):
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
