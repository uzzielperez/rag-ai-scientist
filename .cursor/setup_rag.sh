#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PYTHON_BIN="${PYTHON_BIN:-python}"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
  echo "Error: '${PYTHON_BIN}' not found. Activate your venv first (e.g. source ~/mcp_env/bin/activate)." >&2
  exit 1
fi

echo "Using Python: $(${PYTHON_BIN} -c 'import sys; print(sys.executable)')"
echo "Using pip: $(${PYTHON_BIN} -m pip -V)"

# Guard against accidental installs to read-only CVMFS Python.
if ${PYTHON_BIN} -m pip -V | grep -q "/cvmfs/"; then
  echo "Error: pip resolves to /cvmfs (read-only)." >&2
  echo "Activate a writable virtualenv first: source ~/mcp_env/bin/activate" >&2
  exit 1
fi

"${PYTHON_BIN}" -m pip install -r "${REPO_ROOT}/requirements.txt"
"${PYTHON_BIN}" -m pip install -r "${REPO_ROOT}/.cursor/requirements.txt"
"${PYTHON_BIN}" "${REPO_ROOT}/.cursor/index_documents.py"

echo "RAG setup complete."
