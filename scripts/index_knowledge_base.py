#!/usr/bin/env python3
"""
Index Portfolio AI knowledge base to Qdrant vector database.
Documents: 28 LinkedIn posts + 5 case studies + resume
Embedding model: BAAI/bge-small-en-v1.5 (384 dims)
"""

import json
import os
import sys
from pathlib import Path
from typing import Optional
import argparse

try:
    import requests
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("Installing dependencies...")
    os.system("pip install -q requests sentence-transformers")
    import requests
    from sentence_transformers import SentenceTransformer


def load_documents(kb_path: str) -> list:
    """Load all knowledge base documents."""
    docs = []
    kb_dir = Path(kb_path)

    # Load metadata (posts)
    metadata_file = kb_dir / "POSTS_METADATA.json"
    if metadata_file.exists():
        with open(metadata_file) as f:
            posts = json.load(f)
            for post in posts:
                docs.append({
                    "id": f"post_{post['id']}",
                    "title": post.get("title", "Untitled"),
                    "content": post.get("content", ""),
                    "source": "linkedin_post",
                    "impressions": post.get("impressions", 0),
                })
        print(f"✓ Loaded {len(posts)} LinkedIn posts")

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
        print(f"✓ Loaded {case_studies_dir.glob('*.md').__sizeof__()} case studies")

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
        print(f"✓ Loaded resume")

    return docs


def create_collection(qdrant_url: str, collection_name: str, vector_size: int = 384) -> bool:
    """Create Qdrant collection if it doesn't exist."""
    try:
        resp = requests.get(f"{qdrant_url}/collections/{collection_name}")
        if resp.status_code == 200:
            print(f"✓ Collection '{collection_name}' already exists")
            return True
    except Exception as e:
        print(f"Warning: Could not check collection: {e}")

    # Create collection
    try:
        payload = {
            "vectors": {
                "size": vector_size,
                "distance": "Cosine",
            }
        }
        resp = requests.put(
            f"{qdrant_url}/collections/{collection_name}",
            json=payload
        )
        if resp.status_code == 200:
            print(f"✓ Created collection '{collection_name}'")
            return True
        else:
            print(f"✗ Failed to create collection: {resp.status_code} {resp.text}")
            return False
    except Exception as e:
        print(f"✗ Error creating collection: {e}")
        return False


def index_documents(qdrant_url: str, docs: list, collection_name: str = "documents"):
    """Index documents to Qdrant."""
    print("\n=== Indexing Documents ===")

    # Load embedding model
    print("Loading embedding model (BAAI/bge-small-en-v1.5)...")
    model = SentenceTransformer("BAAI/bge-small-en-v1.5")

    # Create collection
    if not create_collection(qdrant_url, collection_name):
        return False

    # Index documents in batches
    batch_size = 10
    total = len(docs)

    for i in range(0, total, batch_size):
        batch = docs[i : i + batch_size]
        points = []

        for idx, doc in enumerate(batch):
            point_id = i + idx
            # Combine title and content for embedding
            text = f"{doc['title']}\n{doc['content'][:1000]}"  # Limit to first 1000 chars
            embedding = model.encode(text, normalize_embeddings=True).tolist()

            points.append({
                "id": point_id,
                "vector": embedding,
                "payload": {
                    "doc_id": doc["id"],
                    "title": doc["title"],
                    "source": doc["source"],
                    "impressions": doc.get("impressions", 0),
                }
            })

        # Upload batch
        try:
            resp = requests.put(
                f"{qdrant_url}/collections/{collection_name}/points",
                json={"points": points}
            )
            if resp.status_code == 200:
                print(f"✓ Indexed {min(batch_size, total - i)}/{total} documents")
            else:
                print(f"✗ Failed to index batch: {resp.status_code}")
        except Exception as e:
            print(f"✗ Error indexing batch: {e}")
            return False

    print(f"\n✓ Indexed {total} documents to Qdrant")
    return True


def main():
    parser = argparse.ArgumentParser(description="Index knowledge base to Qdrant")
    parser.add_argument("--qdrant-url", default="http://ai.cwetzel.com:6333", help="Qdrant URL")
    parser.add_argument("--kb-path", default="src/data/knowledge_base", help="Knowledge base path")
    parser.add_argument("--collection", default="documents", help="Collection name")
    args = parser.parse_args()

    print(f"Qdrant URL: {args.qdrant_url}")
    print(f"KB Path: {args.kb_path}")
    print(f"Collection: {args.collection}\n")

    # Load documents
    docs = load_documents(args.kb_path)
    if not docs:
        print("✗ No documents found")
        return 1

    print(f"✓ Loaded {len(docs)} total documents\n")

    # Index to Qdrant
    if index_documents(args.qdrant_url, docs, args.collection):
        print("\n✅ Knowledge base indexing complete!")
        return 0
    else:
        print("\n✗ Indexing failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
