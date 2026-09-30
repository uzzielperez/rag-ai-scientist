# rag-ai-scientist

Installable toolkit for local RAG indexing + MCP serving in scientific workflows.

[![PyPI](https://img.shields.io/badge/package-installable-blue)](#installation)
[![Python](https://img.shields.io/badge/python-3.10%2B-informational)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-green)](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/LICENSE)

`rag-ai-scientist` gives you:

- a CLI to initialize and build a **local vector database** from **your** papers and notes,
- an MCP server entrypoint for any MCP-compatible AI client,
- **packaged skills** under `rag_ai_scientist/skills/` (workflow checklists—no Git clone needed),
- a **verification harness** (`ras run`) — the domain-free index → answer → validate → correct loop with gates, golden sets and promoted skills,
- **Overleaf Git sync** tools (same credentials as your Overleaf MCP) for pushing LaTeX bundles,
- a vendored **Overleaf Node MCP server** (`overleaf install-node-server`) so anyone can run the full read/write/commit/push toolset.

On **PyPI**, this README contains the complete install and MCP setup workflow. Additional examples are included in the source distribution.

---

## End-user workflow (pip only — **no clone required**)

You install from PyPI, create **any folder** for your project, put your research materials there, index once, then connect an MCP-compatible AI client.

The workflow is: install → add files under `references/` → `init-references` → `setup-rag` → configure any MCP client → update notes and rebuild as needed.

Minimal command sequence (after `pip install rag-ai-scientist`):

```bash
mkdir -p ~/my-ai-scientist/references
cd ~/my-ai-scientist
# Add your own .md / .pdf files under references/

rag-ai-scientist init-references --project-root . --references-dir ./references
rag-ai-scientist setup-rag --project-root . --force
rag-ai-scientist mcp --project-root .    # configure this command in your MCP client
```

- **`query_analysis_knowledge`** answers from **your indexed files**.
- **`get_skill`** loads packaged skills (e.g. **`cms-higgs-opendata`**, **`overleaf-paper-sync`**) **without** indexing anything extra.

You update your AI scientist by editing files under **`references/`** (and **`configs/references.yaml`** if paths change), then **`setup-rag --force`** again.

---

## Installation

### From PyPI (recommended)

```bash
python -m pip install rag-ai-scientist
```

Pinned example:

```bash
python -m pip install rag-ai-scientist==0.1.10
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
| **`setup-rag`** | Indexes sources into **`.rag-ai-scientist/rag_db`** by default (or the configured `indexing.data_dir`). |
| **`mcp`** | Starts the stdio MCP server — point **`--project-root`** at the same folder you indexed. |
| **`handoff create` / `handoff apply`** | Package collaborator work into a verified bundle, then preview or apply it from a clean checkout. |
| **`rag-ai-scientist-handoff create` / `apply`** | Lightweight standalone handoff CLI; works without installing RAG/ML dependencies. |
| **`ras init-project` / `index` / `run` / `eval`** | Domain-free verification harness (see [docs/harness.md](docs/harness.md)). |
| **`ras demo`** | Watch the whole harness work end to end in a throwaway project (animated, offline). |
| **`harness list` / `harness run`** | Legacy profile loops — no profiles ship by default (register your own). |
| **`overleaf list-projects` / `status` / `sync`** | Inspect / push Overleaf projects via Git integration. |
| **`overleaf install-node-server`** | Install the vendored Node Overleaf MCP server (full read/write/commit/push tools) — no separate download needed. |

Common flags: **`--project-root`**, **`--force`** (rebuild index), **`--references-dir`** (with `init-references`).

---

## Verification harness (`ras`)

The harness is **domain-free**: point it at any project with a text corpus and a golden set of questions and it runs an offline, gated index → answer → validate → correct loop.

```bash
ras init-project --project-root .   # scaffold configs/harness.yaml
ras run --project-root .            # PLAN/EXECUTE/VALIDATE/CORRECT until every gate passes
ras eval --project-root .           # score the run against the golden set
ras skills list --project-root .    # skills promoted by passing runs
```

Legacy MCP tools **`harness_list_profiles`** / **`harness_run`** expose the profile interface — no profiles ship by default; register one with `harness.registry.register`. Full reference: **[docs/harness.md](docs/harness.md)**.

**Prefer watching to reading:** `ras demo` is an animated terminal show that drives the real `ras` CLI against a throwaway project — scaffold → corpus → index → the gated loop → eval → skill → report — entirely offline, then deletes the project afterwards. It ships **inside the wheel**, so `pip install` is all you need: `ras demo --fast` for instant output (CI mode), `ras demo --keep` to explore the demo project afterwards.

**Learning it:** **[docs/TUTORIAL.md](docs/TUTORIAL.md)** walks the flow end to end with the output you should see and a gate-by-gate failure playbook. The same walkthrough ships as a packaged skill — any MCP client can load it with **`get_skill("harness-tutorial")`**.

---

## Overleaf (built-in + companion MCP)

```bash
export OVERLEAF_PROJECTS_CONFIG="$HOME/.config/overleaf-mcp/projects.json"
rag-ai-scientist overleaf list-projects
rag-ai-scientist overleaf sync --bundle-dir output/overleaf_bundle --dry-run
# Anyone can install the companion Node MCP server straight from the wheel:
rag-ai-scientist overleaf install-node-server --dest ~/.config/overleaf-mcp
npm install --prefix ~/.config/overleaf-mcp
```

MCP tools: **`overleaf_list_projects`**, **`overleaf_status`**, **`overleaf_list_files`**, **`overleaf_read_file`**, **`overleaf_sync_bundle`**. Skill: **`overleaf-paper-sync`**.

Keep the Node Overleaf MCP for section-level edits; use these Python tools for list/read/bundle push.

### Overleaf Node MCP pickup (no separate download)

The full read/write/commit/push server ships **inside the wheel** as
`rag_ai_scientist/overleaf/node/` (`overleaf-mcp-server.js` +
`overleaf-git-client.js`, needs `@modelcontextprotocol/sdk`). After
`pip install rag-ai-scientist`:

```bash
rag-ai-scientist overleaf install-node-server --dest ~/.config/overleaf-mcp
npm install --prefix ~/.config/overleaf-mcp
```

Then point any MCP client at it:

```json
{
  "mcpServers": {
    "overleaf": {
      "command": "node",
      "args": ["/Users/YOU/.config/overleaf-mcp/overleaf-mcp-server.js"],
      "env": {"OVERLEAF_PROJECTS_CONFIG": "/Users/YOU/.config/overleaf-mcp/projects.json"}
    }
  }
}
```

Tools: `list_files`, `read_file`, `write_file`, `get_sections`,
`get_section_content`, `status_summary`, `list_projects`, `delete_file`,
`commit_changes`, `push_changes`, `git_status`, `upload_file`.

---

## Connect an MCP client

The server uses standard MCP over stdio. In VS Code with GitHub Copilot, add this to **`.vscode/mcp.json`** (use absolute paths):

```json
{
  "servers": {
    "rag-ai-scientist": {
      "type": "stdio",
      "command": "/absolute/path/to/venv/bin/rag-ai-scientist",
      "args": ["mcp", "--project-root", "/absolute/path/to/my-ai-scientist"]
    }
  }
}
```

Other MCP clients use the same command and arguments, though their configuration file/schema may differ. For clients using an `mcpServers` object (including Cursor, Cline, and Claude Desktop), use:

```json
{
  "mcpServers": {
    "rag-ai-scientist": {
      "command": "/absolute/path/to/venv/bin/rag-ai-scientist",
      "args": ["mcp", "--project-root", "/absolute/path/to/my-ai-scientist"]
    }
  }
}
```

See **[Getting started](docs/GETTING_STARTED.md)** for setup details and the optional **`.rag-ai-scientist/.env`** file for LLM keys. Existing projects with an index under **`.cursor/rag_db`** continue to work without moving it.

---

## Packaged skills and examples

- Skills ship **inside the installed package**. Access via MCP **`get_skill`**:
  - **`cms-higgs-opendata`** — CMS Run-1 Higgs open-data replication
  - **`overleaf-paper-sync`** — Overleaf Git sync + MCP tools
  - **`harness-tutorial`** — guided first run of the `ras` verification harness
  - **`rag-setup`** and other project workflow skills
- Additional **`get_skill`** and client configuration examples are included in **`docs/examples/README.md`** in the source distribution.

### Harness worked example (offline)

The golden-set format and an example question set ship in `evals/golden/`. The corpus is yours: drop PDFs or Markdown into `docs/references/papers/`. Nothing here needs a model, an API key or a network connection.

```bash
ras demo --fast               # self-contained: builds its own 4-document corpus in a temp dir and clears every gate
ras run --project-root .      # index → answer → validate → correct; all gates must pass
ras eval --project-root .     # tier pass rates against the golden set
```

See **[docs/harness.md](docs/harness.md)** for configuration, gates, remedies and skills.

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
  harness/                # Domain-free verification harness (ras run loop)
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
- Treat **`.rag-ai-scientist/rag_db`** (or your configured data directory) as sensitive if your indexed PDFs are sensitive. Legacy **`.cursor/rag_db`** indexes are also supported.
