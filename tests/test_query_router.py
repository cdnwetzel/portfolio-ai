"""Tests for cloud/query_router.py — Tier 4 query classification.

Regression cover for 2026-08-19: the router defaulted to off_topic, so any question
without a keyword hit — including "what can you tell me about chris" — was redirected
away from the portfolio it exists to describe. The default is now on_topic, with
grounding left to api-proxy's RAG_MIN_SCORE guardrail where it belongs.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cloud"))

from query_router import (  # noqa: E402
    classify_query,
    META_RESPONSE,
    OFF_TOPIC_RESPONSE,
    NOT_DOCUMENTED_RESPONSE,
)


class TestMetaQueries:
    """Questions about the chat itself get the instant meta response, not a redirect."""

    def test_who_are_you(self):
        assert classify_query("who are you?") == "meta"

    def test_how_does_this_work(self):
        assert classify_query("how does this work") == "meta"

    def test_what_can_i_ask(self):
        assert classify_query("what can I ask?") == "meta"

    def test_what_do_you_know(self):
        # Regressed live: fell through to the off-topic default.
        assert classify_query("what do you know?") == "meta"

    def test_what_am_i_supposed_to_do(self):
        # A visitor asking the chat for help must never be told they're off-topic.
        assert classify_query("what am I supposed to do") == "meta"

    def test_case_insensitive(self):
        assert classify_query("WHO ARE YOU") == "meta"


class TestOnTopicQueries:
    def test_asking_about_chris_is_on_topic(self):
        # The single most likely opening question on a portfolio site.
        assert classify_query("what can you tell me about chris") == "on_topic"

    def test_portfolio_keyword(self):
        assert classify_query("Tell me about the GPU home lab setup") == "on_topic"

    def test_what_has_chris_built(self):
        assert classify_query("what has chris built?") == "on_topic"

    def test_unmatched_query_defaults_to_on_topic(self):
        # The default is permissive: the RAG guardrail (RAG_MIN_SCORE), not the
        # router, is what prevents ungrounded answers.
        assert classify_query("what is Chris's favorite operating system") == "on_topic"

    def test_portfolio_keyword_beats_off_topic_keyword(self):
        # Ordering matters: an explicit portfolio signal wins over a stray match.
        assert classify_query("did the gpu build make the news") == "on_topic"


class TestOffTopicQueries:
    def test_weather(self):
        assert classify_query("what's the weather in Dallas") == "off_topic"

    def test_politics(self):
        assert classify_query("who won the election") == "off_topic"

    def test_joke(self):
        assert classify_query("tell me a joke") == "off_topic"

    def test_crypto(self):
        assert classify_query("bitcoin price?") == "off_topic"


class TestCannedResponses:
    """Every canned path must offer a way forward — these are dead ends otherwise."""

    def test_meta_response_has_followups(self):
        assert "FOLLOWUPS:" in META_RESPONSE

    def test_off_topic_response_has_followups(self):
        assert "FOLLOWUPS:" in OFF_TOPIC_RESPONSE

    def test_not_documented_response_has_followups(self):
        assert "FOLLOWUPS:" in NOT_DOCUMENTED_RESPONSE

    def test_not_documented_keeps_its_refusal_phrase(self):
        # scripts/selftest and the graded eval match on this substring.
        assert "don't have that documented" in NOT_DOCUMENTED_RESPONSE.lower()

    def test_followups_block_is_last(self):
        # parseFollowups (useChat.js) splits on the block and displays what precedes
        # it, so anything after the marker would be lost from the visible answer.
        for resp in (META_RESPONSE, OFF_TOPIC_RESPONSE, NOT_DOCUMENTED_RESPONSE):
            head, _, tail = resp.partition("FOLLOWUPS:")
            assert head.strip(), "canned response must have visible text before FOLLOWUPS"
            assert "FOLLOWUPS:" not in tail, "only one FOLLOWUPS block allowed"
