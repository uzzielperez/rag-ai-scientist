# Local .cursor assets for rag-ai-scientist

This directory contains the Cursor-facing RAG and MCP entrypoints for this repo.

## Minimal usage

```bash
# Build local RAG DB
python .cursor/index_documents.py

# Start MCP server
bash .cursor/run_mcp_server.sh
```

## Files

- `mcp_server.py`: minimal MCP server over `.cursor/rag_db`
- `run_mcp_server.sh`: launcher script
- `index_documents.py`: wrapper around `rag/index_documents.py`
- `ingest_sources.py`: alias to keep legacy command names
- `setup_rag.sh`: install deps + build db
- `requirements.txt`: MCP-side dependencies
