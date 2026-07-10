#!/usr/bin/env python3
"""Compare two Qdrant collections on judge-free retrieval quality.

Why this exists
---------------
The cross-encoder reranker (bge-reranker-base) caps each (query, chunk) pair at 512 tokens — an
XLM-RoBERTa architectural limit. The indexer's 400-word chunks tokenize to a ~640-token median, so
~67% of chunks are *ranked* on roughly their first three-quarters. Smaller chunks fit the window
but, because RAG_TOP_K is a fixed count of chunks, they shrink the evidence the generator sees.

Rather than guess, build a parallel collection at a different chunk size and measure. This script
never writes: it reads two collections through the same embed → search → rerank → per-doc-cap
pipeline the proxy runs, and scores each with the golden set's `expect_substrings` as ground truth.

The metric is deliberately model-free. "Did the fact reach the top-k?" is exactly what reranker
truncation can break, and it needs no judge, so it cannot be confounded by a judge's context window
(the trap that produced a bogus 2.58 grounding baseline).

Services bind 127.0.0.1 on the T5810, so tunnel them first:

    ssh -f -N -L 6333:127.0.0.1:6333 -L 8005:127.0.0.1:8005 -L 8006:127.0.0.1:8006 \
        root@ai.cwetzel.com

Usage:
    python3 scripts/compare_retrieval.py --collections documents documents_c250 --top-k 5 8
"""
import argparse
import json
import sys
import urllib.request
from pathlib import Path

import yaml

GOLDEN = Path(__file__).resolve().parent.parent / "eval" / "golden_set.yaml"


def _post(url: str, payload: dict, timeout: float = 60.0) -> dict:
    req = urllib.request.Request(url, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def embed(embed_url: str, text: str) -> list:
    return _post(f"{embed_url}/embed", {"text": text})["embedding"]


def search(qdrant_url: str, collection: str, vector: list, limit: int) -> list:
    body = {"vector": vector, "limit": limit, "with_payload": True}
    res = _post(f"{qdrant_url}/collections/{collection}/points/search", body)["result"]
    return [{"content": p["payload"].get("content", ""),
             "title": p["payload"].get("title", ""),
             "source": p["payload"].get("source", ""),
             "cosine": p.get("score", 0.0)} for p in res]


def rerank(rerank_url: str, query: str, docs: list) -> list:
    """Return docs reordered by cross-encoder score. Mirrors the proxy: indices in, full docs out."""
    if not docs:
        return docs
    out = _post(f"{rerank_url}/rerank",
                {"query": query, "documents": [d["content"] for d in docs], "top_k": len(docs)})
    return [{**docs[r["index"]], "rerank": r["score"]} for r in out["results"]]


def cap_per_doc(ranked: list, top_k: int, max_per_doc: int = 1) -> list:
    """The proxy's RAG_MAX_PER_DOC: one chunk per source doc, so a long doc can't hog the top-k."""
    seen, kept = {}, []
    for d in ranked:
        key = d.get("title") or d.get("source")
        if seen.get(key, 0) >= max_per_doc:
            continue
        seen[key] = seen.get(key, 0) + 1
        kept.append(d)
        if len(kept) >= top_k:
            break
    return kept


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--collections", nargs="+", required=True, help="Qdrant collections to compare")
    ap.add_argument("--top-k", nargs="+", type=int, default=[5], help="top-k values to score")
    ap.add_argument("--max-per-doc", type=int, default=2,
                    help="chunks allowed from one source doc, matching the proxy's RAG_MAX_PER_DOC "
                         "(default 2 — the deployed value)")
    ap.add_argument("--retrieve-limit", type=int, default=15, help="candidates pulled before rerank")
    ap.add_argument("--qdrant-url", default="http://127.0.0.1:6333")
    ap.add_argument("--embed-url", default="http://127.0.0.1:8005")
    ap.add_argument("--rerank-url", default="http://127.0.0.1:8006")
    ap.add_argument("--golden", default=str(GOLDEN))
    args = ap.parse_args()

    items = [i for i in yaml.safe_load(open(args.golden))
             if i.get("kind", "grounded") == "grounded" and i.get("expect_substrings")]
    print(f"scoring {len(items)} grounded questions with expect_substrings as ground truth\n")

    results = {}
    for coll in args.collections:
        try:
            with urllib.request.urlopen(f"{args.qdrant_url}/collections/{coll}", timeout=15) as r:
                pts = json.loads(r.read().decode())["result"]["points_count"]
        except Exception as e:
            print(f"  ✗ collection '{coll}' unreachable: {e}")
            sys.exit(1)

        hits = {k: 0 for k in args.top_k}
        partial = {k: 0 for k in args.top_k}
        for it in items:
            vec = embed(args.embed_url, it["q"])
            cands = search(args.qdrant_url, coll, vec, args.retrieve_limit)
            ranked = rerank(args.rerank_url, it["q"], cands)
            for k in args.top_k:
                text = " ".join(d["content"] for d in cap_per_doc(ranked, k, args.max_per_doc)).lower()
                found = [s for s in it["expect_substrings"] if s.lower() in text]
                if len(found) == len(it["expect_substrings"]):
                    hits[k] += 1
                elif found:
                    partial[k] += 1

        results[coll] = {"points": pts, "hits": hits, "partial": partial}
        line = f"  {coll:22s} points={pts:5d}"
        for k in args.top_k:
            pct = 100 * hits[k] / len(items)
            line += f"   top{k}: {hits[k]}/{len(items)} ({pct:.0f}% full, {partial[k]} partial)"
        print(line)

    if len(args.collections) == 2:
        a, b = args.collections
        print("\n  delta (full-hit recall):")
        for k in args.top_k:
            d = results[b]["hits"][k] - results[a]["hits"][k]
            sign = "+" if d > 0 else ""
            print(f"    top{k}: {sign}{d} questions  ({b} vs {a})")
        print("\n  A larger top-k is not free: it raises the token budget the generator must fit.")


if __name__ == "__main__":
    main()
