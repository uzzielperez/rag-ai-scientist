# Local `.cursor` assets

This directory contains the Cursor-facing runtime for local RAG and MCP tools.

## Quickstart

```bash
python .cursor/index_documents.py --force
bash .cursor/run_mcp_server.sh
```

## Core files

- `index_documents.py`
  - Wrapper around `rag/index_documents.py`.
  - Uses `configs/references.yaml` (fallback: `references.example.yaml`).
- `mcp_server.py`
  - MCP stdio server with tools:
    - `query_analysis_knowledge`
    - `search_papers`
    - `retrieve_documents`
    - `get_skill`
  - Also exposes skill markdown as MCP resources (`skill://...`).
- `run_mcp_server.sh`
  - Launches MCP server with project-local caches.
  - Loads `.env` if present.
- `ingest.py`
  - Appends curated notes into Chroma without full reindex.
- `visualize_rag.py`
  - 2D projections (UMAP/t-SNE/PCA) of embedding space.

## Embedding model

- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Used for indexing, retrieval, and ingestion consistency.
- Cached under:
  - `.cursor/.cache/huggingface`
  - `.cursor/.cache/torch`

## Environment

Use `.env.example` as a template:

- `GROQ_API_KEY` enables LLM-backed responses in `query_analysis_knowledge`
- without it, the server falls back to extractive retrieval output
- `RAG_COLLECTION_NAME` can override the default collection name

## Skills

- `skills/rag-setup/SKILL.md` for environment + indexing setup
- `skills/an-pipeline-runner/` for stepwise analysis execution
- `skills/an-validation/` for report generation/publishing
- `skills/ap-starterkit-execution/SKILL.md` for AP starterkit workflows
- `skills/_template/SKILL.md` for creating custom workflow skills
