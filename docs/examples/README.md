# Indexed examples (RAG)

## If you only used `pip install` (no repository checkout)

You **do not** need these files for basic usage. Put **your own** markdown and PDFs in the directory you passed to **`init-references --references-dir`**, run **`setup-rag`**, and query with **`query_analysis_knowledge`**. Use MCP **`get_skill`** for packaged workflows without copying anything from here.

Packaged skills available via **`get_skill`**:

| Skill | Use case |
|-------|----------|
| **`cms-higgs-opendata`** | CMS Run-1 Higgs open-data replication |
| **`overleaf-paper-sync`** | Overleaf Git sync + MCP tools |

---

## Maintainer / source-tree layout

Markdown in this directory is intended for **vector indexing** alongside project documentation. Paths under `docs/` are picked up when using `configs/references.example.yaml` from a checkout (`sources.project_docs.paths` includes `../docs`).

| Document | Purpose |
|----------|---------|
| [cms_higgs_opendata_physics_story.md](./cms_higgs_opendata_physics_story.md) | CMS Run-1 Higgs (~125 GeV) discovery narrative and open-data pointers |

Related packaged skills:

- **`cms-higgs-opendata`** — `rag_ai_scientist/skills/cms-higgs-opendata/SKILL.md`
- **`overleaf-paper-sync`** — `rag_ai_scientist/skills/overleaf-paper-sync/SKILL.md`

---

## Verification harness end-to-end

The harness is **domain-free** and runs fully offline (see [../harness.md](../harness.md)):

1. Put a corpus under `docs/references/papers/` (or set `corpus.paths` in `configs/harness.yaml`)
2. Add a golden set of questions under `evals/golden/`
3. Run `ras run --project-root .` — index → answer → validate → correct until every gate passes
4. Score with `ras eval --project-root .`
5. Inspect the generated skill with `ras skills list` / `ras skills show`

---

## Accessing packaged skills (after `pip install`)

Skills ship as Markdown under **`rag_ai_scientist/skills/<name>/`** in the wheel. Agents load them through MCP **`get_skill`**.

```json
{ "skill": "cms-higgs-opendata" }
```

Optional step files:

```json
{ "skill": "cms-higgs-opendata", "step": "iterate" }
```

Resolution order:

1. **`/your/project/.cursor/skills/cms-higgs-opendata/SKILL.md`** if present
2. Else packaged copy in `site-packages/rag_ai_scientist/skills/`

### Cursor MCP configuration (any project as project root)

```json
{
  "mcpServers": {
    "rag-ai-scientist": {
      "command": "rag-ai-scientist",
      "args": ["mcp", "--project-root", "/absolute/path/to/my-project"]
    }
  }
}
```

### Print packaged skill path

```bash
python -c "import pathlib, rag_ai_scientist; print(pathlib.Path(rag_ai_scientist.__file__).parent / 'skills' / 'cms-higgs-opendata' / 'SKILL.md')"
```
