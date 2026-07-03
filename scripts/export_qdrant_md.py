#!/usr/bin/env python3
"""
Export the indexed RAG content from Qdrant to markdown files — the *actual* retrieval
source of truth (post-chunking), which can differ from the repo `knowledge_base/*.md`
if a reindex is pending. Useful for auditing what the chat can actually ground on.

Scrolls the whole `documents` collection, groups chunks back into their source docs
(by `doc_id`, ordered by `chunk_index`), and writes one .md per document plus an INDEX.md.

Payload schema (from scripts/index_with_embeddings.py):
  doc_id, title, content (chunk text), source, chunk_index, word_count, impressions

Qdrant is LAN-only. Reach it either on a box that has it at 127.0.0.1:6333, or via an SSH
port-forward from your workstation, e.g.:
  ssh -f -N -L 16333:127.0.0.1:6333 root@ai.cwetzel.com
  python3 scripts/export_qdrant_md.py --qdrant-url http://127.0.0.1:16333

Usage:
  python3 scripts/export_qdrant_md.py [--qdrant-url URL] [--collection documents]
                                      [--out exports/qdrant_kb] [--merge]

By default each doc's chunks are written as explicit, separated sections (faithful to the
index — chunks overlap, so this is honest rather than a lossy reconstruction). --merge
naively concatenates chunk text into flowing prose (overlaps may duplicate a sentence).
"""
import argparse
import json
import os
import re
import urllib.request

QDRANT_URL = os.environ.get("QDRANT_URL", "http://127.0.0.1:6333")


def _post(url, body):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def scroll_all(qdrant_url, collection, page=256):
    """Yield every point's payload from the collection (dense-only, no vectors)."""
    offset = None
    while True:
        body = {"limit": page, "with_payload": True, "with_vector": False}
        if offset is not None:
            body["offset"] = offset
        result = _post(f"{qdrant_url}/collections/{collection}/points/scroll", body)["result"]
        for p in result.get("points", []):
            yield p.get("payload", {}) or {}
        offset = result.get("next_page_offset")
        if offset is None:
            break


def slug(text, maxlen=60):
    s = re.sub(r"[^a-z0-9]+", "-", (text or "untitled").lower()).strip("-")
    return (s[:maxlen].rstrip("-")) or "untitled"


def main():
    ap = argparse.ArgumentParser(description="Export indexed RAG content from Qdrant to markdown")
    ap.add_argument("--qdrant-url", default=QDRANT_URL)
    ap.add_argument("--collection", default="documents")
    ap.add_argument("--out", default="exports/qdrant_kb")
    ap.add_argument("--merge", action="store_true",
                    help="concatenate chunks into prose instead of separated sections")
    args = ap.parse_args()

    # Group payloads by doc_id (fall back to title+source for older points).
    docs = {}
    total_chunks = 0
    for pl in scroll_all(args.qdrant_url, args.collection):
        total_chunks += 1
        key = pl.get("doc_id") or f"{pl.get('source','?')}::{pl.get('title','?')}"
        d = docs.setdefault(key, {
            "title": pl.get("title", "Untitled"),
            "source": pl.get("source", "unknown"),
            "doc_id": pl.get("doc_id", key),
            "impressions": pl.get("impressions", 0),
            "chunks": [],
        })
        d["chunks"].append((pl.get("chunk_index", 0), pl.get("content", ""),
                            pl.get("word_count", len((pl.get("content") or "").split()))))

    if not docs:
        print(f"No points found in '{args.collection}' at {args.qdrant_url}. "
              f"Is Qdrant reachable (SSH forward up)?")
        return

    os.makedirs(args.out, exist_ok=True)
    index_rows = []
    for d in docs.values():
        d["chunks"].sort(key=lambda c: c[0])          # order by chunk_index
        words = sum(c[2] for c in d["chunks"])
        fname = f"{slug(d['source'])}__{slug(d['title'])}.md"

        lines = [
            "---",
            f"title: {json.dumps(d['title'])}",
            f"source: {d['source']}",
            f"doc_id: {json.dumps(d['doc_id'])}",
            f"chunks: {len(d['chunks'])}",
            f"word_count: {words}",
        ]
        if d["impressions"]:
            lines.append(f"impressions: {d['impressions']}")
        lines += ["---", "", f"# {d['title']}", ""]

        if args.merge:
            lines.append("\n\n".join(c[1].strip() for c in d["chunks"]))
        else:
            lines.append(f"> Exported from Qdrant — {len(d['chunks'])} indexed chunk(s), "
                         f"in `chunk_index` order. Chunks may overlap.\n")
            for idx, content, wc in d["chunks"]:
                lines.append(f"## Chunk {idx}  ({wc} words)\n")
                lines.append(content.strip() + "\n")

        with open(os.path.join(args.out, fname), "w", encoding="utf-8") as f:
            f.write("\n".join(lines).rstrip() + "\n")
        index_rows.append((d["source"], d["title"], len(d["chunks"]), words, fname))

    # INDEX.md
    index_rows.sort(key=lambda r: (r[0], r[1].lower()))
    idx = ["# Qdrant KB Export — Index", "",
           f"Collection: `{args.collection}`  ·  {len(docs)} documents  ·  "
           f"{total_chunks} chunks  ·  {sum(r[3] for r in index_rows):,} words", "",
           "| Source | Document | Chunks | Words | File |",
           "|--------|----------|-------:|------:|------|"]
    for source, title, nchunks, words, fname in index_rows:
        idx.append(f"| {source} | {title} | {nchunks} | {words:,} | [{fname}]({fname}) |")
    with open(os.path.join(args.out, "INDEX.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(idx) + "\n")

    print(f"Exported {len(docs)} documents / {total_chunks} chunks → {args.out}/")
    print(f"  see {args.out}/INDEX.md")


if __name__ == "__main__":
    main()
