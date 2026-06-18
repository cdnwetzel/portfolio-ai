#!/usr/bin/env python3
"""
Simple knowledge base indexing to Qdrant (no ML models).
Just stores documents with basic payload for search.
"""

import json
import sys
from pathlib import Path
import requests

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
                    "content": post.get("content", "")[:500],
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
                    "content": content[:500],
                    "source": "case_study",
                })
        print(f"✓ Loaded case studies")

    # Load resume
    resume_file = kb_dir / "RESUME.md"
    if resume_file.exists():
        with open(resume_file) as f:
            docs.append({
                "id": "resume",
                "title": "Resume - Chris Wetzel",
                "content": f.read()[:500],
                "source": "resume",
            })
        print(f"✓ Loaded resume")

    return docs


def create_collection(qdrant_url: str, collection_name: str) -> bool:
    """Create Qdrant collection."""
    try:
        resp = requests.get(f"{qdrant_url}/collections/{collection_name}")
        if resp.status_code == 200:
            print(f"✓ Collection '{collection_name}' already exists")
            return True
    except:
        pass

    # Create simple point-based collection
    try:
        payload = {
            "vectors": {
                "size": 1,
                "distance": "Cosine",
            }
        }
        resp = requests.put(f"{qdrant_url}/collections/{collection_name}", json=payload)
        if resp.status_code == 200:
            print(f"✓ Created collection '{collection_name}'")
            return True
        else:
            print(f"✗ Failed to create collection: {resp.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error creating collection: {e}")
        return False


def index_documents(qdrant_url: str, docs: list, collection_name: str = "documents"):
    """Index documents to Qdrant."""
    print(f"\n=== Indexing {len(docs)} Documents ===")

    if not create_collection(qdrant_url, collection_name):
        return False

    # Create simple vector (just hash of content)
    points = []
    for idx, doc in enumerate(docs):
        # Create a simple vector from content hash
        vector = [float(hash(doc['content']) % 1000) / 1000]

        points.append({
            "id": idx,
            "vector": vector,
            "payload": {
                "doc_id": doc["id"],
                "title": doc["title"],
                "content": doc["content"],
                "source": doc["source"],
                "impressions": doc.get("impressions", 0),
            }
        })

    # Upload all points
    try:
        resp = requests.put(
            f"{qdrant_url}/collections/{collection_name}/points",
            json={"points": points}
        )
        if resp.status_code == 200:
            print(f"✓ Indexed {len(docs)} documents")
            return True
        else:
            print(f"✗ Failed to index: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"✗ Error indexing: {e}")
        return False


def main():
    qdrant_url = "http://ai.cwetzel.com:6333"
    kb_path = "knowledge_base"

    print(f"Qdrant URL: {qdrant_url}")
    print(f"KB Path: {kb_path}\n")

    docs = load_documents(kb_path)
    if not docs:
        print("✗ No documents found")
        return 1

    print(f"✓ Total: {len(docs)} documents\n")

    if index_documents(qdrant_url, docs, "documents"):
        print("\n✅ Knowledge base indexed successfully!")
        return 0
    else:
        print("\n✗ Indexing failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
