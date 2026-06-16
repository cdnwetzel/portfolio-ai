#!/usr/bin/env python3
"""
repo_to_kb.py — Generate a portfolio KB doc from a repo using the local LoRA.

Strategy: map-reduce over chunks so no content is lost to truncation.
  1. Split all discovered markdown into ~12k-char chunks
  2. Extract key facts from each chunk independently (map)
  3. Synthesize all fact extracts into the final KB doc (reduce)

Usage:
    python scripts/repo_to_kb.py /path/to/repo [--url https://github.com/...] [--out kb_doc.md]

Core function generate_kb_doc() is importable for webhook reuse.
"""

import argparse
import os
import sys
from pathlib import Path
import requests

VLLM_URL = os.environ.get("VLLM_URL", "http://10.0.1.125:8003")
MODEL = os.environ.get("KB_MODEL", "pscode-prod")

# Chunk size for map phase (~3k tokens each, well within context limit)
CHUNK_CHARS = 12_000

# Read these first, in order
MD_PRIORITY = [
    "README.md",
    "architecture.md", "ARCHITECTURE.md",
    "VISION.md", "vision.md",
    "STATUS.md",
    "CHECKPOINT.md",
    "prd.md", "PRD.md",
    "CONVENTIONS.md",
    "CLAUDE.md", "AGENTS.md", "GEMINI.md",
    "pending-tasks.md",
    "CHANGELOG.md",
]

# Directories that are never project content
EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "env",
    "node_modules", ".pytest_cache", "__pycache__",
    "site-packages", ".mypy_cache", ".ruff_cache",
    "archive", "review", "reviews", ".claude",
    "dist", "build", ".eggs",
    "planning",  # internal planning artifacts
}

# Max facts chunks to feed into a single synthesize call (~16k token limit)
MAX_CHUNKS_PER_SYNTHESIZE = 8

# Top-level subdirs to scan for additional .md files (after priority files)
# Note: "plans" excluded — internal planning artifacts, not useful for KB
CONTENT_SUBDIRS = ["docs", "specs", "services", "deploy"]

EXCLUDE_FILES = {"CHANGELOG.md", "LICENSE.md", "LICENSE", ".aider.chat.history.md"}

SYSTEM_PROMPT = """You generate knowledge base documents for a technical portfolio chatbot.
Documents are chunked and indexed for RAG retrieval, so they must be dense with specific,
searchable facts: version numbers, counts, names, file paths, architectural decisions, and lessons."""

EXTRACT_PROMPT = """You are reading part {chunk_num} of {total_chunks} from a software repository.
Extract every specific, concrete fact that would be useful in a technical KB doc:
- What the project does and its current version/status
- Architecture: components, ports, protocols, file paths, data flows
- Key features with specific details (counts, names, behaviors)
- Engineering decisions and why they were made
- Test counts, tooling, quality practices
- Hard-won lessons and non-obvious insights
- Tech stack: languages, libraries, infrastructure

Repository: {repo_url}

---
{content}
---

List all concrete facts found in this chunk. Be specific — include numbers, names, and paths exactly as written. One fact per line, grouped loosely by topic.
If a number appears as a goal or target (e.g. "we plan to reach 1500 tests"), mark it as "(target)" not a fact. Only report measured/observed values as plain facts:"""

SYNTHESIZE_PROMPT = """You are writing a knowledge base document for a technical portfolio chatbot.
The author is Chris Wetzel — a senior IT/infrastructure professional who builds sophisticated
engineering projects as hobby/portfolio work. Frame these as personal engineering projects
that demonstrate technical depth, not as client deliverables.

Below are facts extracted from all sections of the repository documentation.
Synthesize them into a complete KB doc using these exact sections:

# <Project Name> — <what it does, 10 words max>

## What It Is
2-3 sentences. Concrete facts: what it does, current version/status, where it runs.

## What Problem It Solves
The real motivation. Specific pain point, not generic "improves productivity."

## Architecture
How it actually works. Components, data flow, key interfaces. Include port numbers, paths, protocols.

## Key Features
Specific capabilities with concrete details. Numbers, names, behaviors — not vague adjectives.

## Engineering Quality
Tests (count if known), tooling, discipline choices, notable decisions and why.

## Tech Stack
Bullet list or table: language, key libraries, infrastructure.

## What I Learned Building This
Non-obvious insights. Hard-won lessons. What surprised him. What he'd do differently.

Rules:
- Only use facts from the extracted list below. Do not invent details.
- Write in third person: "Chris built...", "the project ships...", "pxx uses..."
- No vague claims ("robust", "scalable") — say what it specifically does.
- Dense over verbose. Each sentence should earn its place with a searchable fact.
- Prefer measured/observed facts over goals or planned targets (e.g. actual test count, not a roadmap target).
- End after the last section. Do not add any closing commentary, meta-notes, or explanations about the document.

Repository: {repo_url}

Extracted facts:
---
{facts}
---

Generate the KB doc now (stop after ## What I Learned Building This):"""


def is_excluded(path: Path, repo_root: Path) -> bool:
    try:
        rel = path.relative_to(repo_root)
    except ValueError:
        return True
    return any(part in EXCLUDE_DIRS for part in rel.parts)


def discover_md_files(repo_path: Path) -> list[Path]:
    """Discover project markdown files in priority order, excluding noise."""
    seen = set()
    found = []

    def add(p: Path):
        if p not in seen and p.exists() and not is_excluded(p, repo_path):
            if p.name not in EXCLUDE_FILES:
                seen.add(p)
                found.append(p)

    for name in MD_PRIORITY:
        add(repo_path / name)

    for subdir_name in CONTENT_SUBDIRS:
        subdir = repo_path / subdir_name
        if not subdir.is_dir() or is_excluded(subdir, repo_path):
            continue
        if subdir_name == "services":
            # Services: one level deep only — just each service's README
            for svc_dir in sorted(subdir.iterdir()):
                if svc_dir.is_dir() and not is_excluded(svc_dir, repo_path):
                    add(svc_dir / "README.md")
        else:
            for f in sorted(subdir.rglob("*.md")):
                if not is_excluded(f, repo_path) and f.name not in EXCLUDE_FILES:
                    add(f)

    for f in sorted(repo_path.glob("*.md")):
        add(f)

    return found


def build_full_context(files: list[Path]) -> tuple[str, list[str]]:
    """Read all files into a single string. Returns (full_text, included_names)."""
    parts = []
    included = []
    for f in files:
        try:
            content = f.read_text(encoding="utf-8", errors="ignore").strip()
            if not content:
                continue
            parts.append(f"### {f.name}\n\n{content}\n\n")
            included.append(f.name)
        except Exception:
            continue
    return "".join(parts), included


def split_into_chunks(text: str, chunk_size: int = CHUNK_CHARS) -> list[str]:
    """Split text into chunks, breaking on double-newlines where possible."""
    chunks = []
    while len(text) > chunk_size:
        # Try to break on a paragraph boundary near the chunk size
        split_at = text.rfind("\n\n", 0, chunk_size)
        if split_at == -1 or split_at < chunk_size // 2:
            split_at = chunk_size
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
    return chunks


def lora_call(messages: list[dict], model: str, vllm_url: str, max_tokens: int = 1024) -> str:
    resp = requests.post(
        f"{vllm_url}/v1/chat/completions",
        json={
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.1,
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def extract_facts(chunk: str, chunk_num: int, total: int, repo_url: str, model: str, vllm_url: str) -> str:
    """Map phase: extract concrete facts from one chunk."""
    prompt = EXTRACT_PROMPT.format(
        chunk_num=chunk_num,
        total_chunks=total,
        repo_url=repo_url or "not specified",
        content=chunk,
    )
    return lora_call(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        model, vllm_url, max_tokens=1024,
    )


def compress_facts(facts_list: list[str], model: str, vllm_url: str) -> str:
    """Compress a group of fact lists into a single deduplicated fact list."""
    combined = "\n\n".join(f"[Section {i+1}]\n{f}" for i, f in enumerate(facts_list))
    prompt = f"""Merge these fact lists into a single deduplicated list of concrete facts.
Keep all specific details: numbers, names, ports, paths, versions. Remove only true duplicates.

---
{combined}
---

Merged fact list:"""
    return lora_call(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        model, vllm_url, max_tokens=1024,
    )


def synthesize(facts_list: list[str], repo_url: str, model: str, vllm_url: str) -> str:
    """Reduce phase: synthesize all extracted facts into the final KB doc.
    If facts_list is too large for one synthesize call, compress hierarchically first.
    """
    # Hierarchical compression if too many chunks
    while len(facts_list) > MAX_CHUNKS_PER_SYNTHESIZE:
        print(f"  Compressing {len(facts_list)} fact groups...", file=sys.stderr)
        compressed = []
        for i in range(0, len(facts_list), MAX_CHUNKS_PER_SYNTHESIZE):
            group = facts_list[i:i + MAX_CHUNKS_PER_SYNTHESIZE]
            compressed.append(compress_facts(group, model, vllm_url))
        facts_list = compressed

    combined_facts = "\n\n".join(
        f"[Section {i+1}]\n{facts}" for i, facts in enumerate(facts_list)
    )
    prompt = SYNTHESIZE_PROMPT.format(
        repo_url=repo_url or "not specified",
        facts=combined_facts,
    )
    return lora_call(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        model, vllm_url, max_tokens=2048,
    )


def generate_kb_doc(
    repo_path: str,
    repo_url: str = "",
    model: str = MODEL,
    vllm_url: str = VLLM_URL,
) -> str:
    """
    Generate a portfolio KB doc from a repo.
    Importable for webhook reuse: generate_kb_doc(repo_path, repo_url) -> markdown str.
    """
    path = Path(repo_path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"Not a directory: {path}")

    files = discover_md_files(path)
    if not files:
        raise ValueError(f"No markdown files found in {path}")

    full_text, included = build_full_context(files)
    chunks = split_into_chunks(full_text, CHUNK_CHARS)

    print(f"Files read ({len(included)}): {', '.join(included)}", file=sys.stderr)
    print(f"Total context: {len(full_text):,} chars → {len(chunks)} chunks", file=sys.stderr)

    # Map: extract facts from each chunk
    facts_list = []
    for i, chunk in enumerate(chunks):
        print(f"Extracting facts from chunk {i+1}/{len(chunks)}...", file=sys.stderr)
        facts = extract_facts(chunk, i + 1, len(chunks), repo_url, model, vllm_url)
        facts_list.append(facts)

    # Reduce: synthesize into final KB doc
    print("Synthesizing KB doc...", file=sys.stderr)
    return synthesize(facts_list, repo_url, model, vllm_url)


def main():
    parser = argparse.ArgumentParser(description="Generate a portfolio KB doc from a repo.")
    parser.add_argument("repo_path", help="Path to the repository")
    parser.add_argument("--url", default="", help="GitHub URL for the repo")
    parser.add_argument("--out", default="", help="Output file (default: stdout)")
    parser.add_argument("--model", default=MODEL, help=f"Model (default: {MODEL})")
    parser.add_argument("--vllm-url", default=VLLM_URL, help=f"vLLM base URL (default: {VLLM_URL})")
    args = parser.parse_args()

    print(f"Analyzing {args.repo_path}...", file=sys.stderr)
    doc = generate_kb_doc(args.repo_path, args.url, args.model, args.vllm_url)

    if args.out:
        Path(args.out).write_text(doc)
        print(f"Written to {args.out}", file=sys.stderr)
    else:
        print(doc)


if __name__ == "__main__":
    main()
