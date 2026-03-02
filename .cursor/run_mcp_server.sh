#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ==============================================
# Cache configuration
# ==============================================
CACHE_DIR="${SCRIPT_DIR}/.cache"
mkdir -p "${CACHE_DIR}/huggingface" "${CACHE_DIR}/torch" "${CACHE_DIR}/chroma"

# Keep model caches local to this project.
export HF_HOME="${CACHE_DIR}/huggingface"
export SENTENCE_TRANSFORMERS_HOME="${CACHE_DIR}/huggingface"
export TORCH_HOME="${CACHE_DIR}/torch"
export CHROMA_CACHE_DIR="${CACHE_DIR}/chroma"
export HF_HUB_DISABLE_TELEMETRY=1
export TOKENIZERS_PARALLELISM=false

echo "================================================"
echo "Starting RAG MCP Server"
echo "================================================"
echo "Cache directory: ${CACHE_DIR}"

# Load project-local environment variables if present.
if [[ -f "${SCRIPT_DIR}/.env" ]]; then
  echo "Loading environment from .env..."
  set -a
  # shellcheck disable=SC1091
  source "${SCRIPT_DIR}/.env"
  set +a
fi

# Python resolution order:
# 1) MCP_PYTHON env var (explicit override)
# 2) dedicated default venv for this user
# 3) active virtualenv python
# 4) python, then python3 from PATH
DEFAULT_MCP_PYTHON="/afs/cern.ch/user/c/ciperez/mcp_env/bin/python"
if [[ -n "${MCP_PYTHON:-}" ]]; then
  PYTHON_CMD="${MCP_PYTHON}"
elif [[ -x "${DEFAULT_MCP_PYTHON}" ]]; then
  PYTHON_CMD="${DEFAULT_MCP_PYTHON}"
  echo "Using MCP virtual environment..."
elif [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
  PYTHON_CMD="${VIRTUAL_ENV}/bin/python"
elif command -v python >/dev/null 2>&1; then
  PYTHON_CMD="$(command -v python)"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD="$(command -v python3)"
else
  echo "Error: no Python interpreter found." >&2
  echo "Activate a venv first (e.g. source ~/mcp_env/bin/activate)." >&2
  exit 1
fi

if [[ ! -d "${SCRIPT_DIR}/rag_db" ]]; then
  echo ""
  echo "Error: rag_db not found at ${SCRIPT_DIR}/rag_db"
  echo "Build it first with: ./scripts/build_rag_db.sh"
  echo ""
  exit 1
fi

echo ""
echo "Server directory: ${SCRIPT_DIR}"
echo "Python: ${PYTHON_CMD}"
echo ""
echo "Starting MCP server..."
echo "================================================"

cd "${SCRIPT_DIR}"
exec "${PYTHON_CMD}" "${SCRIPT_DIR}/mcp_server.py"
