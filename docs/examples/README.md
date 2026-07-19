# Indexed examples (RAG)

## If you only used `pip install` (no repository checkout)

You **do not** need these files for basic usage. Put **your own** markdown and PDFs in the directory you passed to **`init-references --references-dir`**, run **`setup-rag`**, and query with **`query_analysis_knowledge`**. Use MCP **`get_skill`** for packaged workflows without copying anything from here.

Packaged skills available via **`get_skill`**:

| Skill | Use case |
|-------|----------|
| **`cms-higgs-opendata`** | CMS Run-1 Higgs open-data replication |
| **`whest-estimation-challenge`** | ARC WhiteBox Estimation Challenge 2026 |
| **`challenge-harness`** | Example loop / harness runner (profile: whest) |
| **`overleaf-paper-sync`** | Overleaf Git sync + MCP tools |

---

## Maintainer / source-tree layout

Markdown in this directory is intended for **vector indexing** alongside project documentation. Paths under `docs/` are picked up when using `configs/references.example.yaml` from a checkout (`sources.project_docs.paths` includes `../docs`).

| Document | Purpose |
|----------|---------|
| [cms_higgs_opendata_physics_story.md](./cms_higgs_opendata_physics_story.md) | CMS Run-1 Higgs (~125 GeV) discovery narrative and open-data pointers |
| [whest_estimation_challenge_story.md](./whest_estimation_challenge_story.md) | ARC WhiteBox Estimation Challenge — problem, scoring, algorithms, pip/RAG integration |

Related packaged skills:

- **`cms-higgs-opendata`** — `rag_ai_scientist/skills/cms-higgs-opendata/SKILL.md`
- **`whest-estimation-challenge`** — `rag_ai_scientist/skills/whest-estimation-challenge/SKILL.md`
- **`challenge-harness`** — `rag_ai_scientist/skills/challenge-harness/SKILL.md`
- **`overleaf-paper-sync`** — `rag_ai_scientist/skills/overleaf-paper-sync/SKILL.md`

---

## Whest challenge as end-to-end example (harness)

The recommended **combined workflow** (challenge + PyPI package):

1. Clone [whest-starterkit](https://github.com/AIcrowd/whest-starterkit) and `uv sync`
2. `pip install rag-ai-scientist` (or `pip install -e .` from this repo)
3. Follow **`RAG_SETUP.md`** in whest-starterkit to index challenge docs
4. In Cursor, configure MCP with `--project-root` pointing at **whest-starterkit**
5. Dry-run the harness: `rag-ai-scientist harness run --project-root . --profile whest --dry-run`
6. Ask the agent: *"Use the whest-estimation-challenge skill and implement low-rank covariance propagation"*
7. Iterate with `harness run --until-stage validate` then `score_local`
8. Optional: sync notes with `overleaf sync` / skill **`overleaf-paper-sync`**

Example references config for whest: **`configs/references-whest.example.yaml`** in this repository.

---

## Accessing packaged skills (after `pip install`)

Skills ship as Markdown under **`rag_ai_scientist/skills/<name>/`** in the wheel. Agents load them through MCP **`get_skill`**.

```json
{ "skill": "whest-estimation-challenge" }
```

Optional step files:

```json
{ "skill": "whest-estimation-challenge", "step": "iterate" }
{ "skill": "whest-estimation-challenge", "step": "score" }
```

Resolution order:

1. **`/your/project/.cursor/skills/whest-estimation-challenge/SKILL.md`** if present
2. Else packaged copy in `site-packages/rag_ai_scientist/skills/`

### Cursor MCP configuration (whest-starterkit as project root)

```json
{
  "mcpServers": {
    "rag-ai-scientist": {
      "command": "rag-ai-scientist",
      "args": ["mcp", "--project-root", "/absolute/path/to/whest-starterkit"]
    }
  }
}
```

### Print packaged skill path

```bash
python -c "import pathlib, rag_ai_scientist; print(pathlib.Path(rag_ai_scientist.__file__).parent / 'skills' / 'whest-estimation-challenge' / 'SKILL.md')"
```
