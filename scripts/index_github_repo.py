#!/home/chris/miniforge3/bin/python3
"""
GitHub repo indexer for Qdrant RAG.
Fetches high-value files from a public GitHub repo, chunks them, embeds, and indexes.
Appends to existing Qdrant collection (does not drop/recreate).
"""

import requests
import json
import logging
import uuid
import re
from typing import List, Dict
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def fetch_repo_tree(repo: str) -> List[Dict]:
    """Fetch full recursive file tree from GitHub API."""
    url = f"https://api.github.com/repos/cdnwetzel/{repo}/git/trees/main?recursive=1"
    logger.info(f"Fetching repo tree from {url}...")

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            tree = resp.json().get("tree", [])
            logger.info(f"✓ Fetched {len(tree)} files from repo")
            return tree
        else:
            logger.error(f"✗ Failed to fetch tree: {resp.status_code}")
            return []
    except Exception as e:
        logger.error(f"✗ Error fetching repo tree: {e}")
        return []

def should_index(path: str, size: int) -> bool:
    """Filter to high-value files only."""
    # Include markdown docs
    if path.endswith('.md'):
        return True

    # Include kernel_config.sh (per-machine kernel option explanations)
    if path.endswith('kernel_config.sh'):
        return True

    # Include well-commented tools scripts
    if path.startswith('tools/') and path.endswith('.sh'):
        return True

    # Include shared scripts (cross-machine logic)
    if path.startswith('shared/') and path.endswith('.sh'):
        return True

    return False

def fetch_file_content(repo: str, path: str) -> str:
    """Fetch raw file content from GitHub."""
    url = f"https://raw.githubusercontent.com/cdnwetzel/{repo}/main/{path}"

    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return resp.text
        else:
            logger.warning(f"✗ Failed to fetch {path}: {resp.status_code}")
            return ""
    except Exception as e:
        logger.warning(f"✗ Error fetching {path}: {e}")
        return ""

def chunk_markdown(content: str, path: str) -> List[Dict]:
    """Split markdown by ## headings. Each chunk is one section with context."""
    chunks = []
    lines = content.split('\n')
    current_chunk = []
    current_heading = None

    for line in lines:
        if line.startswith('## '):
            # Save previous chunk if it exists
            if current_chunk and current_heading:
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text:  # Don't save empty chunks
                    chunks.append({
                        'heading': current_heading,
                        'content': f"{current_heading}\n\n{chunk_text}",
                        'file_type': 'markdown'
                    })

            # Start new chunk
            current_heading = line.lstrip('#').strip()
            current_chunk = []
        else:
            current_chunk.append(line)

    # Save final chunk
    if current_chunk and current_heading:
        chunk_text = '\n'.join(current_chunk).strip()
        if chunk_text:
            chunks.append({
                'heading': current_heading,
                'content': f"{current_heading}\n\n{chunk_text}",
                'file_type': 'markdown'
            })

    logger.info(f"  → {path}: {len(chunks)} markdown sections")
    return chunks

def chunk_shell(content: str, path: str) -> List[Dict]:
    """Split shell scripts by function definitions or === comment blocks."""
    chunks = []
    lines = content.split('\n')
    current_chunk = []
    current_section = "start"

    for line in lines:
        # Detect function definition
        if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*\(\)\s*{', line):
            # Save previous chunk
            if current_chunk:
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text and len(chunk_text) > 100:  # Only save substantial chunks
                    chunks.append({
                        'heading': current_section,
                        'content': chunk_text,
                        'file_type': 'shell'
                    })

            # Start new function chunk
            func_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)', line)
            current_section = func_match.group(1) if func_match else "unknown"
            current_chunk = [line]

        # Detect section markers (# ===)
        elif re.match(r'^#\s*={5,}', line):
            # Save previous chunk
            if current_chunk:
                chunk_text = '\n'.join(current_chunk).strip()
                if chunk_text and len(chunk_text) > 100:
                    chunks.append({
                        'heading': current_section,
                        'content': chunk_text,
                        'file_type': 'shell'
                    })

            # Start new section
            current_section = line.lstrip('#').replace('=', '').strip() or "section"
            current_chunk = [line]
        else:
            current_chunk.append(line)

    # Save final chunk
    if current_chunk:
        chunk_text = '\n'.join(current_chunk).strip()
        if chunk_text and len(chunk_text) > 100:
            chunks.append({
                'heading': current_section,
                'content': chunk_text,
                'file_type': 'shell'
            })

    logger.info(f"  → {path}: {len(chunks)} shell sections")
    return chunks

def load_repo_documents(repo: str) -> List[Dict]:
    """Fetch all indexable files from GitHub repo, chunk them."""
    tree = fetch_repo_tree(repo)
    docs = []

    for entry in tree:
        if entry['type'] != 'blob':
            continue

        path = entry['path']
        size = entry.get('size', 0)

        if not should_index(path, size):
            continue

        logger.info(f"Fetching {path}...")
        content = fetch_file_content(repo, path)

        if not content:
            continue

        # Choose chunking strategy
        if path.endswith('.md'):
            chunks = chunk_markdown(content, path)
        elif path.endswith('.sh'):
            chunks = chunk_shell(content, path)
        else:
            # Fallback to word-based chunking
            chunks = chunk_text(content, chunk_size=400, overlap=50)
            chunks = [{'heading': f"chunk_{i}", 'content': c, 'file_type': 'shell'} for i, c in enumerate(chunks)]

        for chunk in chunks:
            docs.append({
                'id': str(uuid.uuid4()),  # UUID string ID
                'title': f"{path}#{chunk['heading']}",
                'content': chunk['content'],
                'source': 'github_repo',
                'repo': repo,
                'file_path': path,
                'file_type': chunk['file_type'],
                'word_count': len(chunk['content'].split()),
            })

    logger.info(f"\n✓ Total: {len(docs)} chunks from {len(set(d['file_path'] for d in docs))} files")
    return docs

def chunk_text(text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
    """Fallback word-based chunking."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = ' '.join(words[i:i + chunk_size])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def index_documents(qdrant_url: str, embed_url: str, docs: List[Dict]):
    """Embed and upsert documents to Qdrant collection (appends, does not drop)."""
    if not docs:
        logger.warning("No documents to index")
        return False

    logger.info(f"\n=== Indexing {len(docs)} chunks to Qdrant ===")

    # Load embedding model on CPU — MUST match the live embed-service / main indexer
    # (bge-base-en-v1.5, 768-d). It appends to the existing `documents` collection, so a
    # different model/dim would be rejected or corrupt search.
    logger.info("Loading embedding model...")
    model = SentenceTransformer('BAAI/bge-base-en-v1.5', device='cpu')
    logger.info("✓ Model loaded")

    # Encode all contents
    contents = [doc['content'] for doc in docs]
    logger.info(f"Embedding {len(contents)} chunks...")
    embeddings = model.encode(contents, show_progress_bar=False)

    # Build Qdrant points
    points = []
    for doc, embedding in zip(docs, embeddings):
        points.append({
            'id': doc['id'],  # UUID string
            'vector': embedding.tolist(),  # 384-dim
            'payload': {
                'title': doc['title'],
                'content': doc['content'],
                'source': doc['source'],
                'repo': doc['repo'],
                'file_path': doc['file_path'],
                'file_type': doc['file_type'],
                'word_count': doc['word_count'],
            }
        })

    # Upsert to Qdrant (append, does NOT drop collection)
    logger.info(f"Uploading {len(points)} points to Qdrant...")

    try:
        resp = requests.put(
            f"{qdrant_url}/collections/documents/points",
            json={'points': points},
            timeout=60
        )

        if resp.status_code == 200:
            logger.info(f"✓ Indexed {len(points)} chunks")
            logger.info("✓ Appended to existing collection (did not drop)")
            return True
        else:
            logger.error(f"✗ Failed to index: {resp.status_code} {resp.text[:200]}")
            return False
    except Exception as e:
        logger.error(f"✗ Error indexing: {e}")
        return False

def main():
    qdrant_url = "http://localhost:6333"
    embed_url = "http://127.0.0.1:8005"
    repo = "gentoo-machines"

    logger.info(f"Qdrant: {qdrant_url}")
    logger.info(f"Repo: {repo}\n")

    docs = load_repo_documents(repo)

    if not docs:
        logger.error("✗ No documents loaded")
        return 1

    if index_documents(qdrant_url, embed_url, docs):
        logger.info("\n✅ GitHub repo indexed successfully!")
        logger.info("New chunks appended to existing RAG collection.")
        return 0
    else:
        logger.error("\n✗ Indexing failed")
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
