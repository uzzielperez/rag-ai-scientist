# RAG Vector Database

This project uses a local vector DB under `.cursor/rag_db/`.

## Build index

```bash
./scripts/build_rag_db.sh
```

Equivalent direct command:

```bash
python .cursor/index_documents.py --force
```

If `configs/references.yaml` does not exist, it falls back to `configs/references.example.yaml`.

## Query index

Use MCP server tools for querying:

```bash
bash .cursor/run_mcp_server.sh
```

In Cursor, call one of:

- `query_analysis_knowledge`
- `search_papers`
- `retrieve_documents`

## Regeneration workflow

1. Update reference paths in `configs/references.yaml`.
2. Rebuild with `./scripts/build_rag_db.sh`.
3. Start MCP with `bash .cursor/run_mcp_server.sh`.
4. Validate retrieval with MCP tools.

## Stored artifacts

- ChromaDB files (for example: `chroma.sqlite3`, index segment directories)
- Optional `ingest_log.jsonl` for curated ingested notes

## Notes

- The current backend is Chroma + Hugging Face embeddings.
- Collection name is configurable via `configs/references.yaml` (`indexing.collection_name`).
