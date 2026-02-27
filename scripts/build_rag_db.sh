#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REF_CONFIG="${REPO_ROOT}/configs/references.yaml"
if [[ ! -f "${REF_CONFIG}" ]]; then
  REF_CONFIG="${REPO_ROOT}/configs/references.example.yaml"
fi

python "${REPO_ROOT}/rag/index_documents.py" \
  --config "${REF_CONFIG}" \
  --output-dir "${REPO_ROOT}/.cursor/rag_db"

echo "RAG database built at ${REPO_ROOT}/.cursor/rag_db"
