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
