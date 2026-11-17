#!/home/chris/miniforge3/bin/python3
"""
Index linux_sysadmin_background.md to Qdrant.
Uses embed service on port 8005 for embeddings.
"""

import requests
import json
import uuid

qdrant_url = "http://localhost:6333"
embed_url = "http://127.0.0.1:8005"

# Load document
with open("/tmp/linux_sysadmin_background.md") as f:
    content = f.read()

# Chunk by ## heading
chunks = []
lines = content.split('\n')
current_heading = None
current_chunk = []

for line in lines:
    if line.startswith('## '):
        # Save previous chunk
        if current_chunk and current_heading:
            chunk_text = '\n'.join(current_chunk).strip()
            if chunk_text:
                chunks.append({
                    'heading': current_heading,
                    'content': f"{current_heading}\n\n{chunk_text}",
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
        })

print(f"✓ Chunked into {len(chunks)} sections")

# Embed via service
print(f"Embedding {len(chunks)} chunks via service...")
embeddings = []
for i, chunk in enumerate(chunks):
    try:
        resp = requests.post(
            f"{embed_url}/embed",
            json={"text": chunk['content']},
            timeout=10
        )
        if resp.status_code == 200:
            embedding = resp.json()["embedding"]
            embeddings.append(embedding)
            print(f"  {i+1}/{len(chunks)} embedded")
        else:
            print(f"✗ Embedding failed for chunk {i}: {resp.status_code}")
            embeddings.append(None)
    except Exception as e:
        print(f"✗ Error embedding chunk {i}: {e}")
        embeddings.append(None)

valid_chunks = [c for c, e in zip(chunks, embeddings) if e is not None]
valid_embeddings = [e for e in embeddings if e is not None]

print(f"✓ Successfully embedded {len(valid_embeddings)}/{len(chunks)} chunks")

# Build Qdrant points
points = []
for chunk, embedding in zip(valid_chunks, valid_embeddings):
    points.append({
        'id': str(uuid.uuid4()),
        'vector': embedding,
        'payload': {
            'title': f"linux_sysadmin_background.md#{chunk['heading']}",
            'content': chunk['content'],
            'source': 'knowledge_base',
            'file_path': 'case_studies/linux_sysadmin_background.md',
            'file_type': 'markdown',
            'word_count': len(chunk['content'].split()),
        }
    })

# Upsert to Qdrant
print(f"Uploading {len(points)} points to Qdrant...")
try:
    resp = requests.put(
        f"{qdrant_url}/collections/documents/points",
        json={'points': points},
        timeout=60
    )
    if resp.status_code == 200:
        print(f"✓ Indexed {len(points)} chunks")
        print(f"✓ Added to documents collection")
    else:
        print(f"✗ Failed: {resp.status_code}")
        print(resp.text[:200])
except Exception as e:
    print(f"✗ Error: {e}")
