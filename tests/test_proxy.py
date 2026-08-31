"""
Unit tests for proxy context management.
No infrastructure required — pure function tests.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "cloud"))
from context_manager import (
    compact_history,
    compact_history_by_tokens,
    inject_system_prompt,
    prompt_too_long,
    fit_context_docs,
    count_tokens,
    truncate_text_to_tokens,
    format_doc_block,
    server_facts_block,
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


# --- token budget utilities ---

def test_count_tokens_is_positive():
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0


def test_truncate_text_to_tokens_respects_limit():
    text = "word " * 100
    truncated = truncate_text_to_tokens(text, 10)
    assert count_tokens(truncated) <= 10
    assert len(truncated) <= len(text)


def test_format_doc_block_includes_title_source_content():
    block = format_doc_block("Resume", "resume.md", "I build things.")
    assert "Resume" in block
    assert "resume.md" in block
    assert "I build things." in block


def test_fit_context_docs_selects_all_when_budget_large():
    docs = [
        {"title": "A", "source": "a.md", "content": "content a"},
        {"title": "B", "source": "b.md", "content": "content b"},
    ]
    selected = fit_context_docs(
        docs,
        system_prefix="prefix ",
        system_suffix=" suffix",
        history_messages=[],
        user_query="hi",
        max_tokens=100,
        reserve_response_tokens=0,
    )
    assert len(selected) == 2
    assert selected[0]["content"] == "content a"
    assert selected[1]["content"] == "content b"


def test_fit_context_docs_drops_docs_when_budget_tight():
    docs = [
        {"title": "A", "source": "a.md", "content": "a " * 200},
        {"title": "B", "source": "b.md", "content": "b " * 200},
    ]
    selected = fit_context_docs(
        docs,
        system_prefix="prefix ",
        system_suffix=" suffix",
        history_messages=[],
        user_query="hi",
        max_tokens=20,
        reserve_response_tokens=0,
    )
    # Should select at most one doc (maybe truncated) given tiny budget
    assert len(selected) <= 1


def test_fit_context_docs_truncates_last_chunk_to_fit():
    docs = [
        {"title": "A", "source": "a.md", "content": "a " * 200},
    ]
    selected = fit_context_docs(
        docs,
        system_prefix="prefix ",
        system_suffix=" suffix",
        history_messages=[],
        user_query="hi",
        max_tokens=15,
        reserve_response_tokens=0,
    )
    assert len(selected) == 1
    assert count_tokens(selected[0]["content"]) < count_tokens("a " * 200)


def test_compact_history_by_tokens_preserves_system():
    long = "word " * 500
    messages = [
        msg("system", "you are chris"),
        msg("user", long), msg("assistant", long),
        msg("user", "keep me"), msg("assistant", "keep me"),
    ]
    result = compact_history_by_tokens(messages, max_tokens=10)
    assert result[0] == msg("system", "you are chris")


def test_compact_history_by_tokens_drops_pairs():
    long = "word " * 500
    messages = [
        msg("user", long), msg("assistant", long),
        msg("user", "short"), msg("assistant", "short"),
    ]
    result = compact_history_by_tokens(messages, max_tokens=10)
    assert result == [msg("user", "short"), msg("assistant", "short")]


# --- server_facts_block ---
# Deterministic age/date facts injected into the system prompt (2026-08-22 live
# confabulation: "how old is Chris" answered "26 years old" by pattern-matching
# "26 years of experience"). Age math must be exact — never the model's job.

from datetime import date


def test_server_facts_age_before_birthday():
    # Jan 9 1982 birthdate; on Jan 8 2026 the birthday hasn't happened yet -> 43
    block = server_facts_block("1982-01-09", today=date(2026, 1, 8))
    assert "43 years old" in block


def test_server_facts_age_on_birthday():
    block = server_facts_block("1982-01-09", today=date(2026, 1, 9))
    assert "44 years old" in block


def test_server_facts_age_after_birthday():
    block = server_facts_block("1982-01-09", today=date(2026, 8, 22))
    assert "44 years old" in block
    assert "2026-08-22" in block  # today's date is always stated


def test_server_facts_never_contains_birthdate():
    # Only the computed age reaches the prompt — the DOB itself must not.
    block = server_facts_block("1982-01-09", today=date(2026, 8, 22))
    assert "1982" not in block
    assert "01-09" not in block


def test_server_facts_empty_birthdate_omits_age():
    block = server_facts_block("", today=date(2026, 8, 22))
    assert "years old" not in block
    assert "2026-08-22" in block  # date line still present


def test_server_facts_invalid_birthdate_omits_age():
    block = server_facts_block("not-a-date", today=date(2026, 8, 22))
    assert "years old" not in block


class TestAnswerTokenCap:
    """estimate_answer_length must not scale the cap by question length.

    Regression for 2026-08-31: the cap was tiered on the QUESTION's word count
    (<=5 words -> 256 tokens), so "What has Chris built?" — four words, and the
    single most important question a visitor can ask — was truncated mid-word at
    ~279 tokens. max_tokens is a ceiling, not a brevity control: lowering it does
    not make a model concise, it cuts it off. Brevity belongs in the prompt.
    """

    def test_short_broad_question_gets_full_cap(self):
        from context_manager import estimate_answer_length, DEFAULT_ANSWER_TOKENS
        assert estimate_answer_length("What has Chris built?") == DEFAULT_ANSWER_TOKENS

    def test_cap_is_independent_of_question_length(self):
        from context_manager import estimate_answer_length
        caps = {
            estimate_answer_length("What GPU?"),
            estimate_answer_length("Tell me about the AVD migration"),
            estimate_answer_length(
                "Walk me through the hardest infrastructure problem you have "
                "solved, how you approached it, and what you would do differently"
            ),
        }
        assert len(caps) == 1, f"cap still varies with question length: {caps}"

    def test_cap_is_generous_enough_for_a_real_answer(self):
        # 256 was the value that truncated a real answer in production.
        from context_manager import estimate_answer_length
        assert estimate_answer_length("What has Chris built?") >= 1024
