# RAG Vector Database

This project uses a local vector DB under `.cursor/rag_db/`.

## Build index

```bash
./scripts/build_rag_db.sh
```

That script runs:

```bash
python rag/index_documents.py --config configs/references.yaml --output-dir .cursor/rag_db
```

If `configs/references.yaml` does not exist, it falls back to `configs/references.example.yaml`.

## Query index

```bash
python rag/query_rag.py --db-dir .cursor/rag_db --query "What is the 2016 BR reference?"
```

## Regeneration workflow

1. Update reference paths in `configs/references.yaml`.
2. Rebuild with `./scripts/build_rag_db.sh`.
3. Run test queries using `rag/query_rag.py`.

## Stored artifacts

- `chunks.jsonl`: chunk text + metadata
- `vectors.json`: TF-IDF vectors
- `vocab.json`: vocabulary map
- `meta.json`: chunk and document counts

## Notes

- This is a lightweight local baseline for fast startup.
- You can replace the backend with Chroma/FAISS later while keeping the same config contract.
