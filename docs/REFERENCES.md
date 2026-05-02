# References for RAG

Use this document to tune **what gets indexed** into your local vector database.

## Pip-install users (recommended path)

You normally **never edit YAML by hand** at first:

```bash
rag-ai-scientist init-references --project-root . --references-dir /path/to/your/references
```

That creates **`configs/references.yaml`** pointing at **your** folder. Add PDFs and markdown there, then:

```bash
rag-ai-scientist setup-rag --project-root . --force
```

To **add another directory later**, open **`configs/references.yaml`** and append a path under **`sources[].paths`**, or run **`init-references`** again with **`--force`** if you want to replace the config (backup first if needed).

## Example `references.example.yaml` (full source checkout)

Maintainers who clone the repository may start from **`configs/references.example.yaml`**, which indexes paths **relative to `configs/`** (project README, **`docs/`**, **`papers/`**, code paths, etc.). See **`docs/examples/README.md`** for optional CMS Higgs narrative files used in CI/docs builds.

## Bring your own references (manual YAML)

1. Copy template if you prefer not to use **`init-references`**:
   - `cp configs/references.example.yaml configs/references.yaml`
2. Add your files/directories under **`sources[].paths`**.
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
