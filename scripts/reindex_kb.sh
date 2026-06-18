#!/usr/bin/env bash
# Rebuild the production Qdrant `documents` collection from the repo's committed KB.
#
# This is the reproducibility guarantee for the vector index: the collection is
# derived data (embeddings of src/data/knowledge_base/), and this script regenerates
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
REPO_KB="${HERE}/../src/data/knowledge_base"
REMOTE_KB="/tmp/knowledge_base"
REMOTE_INDEXER="/tmp/reindex_indexer.py"
PYTHON="/home/chris/miniforge3/bin/python3"

echo "==> Syncing committed KB -> ${T5810}:${REMOTE_KB} (--delete purges stale/removed docs)"
rsync -avz --delete "${REPO_KB}/" "${T5810}:${REMOTE_KB}/"

echo "==> Copying indexer"
ssh "${T5810}" "rm -f ${REMOTE_INDEXER}"
scp -q "${HERE}/index_with_embeddings.py" "${T5810}:${REMOTE_INDEXER}"

echo "==> Rebuilding Qdrant 'documents' collection (wipe + reindex from committed source)"
ssh "${T5810}" "chmod -R a+r ${REMOTE_KB} ${REMOTE_INDEXER} && \
  su - chris -c '${PYTHON} ${REMOTE_INDEXER} --kb-path ${REMOTE_KB} \
    --qdrant-url http://localhost:6333 --collection documents --wipe'"

echo "==> Done. Live index now matches src/data/knowledge_base/."
