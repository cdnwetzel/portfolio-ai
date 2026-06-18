#!/home/chris/miniforge3/bin/python3
"""
Knowledge base indexer with semantic embeddings.
Generates real 384-dim vectors for each chunk using all-MiniLM-L6-v2.
No more manual weight tuning — semantic similarity handles relevance.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict
import requests
from sentence_transformers import SentenceTransformer
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Split text into overlapping chunks by words."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

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

def create_collection(qdrant_url: str, collection_name: str) -> bool:
    """Create Qdrant collection with 384-dim vectors for semantic search."""
    try:
        resp = requests.get(f"{qdrant_url}/collections/{collection_name}")
        if resp.status_code == 200:
            logger.info(f"✓ Collection '{collection_name}' already exists")
            return True
    except:
        pass

    try:
        payload = {
            "vectors": {
                "size": 384,  # all-MiniLM-L6-v2 produces 384-dim embeddings
                "distance": "Cosine",
            }
        }
        resp = requests.put(f"{qdrant_url}/collections/{collection_name}", json=payload)
        if resp.status_code == 200:
            logger.info(f"✓ Created collection '{collection_name}' with size 384")
            return True
        else:
            logger.error(f"✗ Failed to create collection: {resp.status_code}")
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

def index_documents(qdrant_url: str, docs: List[Dict], collection_name: str = "documents"):
    """Index documents as chunks with semantic embeddings."""
    logger.info(f"\n=== Indexing Documents with Semantic Embeddings ===")

    if not create_collection(qdrant_url, collection_name):
        return False

    # Load embedding model on CPU (vLLM is using GPU)
    logger.info("Loading all-MiniLM-L6-v2 embedding model (CPU)...")
    model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
    logger.info("✓ Model loaded on CPU")

    points = []
    point_id = 0
    total_chunks = 0

    for doc in docs:
        # Chunk the content
        chunks = chunk_text(doc['content'], chunk_size=400, overlap=50)
        total_chunks += len(chunks)

        # Batch encode all chunks for this document
        logger.info(f"Embedding {len(chunks)} chunks for {doc['title']}...")
        embeddings = model.encode(chunks, show_progress_bar=False)

        for chunk_idx, chunk in enumerate(chunks):
            embedding = embeddings[chunk_idx].tolist()

            points.append({
                "id": point_id,
                "vector": embedding,  # Real 384-dim semantic vector
                "payload": {
                    "doc_id": doc["id"],
                    "title": doc["title"],
                    "content": chunk,  # Full chunk text for reference
                    "source": doc["source"],
                    "chunk_index": chunk_idx,
                    "word_count": len(chunk.split()),
                    "impressions": doc.get("impressions", 0),
                }
            })
            point_id += 1

        logger.info(f"  → {doc['title']}: {len(chunks)} chunks → {len(chunks) * 384} vector dims")

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
            logger.info(f"✓ Total semantic vectors: {len(points) * 384:,} dimensions")
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
    args = parser.parse_args()

    logger.info(f"Qdrant URL: {args.qdrant_url}")
    logger.info(f"KB Path:    {args.kb_path}")
    logger.info(f"Collection: {args.collection}  (wipe={args.wipe})\n")

    docs = load_documents(args.kb_path)
    if not docs:
        logger.error("✗ No documents found")
        return 1

    logger.info(f"\n✓ Total: {len(docs)} documents\n")

    if args.wipe:
        wipe_collection(args.qdrant_url, args.collection)

    if index_documents(args.qdrant_url, docs, args.collection):
        logger.info("\n✅ Knowledge base indexed with semantic embeddings!")
        logger.info("RAG search now uses real vector similarity — no manual weight tuning needed.")
        return 0
    else:
        logger.error("\n✗ Indexing failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
