#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_PYTHON="/afs/cern.ch/user/c/ciperez/mcp_env/bin/python"

if [[ -x "${MCP_PYTHON}" ]]; then
  PYTHON_CMD="${MCP_PYTHON}"
else
  PYTHON_CMD="python3"
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
