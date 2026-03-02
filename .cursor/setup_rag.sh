#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 -m pip install -r "${REPO_ROOT}/requirements.txt"
python3 -m pip install -r "${REPO_ROOT}/.cursor/requirements.txt"
python3 "${REPO_ROOT}/.cursor/index_documents.py"

echo "RAG setup complete."
