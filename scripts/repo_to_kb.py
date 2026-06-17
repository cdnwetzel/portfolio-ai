#!/usr/bin/env python3
"""
repo_to_kb.py — Generate a portfolio KB doc from a repo using the local LoRA.

Strategy: README-first map-reduce. README gets its own dedicated extract pass
(it is the authoritative source). All other docs are chunked and extracted as
supporting context. Facts are labeled PRIMARY vs SUPPORTING so the synthesize
step knows what to trust when details conflict.

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

# Chunk size for map phase (~3k tokens, well within the 16k context limit)
CHUNK_CHARS = 12_000

# Priority order for non-README docs
MD_PRIORITY = [
    "architecture.md", "ARCHITECTURE.md",
    "VISION.md", "vision.md",
    "STATUS.md",
    "CHECKPOINT.md",
    "prd.md", "PRD.md",
    "CONVENTIONS.md",
    "CLAUDE.md", "AGENTS.md", "GEMINI.md",
    "pending-tasks.md",
]

EXCLUDE_DIRS = {
    ".git", ".venv", "venv", "env",
    "node_modules", ".pytest_cache", "__pycache__",
    "site-packages", ".mypy_cache", ".ruff_cache",
    "archive", "review", "reviews", ".claude",
    "dist", "build", ".eggs",
    "planning",
}

CONTENT_SUBDIRS = ["docs", "specs", "services", "deploy"]

EXCLUDE_FILES = {"CHANGELOG.md", "LICENSE.md", "LICENSE", ".aider.chat.history.md"}

# Max fact groups to feed into a single synthesize call (context limit guard)
MAX_CHUNKS_PER_SYNTHESIZE = 8

SYSTEM_PROMPT = """You extract and synthesize facts for a professional technical portfolio knowledge base.
This is used by recruiters, collaborators, and clients to understand the author's engineering work.
Accuracy is non-negotiable — errors here misrepresent someone's career. Be precise and complete."""

# README gets a dedicated extract with a thorough checklist — it is the authoritative source
README_EXTRACT_PROMPT = """You are extracting facts from the README of a software repository for a professional portfolio KB.
The README is the PRIMARY source — extract every concrete detail. Miss nothing.

Work through this checklist explicitly:

PROJECT IDENTITY
- Project name, one-line description
- Version number and current status (alpha/beta/stable/v1.0 etc.)
- PyPI package name and install command (exact)
- GitHub URL
- Any separately installable sub-packages or standalone components

CLI COMMANDS & FLAGS — list every one found, including:
- Default invocation and what it does
- Edit/write modes and their flags
- Autonomous or loop modes (--loop, --heal, --self-fix, etc.)
- Diagnostic/health commands (--doctor, --self-test, --self-lint, etc.)
- Any slash commands (/recall, /remember, /forget, etc.)
- Flags that pass through to underlying tools

ARCHITECTURE — extract specifically:
- Each named component and what it does
- Port numbers for every service
- File paths and config file locations
- The exact process handoff pattern (e.g. os.execv, subprocess, exec)
- Data flow: what goes in, what comes out, where it goes next
- What runs locally vs remotely

DESIGN DECISIONS — why each architectural choice was made:
- Why os.execv (or equivalent) instead of subprocess/wrapper
- Why fail-closed vs fail-open
- Why local vs cloud
- Any "deliberate" or "intentional" design choices with stated reasons

STANDALONE COMPONENTS
- Any sub-package installable independently (pip install X)
- Services that can run standalone

TEST SUITE
- The count from the project's OWN pytest/test runner (label as "project test suite")
- Do NOT count install verification tests as the project test suite
- If multiple counts appear, list each with its source

NAMED OPTIMIZATIONS & ALGORITHMS
- Cache layers and their speedup (LRU cache, etc.)
- Search algorithms with their parameters (HNSW, BM25 weight %, vector weight %)
- Performance figures (latency, dataset size benchmarks)

MULTI-TOOL OR MULTI-MODEL PATTERNS
- Parallel reviewer setups (multiple AI tools reviewing simultaneously)
- Multi-model routing or fallback chains
- Named reviewer tools used

ENVIRONMENT & CONFIG
- Every environment variable name and default value
- Config file locations
- Override mechanisms

Repository: {repo_url}

README content:
---
{content}
---

Extract every fact found. One fact per line. Group by the checklist categories above.
Mark any metric that is a goal/target (not yet measured) with "(target)".
Mark install verification test counts with "(install check, not project test suite)":"""

# Supporting docs get a thorough but briefer extract
SUPPORTING_EXTRACT_PROMPT = """You are extracting facts from part {chunk_num} of {total_chunks} of the supporting documentation
for a software repository. These facts supplement the README.

Look specifically for anything NOT typically in a README:
- Internal architecture details, file paths, class/function names
- Engineering decisions with reasons (why X was chosen over Y)
- Lessons learned, what broke, what was surprising
- CLI commands or features not documented in README
- Test counts from the project's own pytest suite (NOT install verification counts)
- Named sub-features with implementation specifics (cache hit rates, algorithm parameters)
- Multi-tool patterns (parallel reviewers, concurrent LLM calls)
- Standalone installable sub-packages

Repository: {repo_url}
Source: chunk {chunk_num}/{total_chunks} of supporting docs

---
{content}
---

Extract concrete facts not already obvious from a typical README. One fact per line.
Mark any metric that is a goal/target with "(target)".
Mark install verification test counts with "(install check, not project test suite)":"""

SYNTHESIZE_PROMPT = """You are writing a professional portfolio knowledge base document for Chris Wetzel.
This will be read by recruiters, collaborators, and clients asking about his engineering projects.
Getting the facts right matters — this represents his career and skills.

Facts are labeled [PRIMARY] (from README — highest confidence) or [SUPPORTING] (from other docs).
Rules for conflicts:
- Prefer [PRIMARY] facts over [SUPPORTING] facts
- For test counts: use the count from the project's OWN test suite (pytest), NOT from install verification
- If a [PRIMARY] fact and [SUPPORTING] fact conflict, use [PRIMARY] and note the discrepancy only if significant

Frame this as a personal engineering project that demonstrates technical depth.
Chris Wetzel is a senior IT/infrastructure professional — not a student, not a contractor billing hours.

Write the KB doc with EXACTLY these sections and headers:

# <Project Name> — <one-line description, 10 words max>

## What It Is
2-3 sentences. What it does, current version/status, where it runs. Concrete facts only.

## What Problem It Solves
The real motivation behind building it. Specific pain point, not generic "improves workflow."

## Architecture
How it actually works: components, data flow, key interfaces. Include port numbers, file paths,
and the specific process handoff pattern (e.g. os.execv vs subprocess). Show the actual flow.

## Key Features
Specific capabilities with concrete details. Include:
- Named modes and commands (autonomous, diagnostic, dogfooding)
- Named algorithms with parameters (HNSW, BM25 weights, LRU cache behavior)
- Slash commands or interactive session commands
- Multi-tool or multi-model patterns

## Engineering Quality
Test count (from project's own pytest suite — not install verification), tooling choices,
notable discipline decisions and the reason behind each.

## Tech Stack
Clean bullet list: language/version, key libraries, infrastructure components with roles.

## What I Learned Building This
Non-obvious insights. Hard-won lessons. What broke and what that revealed. What he'd do differently.
Specific, not generic. Each point should be something a reader couldn't have guessed.

Strict rules:
- Use ONLY facts from the extracted lists below. Do not invent or infer details.
- Write in third person: "Chris built...", "pxx uses...", "the project ships..."
- No vague adjectives ("robust", "scalable", "powerful") — replace with specifics.
- Dense over verbose. Every sentence earns its place with a searchable fact.
- Use measured/observed values not targets. Do not report planned future counts as current facts.
- Stop after ## What I Learned Building This. No closing commentary, no meta-notes.

Repository: {repo_url}

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


def discover_supporting_files(repo_path: Path) -> list[Path]:
    """Discover non-README markdown files in priority order."""
    seen = set()
    found = []
    readme = repo_path / "README.md"

    def add(p: Path):
        if p != readme and p not in seen and p.exists() and not is_excluded(p, repo_path):
            if p.name not in EXCLUDE_FILES and p.name != "README.md":
                seen.add(p)
                found.append(p)

    for name in MD_PRIORITY:
        add(repo_path / name)

    for subdir_name in CONTENT_SUBDIRS:
        subdir = repo_path / subdir_name
        if not subdir.is_dir() or is_excluded(subdir, repo_path):
            continue
        if subdir_name == "services":
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


def build_text(files: list[Path]) -> tuple[str, list[str]]:
    """Concatenate files into a single string."""
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
    """Split text into chunks at paragraph boundaries."""
    chunks = []
    while len(text) > chunk_size:
        split_at = text.rfind("\n\n", 0, chunk_size)
        if split_at == -1 or split_at < chunk_size // 2:
            split_at = chunk_size
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
    return chunks


def lora_call(messages: list[dict], model: str, vllm_url: str, max_tokens: int = 1024, retries: int = 3) -> str:
    import time
    last_err = None
    for attempt in range(retries):
        try:
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
        except Exception as e:
            last_err = e
            if attempt < retries - 1:
                wait = 15 * (attempt + 1)
                print(f"  Call failed ({e.__class__.__name__}), retrying in {wait}s...", file=sys.stderr)
                time.sleep(wait)
    raise last_err


def extract_readme(content: str, repo_url: str, model: str, vllm_url: str) -> str:
    """Dedicated README extract with full checklist. Returns labeled PRIMARY facts."""
    chunks = split_into_chunks(content, CHUNK_CHARS)
    facts_parts = []
    for i, chunk in enumerate(chunks):
        print(f"  README chunk {i+1}/{len(chunks)}...", file=sys.stderr)
        prompt = README_EXTRACT_PROMPT.format(repo_url=repo_url or "not specified", content=chunk)
        facts_parts.append(lora_call(
            [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            model, vllm_url, max_tokens=2048,
        ))
    combined = "\n\n".join(facts_parts)
    return f"[PRIMARY - README]\n{combined}"


def extract_supporting(chunk: str, chunk_num: int, total: int, repo_url: str, model: str, vllm_url: str) -> str:
    """Extract facts from a supporting doc chunk. Returns labeled SUPPORTING facts."""
    prompt = SUPPORTING_EXTRACT_PROMPT.format(
        chunk_num=chunk_num,
        total_chunks=total,
        repo_url=repo_url or "not specified",
        content=chunk,
    )
    facts = lora_call(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        model, vllm_url, max_tokens=1024,
    )
    return f"[SUPPORTING - chunk {chunk_num}/{total}]\n{facts}"


def compress_facts(facts_list: list[str], model: str, vllm_url: str) -> str:
    """Compress a group of fact strings into one deduplicated list, preserving PRIMARY labels."""
    combined = "\n\n".join(facts_list)
    prompt = f"""Merge these fact lists into one deduplicated list.
Preserve all [PRIMARY] and [SUPPORTING] labels. Keep every specific detail: numbers, names,
ports, paths, versions, algorithm parameters. Remove only true word-for-word duplicates.

---
{combined}
---

Merged fact list:"""
    return lora_call(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
        model, vllm_url, max_tokens=1500,
    )


def synthesize(facts_list: list[str], repo_url: str, model: str, vllm_url: str) -> str:
    """Reduce phase: synthesize labeled facts into the final KB doc."""
    while len(facts_list) > MAX_CHUNKS_PER_SYNTHESIZE:
        print(f"  Compressing {len(facts_list)} fact groups...", file=sys.stderr)
        compressed = []
        for i in range(0, len(facts_list), MAX_CHUNKS_PER_SYNTHESIZE):
            group = facts_list[i:i + MAX_CHUNKS_PER_SYNTHESIZE]
            compressed.append(compress_facts(group, model, vllm_url))
        facts_list = compressed

    combined_facts = "\n\n".join(facts_list)
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

    readme = path / "README.md"
    supporting_files = discover_supporting_files(path)

    facts_list = []

    # Phase 1: README dedicated extract (PRIMARY)
    if readme.exists():
        readme_text = readme.read_text(encoding="utf-8", errors="ignore").strip()
        print(f"Extracting README ({len(readme_text):,} chars)...", file=sys.stderr)
        facts_list.append(extract_readme(readme_text, repo_url, model, vllm_url))
    else:
        print("No README.md found — proceeding with supporting docs only.", file=sys.stderr)

    # Phase 2: Supporting docs chunked extract (SUPPORTING)
    if supporting_files:
        supporting_text, included = build_text(supporting_files)
        chunks = split_into_chunks(supporting_text, CHUNK_CHARS)
        print(f"Supporting docs ({len(included)} files, {len(supporting_text):,} chars → {len(chunks)} chunks):", file=sys.stderr)
        for name in included:
            print(f"  {name}", file=sys.stderr)
        for i, chunk in enumerate(chunks):
            print(f"Extracting supporting chunk {i+1}/{len(chunks)}...", file=sys.stderr)
            facts_list.append(extract_supporting(chunk, i + 1, len(chunks), repo_url, model, vllm_url))

    if not facts_list:
        raise ValueError(f"No content found in {path}")

    # Phase 3: Synthesize (with hierarchical compression if needed)
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
