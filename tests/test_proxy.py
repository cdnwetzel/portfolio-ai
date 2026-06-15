"""
Unit tests for proxy context management.
No infrastructure required — pure function tests.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "cloud"))
from context_manager import (
    compact_history,
    inject_system_prompt,
    prompt_too_long,
    MAX_PROMPT_CHARS,
    MAX_HISTORY_CHARS,
)


def msg(role: str, content: str) -> dict:
    return {"role": role, "content": content}


# --- compact_history ---

def test_compact_history_short_unchanged():
    messages = [msg("user", "hi"), msg("assistant", "hello")]
    result = compact_history(messages, max_chars=1000)
    assert result == messages


def test_compact_history_drops_oldest_pair():
    # 3 user/assistant pairs; first two push total over limit
    long = "x" * 500
    messages = [
        msg("user", long), msg("assistant", long),  # pair 1 — should be dropped
        msg("user", long), msg("assistant", long),  # pair 2 — should be dropped
        msg("user", "short"), msg("assistant", "short"),  # pair 3 — kept
    ]
    result = compact_history(messages, max_chars=100)
    assert result == [msg("user", "short"), msg("assistant", "short")]


def test_compact_history_preserves_system_message():
    long = "x" * 500
    messages = [
        msg("system", "you are chris"),
        msg("user", long), msg("assistant", long),
        msg("user", "keep me"), msg("assistant", "keep me"),
    ]
    result = compact_history(messages, max_chars=100)
    assert result[0] == msg("system", "you are chris")


def test_compact_history_never_drops_below_one_pair():
    # Even if a single pair exceeds max_chars, it should not be removed
    long = "x" * 5000
    messages = [msg("user", long), msg("assistant", long)]
    result = compact_history(messages, max_chars=10)
    assert len(result) == 2


def test_compact_history_does_not_mutate_input():
    messages = [msg("user", "x" * 500), msg("assistant", "x" * 500)]
    original = list(messages)
    compact_history(messages, max_chars=10)
    assert messages == original


# --- inject_system_prompt ---

def test_inject_adds_system_when_absent():
    messages = [msg("user", "hello")]
    result = inject_system_prompt(messages, "be helpful")
    assert result[0] == msg("system", "be helpful")
    assert len(result) == 2


def test_inject_skips_when_system_present():
    messages = [msg("system", "existing"), msg("user", "hello")]
    result = inject_system_prompt(messages, "new prompt")
    assert result[0] == msg("system", "existing")
    assert len(result) == 2


# --- prompt_too_long ---

def test_prompt_within_limit():
    assert not prompt_too_long("hello", max_chars=MAX_PROMPT_CHARS)


def test_prompt_exactly_at_limit():
    assert not prompt_too_long("x" * MAX_PROMPT_CHARS, max_chars=MAX_PROMPT_CHARS)


def test_prompt_over_limit():
    assert prompt_too_long("x" * (MAX_PROMPT_CHARS + 1), max_chars=MAX_PROMPT_CHARS)
