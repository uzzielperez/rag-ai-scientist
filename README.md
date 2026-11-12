# rag-ai-scientist

Installable toolkit for local RAG indexing + MCP serving in scientific workflows.

[![PyPI](https://img.shields.io/badge/package-installable-blue)](#installation)
[![Python](https://img.shields.io/badge/python-3.10%2B-informational)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-green)](https://github.com/uzzielperez/rag-ai-scientist/blob/dev/LICENSE)

`rag-ai-scientist` gives you:

- a CLI to initialize and build a **local vector database** from **your** papers and notes,
- an MCP server entrypoint for any MCP-compatible AI client,
- **packaged skills** under `rag_ai_scientist/skills/` (workflow checklists—no Git clone needed),
- a **challenge harness** (reference profile: **whest**) — the example RAG → skill → validate → score loop,
- **Overleaf Git sync** tools (same credentials as your Overleaf MCP) for pushing LaTeX bundles.

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
python -m pip install rag-ai-scientist==0.1.9
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
| **`harness list` / `harness run`** | Challenge loops (default profile: **`whest`**). |
| **`overleaf list-projects` / `status` / `sync`** | Inspect / push Overleaf projects via Git integration. |
| **`onboard`** (or `dali-onboard`) | Interactive DALI onboarding state machine (LangGraph): paper + codebase in, tested RAG brain and a validated, human-gated execution plan out. |

Common flags: **`--project-root`**, **`--force`** (rebuild index), **`--references-dir`** (with `init-references`).

---

## DALI onboarding (`onboard` / `dali-onboard`)

**DALI scaffolds your physics analyses** — the boilerplate, plumbing and
bookkeeping — so you can spend more time on the physics. Nothing is a black
box: the code it generates and the pipeline (the *pipes*) it runs are yours to
customise and inspect at every step.

One command takes a new project from *paper + codebase* to a working, verified
setup. It runs a LangGraph state machine with two human gates and a bounded
execute → validate → correct loop:

```
inputs → embed+chunk → build RAG brain → test brain (human gate)
       → plan → [execute → validate → correct]* → smoke test (human gate) → done
```

```bash
pip install rag-ai-scientist          # langgraph comes with it (Python >= 3.10)
dali-onboard --workspace ~/my-analysis
# equivalent: rag-ai-scientist onboard --workspace ~/my-analysis
```

When it starts, DALI greets you, confirms you are in the right workspace
(resolved path, brain/checkpoint locations, free disk space), and offers an
opt-in **learn-more menu** before the session begins:

| Topic | What it covers |
|---|---|
| Examples & tutorials | `docs/GETTING_STARTED.md`, `docs/examples/`, a first demo run |
| Skills | what DALI can do, and how to add your own (`skills/_template/`) |
| Tools | what DALI can run over MCP, and how to register a new one |
| The pipes | the pipeline as snap-together blocks (think Minecraft/Roblox), how to extend a step, and how to contribute a reusable pipe back as a skill |

- **Deterministic nodes do the work** (chunking, chroma brain at
  `.dali/brain`, shell execution); the LLM (Groq via `GROQ_API_KEY`, or
  OpenAI-compatible) is only used in `plan` and `correct`, and every LLM
  proposal is still executed and validated by the harness — never trusted.
- The **brain test gate** answers your own question against the fresh index
  and shows real hits before you approve; `rebuild` loops back.
- Every node writes a verifiable check; the final report lists
  `PASS/FAIL` + evidence per node. Sessions checkpoint to
  `.dali/onboard/<thread>.json` and resume if you exit mid-flow.
- `autonomous: no` (default) asks before each step run; up to
  `MAX_LOOPS = 5` correction attempts per step before escalating to you.
- The intro, workspace confirmation and learn-more menu are skipped when stdin
  is not a terminal, or with `--yes` / `-y`.

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
  - **`whest-estimation-challenge`** — [ARC WhiteBox Estimation Challenge 2026](https://www.aicrowd.com/challenges/arc-white-box-estimation-challenge-2026) (use with [whest-starterkit](https://github.com/AIcrowd/whest-starterkit))
  - **`challenge-harness`** — generic harness / example-loop skill
  - **`overleaf-paper-sync`** — Overleaf Git sync + MCP tools
- Additional **`get_skill`**, client configuration, and **whest challenge** examples are included in **`docs/examples/README.md`** in the source distribution.

### Whest challenge quick start (combined workflow)

```bash
git clone https://github.com/AIcrowd/whest-starterkit.git && cd whest-starterkit
uv sync
pip install rag-ai-scientist
bash scripts/setup_rag_references.sh   # symlinks docs into references/
rag-ai-scientist init-references --project-root . --references-dir ./references --force
rag-ai-scientist setup-rag --project-root . --force
```

Then configure any MCP-compatible client with `--project-root` set to your `whest-starterkit` folder and ask:

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
- Treat **`.rag-ai-scientist/rag_db`** (or your configured data directory) as sensitive if your indexed PDFs are sensitive. Legacy **`.cursor/rag_db`** indexes are also supported.
