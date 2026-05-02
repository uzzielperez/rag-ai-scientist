# Indexed examples (RAG)

## If you only used `pip install` (no repository checkout)

You **do not** need these files. Put **your own** markdown and PDFs in the directory you passed to **`init-references --references-dir`**, run **`setup-rag`**, and query with **`query_analysis_knowledge`**. Use MCP **`get_skill`** for packaged workflows (for example **`cms-higgs-opendata`**) without copying anything from here.

The rest of this page documents **optional** curated notes **when developing from a full source tree**, plus how **`get_skill`** resolves packaged skills after install.

---

## Maintainer / source-tree layout

Markdown in this directory is intended for **vector indexing** alongside project documentation. Paths under `docs/` are picked up when using `configs/references.example.yaml` from a checkout (`sources.project_docs.paths` includes `../docs`).

| Document | Purpose |
|----------|---------|
| [cms_higgs_opendata_physics_story.md](./cms_higgs_opendata_physics_story.md) | CMS Run-1 Higgs (~125 GeV) discovery narrative, open-data replication pointers, and **`pip install`** / MCP indexing notes |

Related packaged skill (always available without indexing): **`cms-higgs-opendata`** — see `rag_ai_scientist/skills/cms-higgs-opendata/SKILL.md`.

---

## Accessing packaged skills (after `pip install`)

Skills ship as Markdown under **`rag_ai_scientist/skills/<skill-name>/`** in the wheel. You do **not** import them as Python modules; agents load them through the MCP tool **`get_skill`**.

### 1. Run the MCP server

Use the **same** `--project-root` as the repo where you ran **`rag-ai-scientist setup-rag`** (so `.cursor/rag_db` matches):

```bash
rag-ai-scientist mcp --project-root /absolute/path/to/your/project
```

### 2. Cursor MCP configuration

Example **`~/.cursor/mcp.json`** entry:

```json
{
  "mcpServers": {
    "rag-ai-scientist": {
      "command": "rag-ai-scientist",
      "args": ["mcp", "--project-root", "/absolute/path/to/your/project"]
    }
  }
}
```

Use the `rag-ai-scientist` executable from the environment where you installed the package (`pip install rag-ai-scientist` or editable install).

### 3. Call `get_skill`

The MCP server exposes **`get_skill`**. Typical arguments:

```json
{ "skill": "cms-higgs-opendata" }
```

Optional per-step file (must exist next to `SKILL.md`):

```json
{ "skill": "cms-higgs-opendata", "step": "optional-step-file-without-md-suffix" }
```

Resolution order:

1. **`/your/project/.cursor/skills/cms-higgs-opendata/SKILL.md`** if present  
2. Else **`…/site-packages/rag_ai_scientist/skills/cms-higgs-opendata/SKILL.md`** from the installed wheel  

So you can override a packaged skill by adding files under **`.cursor/skills/`** in your project.

### 4. Open the packaged file on disk

Print the path to the installed package root:

```bash
python -c "import pathlib, rag_ai_scientist; print(pathlib.Path(rag_ai_scientist.__file__).parent)"
```

The CMS Higgs skill file is:

```text
<that-directory>/skills/cms-higgs-opendata/SKILL.md
```

One-liner:

```bash
python -c "import pathlib, rag_ai_scientist; print(pathlib.Path(rag_ai_scientist.__file__).parent / 'skills' / 'cms-higgs-opendata' / 'SKILL.md')"
```

### 5. Without MCP

You can still read **`SKILL.md`** locally or copy it into **`.cursor/skills/cms-higgs-opendata/`** and ask your agent to follow it; **`get_skill`** is only required for automated loading via MCP.
