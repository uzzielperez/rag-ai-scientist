# References for RAG

Use this document to manage default and user-supplied references.

## Seeded references

By default, `configs/references.example.yaml` includes:

- `lb02lbgammabr/README.md`
- `lb02lbgammabr/docs/HACKATHON_TASK_BOARD.md`
- `lb02lbgammabr/docs/rag_system_paper.tex`
- `lb02lbgammabr/data/README.md`
- `lb02lbgammabr/data/samplelist.py`

## Bring your own references

1. Copy template:
   - `cp configs/references.example.yaml configs/references.yaml`
2. Add your files/directories under `sources[].paths`.
3. Set allowed extensions for each source group.

Supported formats for the v1 indexer:

- `.md`
- `.txt`
- `.tex`
- `.py`
- `.pdf` (path collection supported; extraction quality depends on text availability)

## Best practices

- Prefer plain-text or markdown exports where possible.
- Keep references versioned and grouped by analysis context.
- Rebuild the vector DB after any reference update.
