# References for RAG

Use this document to manage default and user-supplied references.

## Seeded references (this repository)

By default, `configs/references.example.yaml` indexes paths **relative to `configs/`**:

- `../README.md`
- `../docs` (including **`docs/examples/`** — see [examples README](examples/README.md))
- `../papers` (if present)
- `../scripts` and `../rag` as code sources
- optional `~/public/my_references` for local PDFs and notes

Example narrative indexed from `docs/examples/`:

- **`docs/examples/cms_higgs_opendata_physics_story.md`** — CMS Run-1 Higgs open-data physics story and **`pip install`** usage notes (pair with packaged skill **`cms-higgs-opendata`**).

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
