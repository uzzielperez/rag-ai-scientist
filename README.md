# rag-ai-scientist

Installable toolkit for local RAG indexing + MCP serving in scientific workflows.

[![PyPI](https://img.shields.io/badge/package-installable-blue)](#installation)
[![Python](https://img.shields.io/badge/python-3.10%2B-informational)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-green)](./LICENSE)

`rag-ai-scientist` gives you:

- a CLI to initialize and build a **local vector database** from **your** papers and notes,
- an MCP server entrypoint for Cursor / agent integrations,
- **packaged skills** under `rag_ai_scientist/skills/` (workflow checklists—no Git clone needed).

---

## End-user workflow (pip only — **no GitHub**)

You install from PyPI, create **any folder** for your project, put your research materials there, index once, then connect Cursor.

**Full step-by-step:** **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** — install → `references/` → `init-references` → `setup-rag` → MCP → update notes and rebuild.

Minimal command sequence (after `pip install rag-ai-scientist`):

```bash
mkdir -p ~/my-ai-scientist/references
cd ~/my-ai-scientist
# Add your own .md / .pdf files under references/

rag-ai-scientist init-references --project-root . --references-dir ./references
rag-ai-scientist setup-rag --project-root . --force
rag-ai-scientist mcp --project-root .    # usually configured once inside Cursor — see GETTING_STARTED
```

- **`query_analysis_knowledge`** answers from **your indexed files**.
- **`get_skill`** loads packaged skills (e.g. **`cms-higgs-opendata`**) **without** indexing anything extra.

You update your AI scientist by editing files under **`references/`** (and **`configs/references.yaml`** if paths change), then **`setup-rag --force`** again.

---

## Installation

### From PyPI (recommended)

```bash
python -m pip install rag-ai-scientist
```

Pinned example:

```bash
python -m pip install rag-ai-scientist==0.1.2
```

PyPI: [rag-ai-scientist](https://pypi.org/project/rag-ai-scientist/)

### Verify

```bash
rag-ai-scientist --help
python -c "import rag_ai_scientist; print(rag_ai_scientist.__version__)"
```

### From source (maintainers / contributors only)

```bash
git clone <your fork or upstream URL>
cd rag-ai-scientist-installable   # or package repo name
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

Common flags: **`--project-root`**, **`--force`** (rebuild index), **`--references-dir`** (with `init-references`).

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

See **[docs/GETTING_STARTED.md](docs/GETTING_STARTED.md)** for optional **`.cursor/.env`** (LLM keys).

---

## Packaged skills and examples

- Skills ship **inside the installed package**. Access via MCP **`get_skill`** (e.g. **`cms-higgs-opendata`**). No clone required.
- **[docs/examples/README.md](docs/examples/README.md)** explains **`get_skill`**, Cursor wiring, and optional curated markdown **for maintainers** who ship a full docs tree. End users normally only need their own files under **`references/`**.

---

## Running agents beside a separate lab environment

If training runs use a different conda/venv than `rag-ai-scientist`:

1. Install **`rag-ai-scientist`** in its own small venv.
2. Keep **`--project-root`** pointed at your research folder.
3. Run heavy jobs via explicit wrappers (`conda run`, scripts) from the agent — see **[docs/RUNBOOK.md](docs/RUNBOOK.md)** if present for patterns.

---

## Repository layout (when developing from source)

```text
rag_ai_scientist/
  cli.py                  # CLI entrypoint
  mcp_server.py           # MCP server
  skills/                 # Packaged skills (ship in wheel)
rag/
  index_documents.py      # Indexer used by setup-rag
configs/
  references.example.yaml # Example only — users run init-references instead
docs/
  GETTING_STARTED.md      # Primary user guide (pip-only path)
  examples/               # Maintainer docs / optional narratives
```

---

## Development & PyPI releases

Contributor workflow and release steps: **[DEV_README.md](DEV_README.md)**.

---

## License

- Open-source: AGPL-3.0-or-later (`LICENSE`)
- Commercial: see `LICENSE-COMMERCIAL.md`

---

## Security notes

- Never commit secrets (`.env`, API keys).
- Treat **`.cursor/rag_db`** as sensitive if your indexed PDFs are sensitive.
