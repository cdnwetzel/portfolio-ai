"""Unit tests for structure-aware chunking (rag-improvements.md §2.2)."""
import importlib.util
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "index_with_embeddings.py")
_spec = importlib.util.spec_from_file_location("indexer", _PATH)
indexer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(indexer)

chunk_text = indexer.chunk_text
_split_sections = indexer._split_sections


def test_sections_split_on_headers():
    text = "# Title\nintro\n\n## A\nalpha body\n\n## B\nbeta body"
    secs = _split_sections(text)
    assert len(secs) == 3
    assert secs[1].startswith("## A")
    assert secs[2].startswith("## B")


def test_small_sections_merge_up_to_target():
    # Two tiny sections merge into ONE chunk (don't emit tiny fragments).
    text = "## One\nshort one\n\n## Two\nshort two"
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    assert len(chunks) == 1
    assert "short one" in chunks[0] and "short two" in chunks[0]


def test_merge_breaks_when_target_exceeded():
    # Each section ~30 words; with chunk_size=50, two sections overflow → split at header.
    s = lambda h: f"## {h}\n" + " ".join(["w"] * 30)
    text = s("A") + "\n\n" + s("B") + "\n\n" + s("C")
    chunks = chunk_text(text, chunk_size=50, overlap=10)
    assert len(chunks) >= 2
    assert all(len(c.split()) <= 50 + 5 for c in chunks)  # ~target, header tokens slack


def test_long_section_falls_back_to_word_windows():
    body = "word " * 1000  # one big section, no internal headers
    text = "## Big\n" + body
    chunks = chunk_text(text, chunk_size=400, overlap=50)
    assert len(chunks) > 1  # split into windows
    assert all(len(c.split()) <= 400 for c in chunks)


def test_preamble_before_first_header_is_kept():
    text = "leading text with no header\n\n## Section\nbody"
    chunks = chunk_text(text)
    assert any("leading text" in c for c in chunks)


def test_no_empty_chunks():
    text = "## A\n\n\n## B\nreal content here"
    chunks = chunk_text(text)
    assert all(c.strip() for c in chunks)


def test_plain_text_without_headers():
    text = "just a paragraph of words without any markdown headers at all"
    chunks = chunk_text(text)
    assert len(chunks) == 1
    assert chunks[0].startswith("just a paragraph")
