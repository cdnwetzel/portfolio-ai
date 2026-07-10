#!/home/chris/miniforge3/bin/python3
"""
Knowledge base indexer with semantic embeddings.
Generates real 768-dim vectors for each chunk using BAAI/bge-base-en-v1.5.
No more manual weight tuning — semantic similarity handles relevance.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import List, Dict
import logging

# Heavy/optional deps imported lazily so the pure chunking logic below is importable
# (and unit-testable) on a machine without them. They ARE present in the T5810 indexer env.
try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def _load_sparse_module():
    """Import sparse_bm25 (shared with the proxy). It is copied next to this indexer on
    the T5810 by reindex_kb.sh; also try the repo's cloud/ dir for local runs."""
    import importlib
    here = Path(__file__).resolve().parent
    for p in (str(here), str(here.parent / "cloud")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        return importlib.import_module("sparse_bm25")
    except Exception as e:
        logger.error(f"sparse_bm25 import failed: {e}")
        return None


_HEADER_RE = re.compile(r'^#{1,6}\s')


def _split_sections(text: str) -> List[str]:
    """Split markdown into sections at header lines (#..######). Each section starts at
    its header and runs to the next header; any preamble before the first header is its
    own section. Keeps a header attached to its body for cleaner embeddings + citations."""
    sections, current = [], []
    for line in text.split('\n'):
        if _HEADER_RE.match(line) and current:
            sections.append('\n'.join(current))
            current = [line]
        else:
            current.append(line)
    if current:
        sections.append('\n'.join(current))
    return sections


def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Structure-aware chunking (rag-improvements.md §2.2).

    Prefer to break at markdown section headers, but GREEDILY MERGE consecutive small
    sections up to ~chunk_size words so we don't emit tiny one-paragraph fragments
    (splitting on every header over-fragments — measured 293 vs ~65 chunks with flat
    grounding and worse citation). A section larger than chunk_size on its own falls
    back to the original overlapping word-window split. Net: chunks sized like the
    blind 400-word window, but aligned to section boundaries."""
    chunks: List[str] = []
    buf_texts: List[str] = []
    buf_words = 0

    def flush():
        nonlocal buf_texts, buf_words
        if buf_texts:
            merged = "\n\n".join(buf_texts).strip()
            if merged:
                chunks.append(merged)
        buf_texts, buf_words = [], 0

    for section in _split_sections(text):
        words = section.split()
        n = len(words)
        if n == 0:
            continue
        if n > chunk_size:
            # Large section: flush any pending merge, then window-split this section.
            flush()
            for i in range(0, n, chunk_size - overlap):
                window = words[i:i + chunk_size]
                if window:
                    chunks.append(' '.join(window))
            continue
        # Small/medium section: start a new chunk if adding this would overflow.
        if buf_texts and buf_words + n > chunk_size:
            flush()
        buf_texts.append(section.strip())
        buf_words += n
    flush()
    return [c for c in chunks if c.strip()]

def load_documents(kb_path: str) -> List[Dict]:
    """Load all knowledge base documents."""
    docs = []
    kb_dir = Path(kb_path)

    # Load posts from metadata
    metadata_file = kb_dir / "POSTS_METADATA.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            posts = json.load(f).get('posts', [])
            for post in posts[:10]:  # Top 10 posts by impressions
                post_file = kb_dir / post.get('file', '')
                if post_file.exists():
                    with open(post_file) as pf:
                        content = pf.read()
                        docs.append({
                            "id": f"post_{post['rank']}",
                            "title": post.get('title', 'Untitled'),
                            "content": content,
                            "source": "linkedin_post",
                            "impressions": post.get('impressions', 0),
                        })
                        logger.info(f"✓ Loaded post: {post.get('title', 'Untitled')} ({post.get('impressions', 0)} impressions)")

    # Load case studies
    case_studies_dir = kb_dir / "case_studies"
    if case_studies_dir.exists():
        for cs_file in sorted(case_studies_dir.glob("*.md")):
            with open(cs_file) as f:
                content = f.read()
                title = cs_file.stem.replace("_", " ").title()
                docs.append({
                    "id": f"case_{cs_file.stem}",
                    "title": title,
                    "content": content,
                    "source": "case_study",
                })
                logger.info(f"✓ Loaded case study: {title}")

    # Load infrastructure docs (and any other subdirectories of .md files)
    for subdir in sorted(kb_dir.iterdir()):
        if not subdir.is_dir() or subdir.name in ("case_studies", "posts", "pxx_docs"):
            continue
        for md_file in sorted(subdir.glob("*.md")):
            with open(md_file) as f:
                content = f.read()
                title = md_file.stem.replace("_", " ").title()
                docs.append({
                    "id": f"{subdir.name}_{md_file.stem}",
                    "title": title,
                    "content": content,
                    "source": subdir.name,
                })
                logger.info(f"✓ Loaded {subdir.name}/{md_file.name}: {title}")

    # Load top-level .md files (except RESUME which is handled separately)
    for md_file in sorted(kb_dir.glob("*.md")):
        if md_file.name in ("RESUME.md", "INDEX.md"):
            continue
        with open(md_file) as f:
            content = f.read()
            title = md_file.stem.replace("_", " ").title()
            docs.append({
                "id": f"doc_{md_file.stem}",
                "title": title,
                "content": content,
                "source": "knowledge_base",
            })
            logger.info(f"✓ Loaded {md_file.name}: {title}")

    # Load resume
    resume_file = kb_dir / "RESUME.md"
    if resume_file.exists():
        with open(resume_file) as f:
            docs.append({
                "id": "resume",
                "title": "Resume - Chris Wetzel",
                "content": f.read(),
                "source": "resume",
            })
            logger.info(f"✓ Loaded resume")

    # Load PROFESSIONAL_CONTEXT
    prof_context = kb_dir.parent / "PROFESSIONAL_CONTEXT.md"
    if prof_context.exists():
        with open(prof_context) as f:
            docs.append({
                "id": "professional_context",
                "title": "Professional Context & Positioning",
                "content": f.read(),
                "source": "context",
            })
            logger.info(f"✓ Loaded professional context")

    return docs

def create_collection(qdrant_url: str, collection_name: str, hybrid: bool = False) -> bool:
    """Create the Qdrant collection.

    Dense-only (default): unnamed 768-d cosine vector (current production schema).
    Hybrid (rag-improvements.md §2.1): NAMED 'dense' (768-d cosine) + a 'bm25' sparse
    vector, for dense+sparse fusion via the Query API. NOTE: hybrid uses named vectors,
    which the proxy must query differently — a coordinated schema migration."""
    try:
        resp = requests.get(f"{qdrant_url}/collections/{collection_name}")
        if resp.status_code == 200:
            logger.info(f"✓ Collection '{collection_name}' already exists")
            return True
    except:
        pass

    try:
        if hybrid:
            payload = {
                "vectors": {"dense": {"size": 768, "distance": "Cosine"}},
                "sparse_vectors": {"bm25": {}},
            }
        else:
            payload = {"vectors": {"size": 768, "distance": "Cosine"}}
        resp = requests.put(f"{qdrant_url}/collections/{collection_name}", json=payload)
        if resp.status_code == 200:
            logger.info(f"✓ Created collection '{collection_name}' ({'hybrid dense+bm25' if hybrid else 'dense 768'})")
            return True
        else:
            logger.error(f"✗ Failed to create collection: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"✗ Error creating collection: {e}")
        return False


def wipe_collection(qdrant_url: str, collection_name: str) -> None:
    """Delete the collection so the next create_collection rebuilds it from scratch.
    Use before a full rebuild to clear orphan points left by partial/targeted
    re-indexes (e.g. hand-patched chunks with custom IDs), so the result is byte-for-byte
    what a clean indexer run produces from committed source."""
    try:
        resp = requests.delete(f"{qdrant_url}/collections/{collection_name}", timeout=30)
        logger.info(f"✓ Wiped collection '{collection_name}' (status {resp.status_code})")
    except Exception as e:
        logger.error(f"✗ Error wiping collection: {e}")

def index_documents(qdrant_url: str, docs: List[Dict], collection_name: str = "documents",
                    hybrid: bool = False, chunk_size: int = 400, overlap: int = 50):
    """Index documents as chunks with semantic embeddings (+ BM25 sparse vectors if hybrid).

    chunk_size is in WORDS. The default 400 was chosen for the bi-encoder, which has no length
    limit worth worrying about; note it tokenizes to a ~640-token median, while the cross-encoder
    reranker truncates each (query, chunk) pair at 512 tokens. Exposed so a parallel collection can
    be built at a different size and compared, rather than guessed at.
    """
    logger.info(f"\n=== Indexing Documents ({'hybrid dense+bm25' if hybrid else 'dense'}) ===")

    if not create_collection(qdrant_url, collection_name, hybrid=hybrid):
        return False

    # Load embedding model on CPU (vLLM is using GPU)
    from sentence_transformers import SentenceTransformer  # lazy: heavy dep, T5810-only
    logger.info("Loading BAAI/bge-base-en-v1.5 embedding model (CPU)...")
    model = SentenceTransformer('BAAI/bge-base-en-v1.5', device='cpu')
    logger.info("✓ Model loaded on CPU")

    # Pass 1: chunk every doc. For hybrid, tokenize all chunks first to build corpus IDF.
    sp = None
    idf = avgdl = None
    chunked = []  # list of (doc, [chunks])
    for doc in docs:
        chunks = chunk_text(doc['content'], chunk_size=chunk_size, overlap=overlap)
        chunked.append((doc, chunks))

    if hybrid:
        sp = _load_sparse_module()
        if sp is None:
            logger.error("✗ --hybrid requested but sparse_bm25 module not importable")
            return False
        corpus_tokens = [sp.tokenize(c) for _, chunks in chunked for c in chunks]
        idf, avgdl = sp.build_idf(corpus_tokens)
        logger.info(f"✓ BM25 IDF over {len(corpus_tokens)} chunks (avgdl={avgdl:.1f})")

    points = []
    point_id = 0

    for doc, chunks in chunked:
        logger.info(f"Embedding {len(chunks)} chunks for {doc['title']}...")
        embeddings = model.encode(chunks, show_progress_bar=False)

        for chunk_idx, chunk in enumerate(chunks):
            embedding = embeddings[chunk_idx].tolist()
            payload = {
                "doc_id": doc["id"], "title": doc["title"], "content": chunk,
                "source": doc["source"], "chunk_index": chunk_idx,
                "word_count": len(chunk.split()), "impressions": doc.get("impressions", 0),
            }
            if hybrid:
                sparse = sp.encode_doc(sp.tokenize(chunk), idf, avgdl)
                vector = {"dense": embedding, "bm25": sparse}
            else:
                vector = embedding
            points.append({"id": point_id, "vector": vector, "payload": payload})
            point_id += 1

        logger.info(f"  → {doc['title']}: {len(chunks)} chunks")

    # Upload all points
    try:
        logger.info(f"Uploading {len(points)} points to Qdrant...")
        resp = requests.put(
            f"{qdrant_url}/collections/{collection_name}/points",
            json={"points": points},
            timeout=60
        )
        if resp.status_code == 200:
            logger.info(f"✓ Indexed {len(points)} chunks across {len(docs)} documents")
            logger.info(f"✓ Total semantic vectors: {len(points) * 768:,} dimensions")
            return True
        else:
            logger.error(f"✗ Failed to index: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"✗ Error indexing: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Index the knowledge base into Qdrant with semantic embeddings. "
                    "Point --kb-path at the repo's knowledge_base for a rebuild from committed source."
    )
    parser.add_argument("--kb-path", default="/tmp/knowledge_base",
                        help="Path to the knowledge_base directory (default: /tmp/knowledge_base)")
    parser.add_argument("--qdrant-url", default="http://localhost:6333",
                        help="Qdrant base URL (default: http://localhost:6333)")
    parser.add_argument("--collection", default="documents",
                        help="Qdrant collection name (default: documents)")
    parser.add_argument("--wipe", action="store_true",
                        help="Delete and rebuild the collection from scratch — recommended for a clean, "
                             "reproducible rebuild (clears orphan points from prior targeted re-indexes)")
    parser.add_argument("--chunk-size", type=int, default=400,
                        help="Chunk size in WORDS (default: 400). The reranker truncates a "
                             "(query, chunk) pair at 512 tokens; 400 words is a ~640-token median.")
    parser.add_argument("--overlap", type=int, default=50,
                        help="Chunk overlap in words (default: 50)")
    parser.add_argument("--hybrid", action="store_true",
                        help="Build a hybrid dense+BM25-sparse collection (named 'dense' + 'bm25' "
                             "sparse vectors). Requires a proxy that queries via the fusion API.")
    args = parser.parse_args()

    logger.info(f"Qdrant URL: {args.qdrant_url}")
    logger.info(f"KB Path:    {args.kb_path}")
    logger.info(f"Collection: {args.collection}  (wipe={args.wipe}, hybrid={args.hybrid})\n")

    docs = load_documents(args.kb_path)
    if not docs:
        logger.error("✗ No documents found")
        return 1

    logger.info(f"\n✓ Total: {len(docs)} documents\n")

    if args.wipe:
        wipe_collection(args.qdrant_url, args.collection)

    if index_documents(args.qdrant_url, docs, args.collection, hybrid=args.hybrid,
                       chunk_size=args.chunk_size, overlap=args.overlap):
        logger.info("\n✅ Knowledge base indexed with semantic embeddings!")
        logger.info("RAG search now uses real vector similarity — no manual weight tuning needed.")
        return 0
    else:
        logger.error("\n✗ Indexing failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
