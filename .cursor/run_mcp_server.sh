#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python resolution order:
# 1) MCP_PYTHON env var (explicit override)
# 2) active virtualenv python
# 3) python, then python3 from PATH
if [[ -n "${MCP_PYTHON:-}" ]]; then
  PYTHON_CMD="${MCP_PYTHON}"
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

mkdir -p "${SCRIPT_DIR}/.cache"

if [[ ! -d "${SCRIPT_DIR}/rag_db" ]]; then
  echo "rag_db not found in ${SCRIPT_DIR}/rag_db"
  echo "Build it first with: ./scripts/build_rag_db.sh"
  exit 1
fi

echo "Starting MCP server from ${SCRIPT_DIR}"
echo "Python: ${PYTHON_CMD}"

exec "${PYTHON_CMD}" "${SCRIPT_DIR}/mcp_server.py"
