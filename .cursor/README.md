# Local .cursor assets for rag-ai-scientist

This directory contains the Cursor-facing RAG and MCP entrypoints for this repo.

## Minimal usage

```bash
# Build local RAG DB
python .cursor/index_documents.py --force

# Start MCP server
bash .cursor/run_mcp_server.sh
```

## Embedding model (explicit)

This path now uses a Hugging Face sentence embedding model:

- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Where used:
  - `rag/index_documents.py`: converts each text chunk into semantic vectors and writes them into Chroma (`.cursor/rag_db`)
  - `.cursor/mcp_server.py`: embeds user queries with the same model to do nearest-neighbor retrieval
- First-time download:
  - Triggered when embeddings are initialized (indexing or server startup if cache is empty)
- Cache location (when started via `run_mcp_server.sh`):
  - `.cursor/.cache/huggingface`
  - `.cursor/.cache/torch`

## What embeddings are for vs "just grepping"

- Embeddings (semantic search):
  - Match by meaning, not exact words
  - Can retrieve relevant text even if query vocabulary differs from document vocabulary
  - Better for physics phrasing variants and paraphrased questions
- Grep/rg (lexical search):
  - Match exact tokens/patterns
  - Very fast and precise for known identifiers, exact equations, constants, function names
  - Misses semantically related text when wording differs

Practical rule:

- Use embeddings for Q&A and concept retrieval.
- Use grep for exact symbol/path/value lookups.

## Tiny math intuition (why semantic retrieval works)

Let:

- `e(q)` = embedding vector for query `q`
- `e(d_i)` = embedding vector for document chunk `d_i`

The retriever scores each chunk with cosine similarity:

`sim(q, d_i) = (e(q) · e(d_i)) / (||e(q)|| * ||e(d_i)||)`

Then it returns top-`k` chunks with highest similarity.

Why this helps:

- If two chunks use different words but express similar meaning, their vectors can still be close.
- With grep/rg, those chunks would be missed unless they share exact lexical patterns.

## Tutorial links

- Sentence Transformers semantic search tutorial:
  - https://www.sbert.net/examples/applications/semantic-search/README.html
- Sentence Transformers semantic textual similarity docs:
  - https://www.sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html

## Cache directories used by server launcher

`run_mcp_server.sh` sets local cache env vars under `.cursor/.cache/`:

- `.cursor/.cache/huggingface`
- `.cursor/.cache/torch`
- `.cursor/.cache/chroma`

## File map

- `mcp_server.py`
  - Minimal stdio MCP server.
  - Loads Hugging Face embeddings + Chroma from `.cursor/rag_db` and exposes tools:
    - `query_analysis_knowledge`
    - `search_papers`
    - `retrieve_documents`
  - Uses semantic similarity search over embedding vectors.

- `index_documents.py`
  - Compatibility wrapper.
  - Resolves config (`configs/references.yaml` fallback to `references.example.yaml`) and calls `rag/index_documents.py`.
  - Rebuilds Chroma vector DB in `.cursor/rag_db`.

- `rag/index_documents.py`
  - Core indexer: reads configured sources, chunks text, computes Hugging Face embeddings, writes to Chroma.
  - Adds metadata like `doc_path`, `chunk_index`, and `source_type`.

- `ingest_sources.py`
  - Legacy command alias/compat helper for older workflows.

- `run_mcp_server.sh`
  - Robust launcher for local use.
  - Creates `.cursor/.cache/*`, loads `.env` if present, picks Python interpreter, checks for `.cursor/rag_db`, then starts `mcp_server.py`.

- `setup_rag.sh`
  - Bootstrap script: installs dependencies and runs indexing once.

- `requirements.txt`
  - Dependencies needed for MCP-side scripts in this directory.

- `.env` / `.env.example`
  - Optional environment configuration used by launcher scripts.
