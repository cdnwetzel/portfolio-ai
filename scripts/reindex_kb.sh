#!/usr/bin/env bash
# Rebuild the production Qdrant `documents` collection from the repo's committed KB.
#
# This is the reproducibility guarantee for the vector index: the collection is
# derived data (embeddings of knowledge_base/), and this script regenerates
# it from committed source. Re-run any time to restore the index to match the repo —
# e.g. after editing KB docs, or to recover from Qdrant loss.
#
# Runs the embedder on the T5810 (same all-MiniLM-L6-v2 env as the live embed-service,
# so index vectors match query vectors) as the `chris` user (model cached there).
#
# Usage:  ./scripts/reindex_kb.sh
# Env:    T5810_HOST (default root@10.0.1.125)
set -euo pipefail

T5810="${T5810_HOST:-root@10.0.1.125}"
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO_KB="${HERE}/../knowledge_base"
REMOTE_KB="/tmp/knowledge_base"
REMOTE_INDEXER="/tmp/reindex_indexer.py"
REMOTE_SPARSE="/tmp/sparse_bm25.py"
PYTHON="/home/chris/miniforge3/bin/python3"
# HYBRID=1 builds a dense+BM25 collection (rag-improvements.md §2.1). The live proxy
# must run with HYBRID_SEARCH=1 to query it — coordinate the two (deploy + reindex).
HYBRID_FLAG=""; [ "${HYBRID:-0}" = "1" ] && HYBRID_FLAG="--hybrid"

echo "==> Syncing committed KB -> ${T5810}:${REMOTE_KB} (--delete purges stale/removed docs)"
rsync -avz --delete "${REPO_KB}/" "${T5810}:${REMOTE_KB}/"

echo "==> Copying indexer (+ sparse_bm25 for hybrid)"
ssh "${T5810}" "rm -f ${REMOTE_INDEXER} ${REMOTE_SPARSE}"
scp -q "${HERE}/index_with_embeddings.py" "${T5810}:${REMOTE_INDEXER}"
scp -q "${HERE}/../cloud/sparse_bm25.py"  "${T5810}:${REMOTE_SPARSE}"

echo "==> Rebuilding Qdrant 'documents' collection (wipe + reindex from committed source; hybrid=${HYBRID:-0})"
ssh "${T5810}" "chmod -R a+r ${REMOTE_KB} ${REMOTE_INDEXER} ${REMOTE_SPARSE} && \
  su - chris -c '${PYTHON} ${REMOTE_INDEXER} --kb-path ${REMOTE_KB} \
    --qdrant-url http://localhost:6333 --collection documents --wipe ${HYBRID_FLAG}'"

echo "==> Done. Live index now matches knowledge_base/."
