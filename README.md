# rag-ai-scientist

Installable toolkit for local RAG indexing + MCP serving in scientific workflows.

[![PyPI](https://img.shields.io/badge/package-installable-blue)](#installation)
[![Python](https://img.shields.io/badge/python-3.10%2B-informational)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-green)](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/LICENSE)

`rag-ai-scientist` gives you:

- a CLI to initialize and build a **local vector database** from **your** papers and notes,
- an MCP server entrypoint for Cursor / agent integrations,
- **packaged skills** under `rag_ai_scientist/skills/` (workflow checklists—no Git clone needed),
- a **challenge harness** (reference profile: **whest**) — the example RAG → skill → validate → score loop,
- **Overleaf Git sync** tools (same credentials as your Overleaf MCP) for pushing LaTeX bundles.

On **PyPI**, only this README is shown; detailed guides live on **GitHub** (absolute links below).

---

## End-user workflow (pip only — **no clone required**)

You install from PyPI, create **any folder** for your project, put your research materials there, index once, then connect Cursor.

**Full step-by-step:** **[Getting started](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/docs/GETTING_STARTED.md)** — install → `references/` → `init-references` → `setup-rag` → MCP → update notes and rebuild.

Minimal command sequence (after `pip install rag-ai-scientist`):

```bash
mkdir -p ~/my-ai-scientist/references
cd ~/my-ai-scientist
# Add your own .md / .pdf files under references/

rag-ai-scientist init-references --project-root . --references-dir ./references
rag-ai-scientist setup-rag --project-root . --force
rag-ai-scientist mcp --project-root .    # usually configured once inside Cursor — see Getting started link above
```

- **`query_analysis_knowledge`** answers from **your indexed files**.
- **`get_skill`** loads packaged skills (e.g. **`cms-higgs-opendata`**, **`whest-estimation-challenge`**) **without** indexing anything extra.

You update your AI scientist by editing files under **`references/`** (and **`configs/references.yaml`** if paths change), then **`setup-rag --force`** again.

---

## Installation

### From PyPI (recommended)

```bash
python -m pip install rag-ai-scientist
```

Pinned example:

```bash
python -m pip install rag-ai-scientist==0.1.5
```

PyPI project page: [rag-ai-scientist](https://pypi.org/project/rag-ai-scientist/)

### Verify

```bash
rag-ai-scientist --help
python -c "import rag_ai_scientist; print(rag_ai_scientist.__version__)"
```

### From source (maintainers / contributors only)

```bash
git clone https://github.com/uzzielperez/rag-ai-scientist.git
cd rag-ai-scientist
git checkout dev   # or your working branch
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -e .
```

Isolation tip: use a dedicated venv (e.g. `~/venvs/rag-ai-scientist`) instead of mixing with heavy analysis stacks.

---

## CLI commands

| Command | Purpose |
|---------|---------|
| **`init-references`** | Writes **`configs/references.yaml`** pointing at your references directory. |
| **`setup-rag`** | Indexes sources into **`.cursor/rag_db`**. |
| **`mcp`** | Starts the stdio MCP server — point **`--project-root`** at the same folder you indexed. |
| **`harness list` / `harness run`** | Challenge loops (default profile: **`whest`**). |
| **`overleaf list-projects` / `status` / `sync`** | Inspect / push Overleaf projects via Git integration. |

Common flags: **`--project-root`**, **`--force`** (rebuild index), **`--references-dir`** (with `init-references`).

---

## Challenge harness (WHEST as the example loop)

```bash
# From a whest-starterkit checkout:
rag-ai-scientist harness run --project-root . --profile whest --dry-run
rag-ai-scientist harness run --project-root . --profile whest --until-stage validate
```

MCP tools: **`harness_list_profiles`**, **`harness_run`**. Skills: **`challenge-harness`**, **`whest-estimation-challenge`**.

---

## Overleaf (built-in + companion MCP)

```bash
export OVERLEAF_PROJECTS_CONFIG="$HOME/.config/overleaf-mcp/projects.json"
rag-ai-scientist overleaf list-projects
rag-ai-scientist overleaf sync --bundle-dir output/overleaf_bundle --dry-run
```

MCP tools: **`overleaf_list_projects`**, **`overleaf_status`**, **`overleaf_list_files`**, **`overleaf_read_file`**, **`overleaf_sync_bundle`**. Skill: **`overleaf-paper-sync`**.

Keep the Node Overleaf MCP for section-level edits; use these Python tools for list/read/bundle push.

---

## Cursor MCP configuration

Register the server so Cursor runs it with **your** project path:

```json
{
  "mcpServers": {
    "rag-ai-scientist": {
      "command": "rag-ai-scientist",
      "args": ["mcp", "--project-root", "/absolute/path/to/my-ai-scientist"]
    }
  }
}
```

See **[Getting started](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/docs/GETTING_STARTED.md)** for optional **`.cursor/.env`** (LLM keys).

---

## Packaged skills and examples

- Skills ship **inside the installed package**. Access via MCP **`get_skill`**:
  - **`cms-higgs-opendata`** — CMS Run-1 Higgs open-data replication
  - **`whest-estimation-challenge`** — [ARC WhiteBox Estimation Challenge 2026](https://www.aicrowd.com/challenges/arc-white-box-estimation-challenge-2026) (use with [whest-starterkit](https://github.com/AIcrowd/whest-starterkit))
  - **`challenge-harness`** — generic harness / example-loop skill
  - **`overleaf-paper-sync`** — Overleaf Git sync + MCP tools
- **[Examples / MCP access](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/docs/examples/README.md)** explains **`get_skill`**, Cursor wiring, and the **whest challenge as an end-to-end example**.

### Whest challenge quick start (combined workflow)

```bash
git clone https://github.com/AIcrowd/whest-starterkit.git && cd whest-starterkit
uv sync
pip install rag-ai-scientist
bash scripts/setup_rag_references.sh   # symlinks docs into references/
rag-ai-scientist init-references --project-root . --references-dir ./references --force
rag-ai-scientist setup-rag --project-root . --force
```

Then in Cursor, point MCP `--project-root` at your `whest-starterkit` folder and ask:

```text
Use the whest-estimation-challenge skill. Start from mean propagation and improve the estimator.
```

---

## Running agents beside a separate lab environment

If training runs use a different conda/venv than `rag-ai-scientist`:

1. Install **`rag-ai-scientist`** in its own small venv.
2. Keep **`--project-root`** pointed at your research folder.
3. Run heavy jobs via explicit wrappers (`conda run`, scripts) from the agent — see **[Runbook](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/docs/RUNBOOK.md)** for patterns.

---

## Repository layout (when developing from source)

```text
rag_ai_scientist/
  cli.py                  # CLI entrypoint
  mcp_server.py           # MCP server (RAG + skills + harness + Overleaf)
  harness/                # Challenge loops (whest reference profile)
  overleaf/               # Git-based Overleaf client
  skills/                 # Packaged skills (ship in wheel)
rag/
  index_documents.py      # Indexer used by setup-rag
configs/
  references.example.yaml # Example only — users run init-references instead
  overleaf.example.yaml   # Overleaf sync template
docs/
  GETTING_STARTED.md      # Primary user guide (pip-only path)
  examples/               # Maintainer docs / optional narratives
```

Browse on GitHub: [docs/](https://github.com/uzzielperez/rag-ai-scientist/tree/dev/docs).

---

## Development & PyPI releases

Contributor workflow and release steps: **[DEV_README.md](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/DEV_README.md)**.

---

## License

- Open-source: AGPL-3.0-or-later ([`LICENSE`](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/LICENSE))
- Commercial: see [`LICENSE-COMMERCIAL.md`](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/LICENSE-COMMERCIAL.md)

---

## Security notes

- Never commit secrets (`.env`, API keys).
- Treat **`.cursor/rag_db`** as sensitive if your indexed PDFs are sensitive.
