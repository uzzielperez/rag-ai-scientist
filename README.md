# rag-ai-scientist

Installable toolkit for local RAG indexing + MCP serving in scientific workflows.

[![PyPI](https://img.shields.io/badge/package-installable-blue)](#installation)
[![Python](https://img.shields.io/badge/python-3.10%2B-informational)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-AGPL--3.0--or--later-green)](./LICENSE)

`rag-ai-scientist` gives you:
- a CLI to initialize and build a local vector database from your references,
- an MCP server entrypoint for Cursor/agent integrations,
- packaged reusable skills under `rag_ai_scientist/skills/`.

## Installation

### From PyPI (recommended for end users)

Project page: [rag-ai-scientist on PyPI](https://pypi.org/project/rag-ai-scientist/0.1.0/)

```bash
python -m pip install rag-ai-scientist==0.1.0
```

Or install the latest published release:

```bash
python -m pip install rag-ai-scientist
```

### From source (recommended while developing)

```bash
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

If `uv` is not available, fallback to:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Recommended isolation: keep this in a dedicated environment (for example
`venvs/rag-ai-scientist`) rather than reusing analysis environments such as
`ecalgnn311`.

### Verify install

```bash
python -m pip show rag-ai-scientist
rag-ai-scientist --help
python -c "import rag_ai_scientist; print(rag_ai_scientist.__version__)"
```

## Quickstart

1) Initialize `configs/references.yaml` for your analysis repo:

```bash
rag-ai-scientist init-references \
  --project-root . \
  --references-dir /path/to/references
```

2) Build the local RAG database:

```bash
rag-ai-scientist setup-rag --project-root . --force
```

3) Start the MCP server:

```bash
rag-ai-scientist mcp --project-root .
```

## CLI Commands

### `init-references`
Creates `configs/references.yaml` with source paths, chunking, and doc-type rules.

Useful options:
- `--references-dir` path containing `.pdf/.md/.txt/.tex/.py/.rst`
- `--collection-name` default: `rag-ai-scientist`
- `--chunk-size`, `--chunk-overlap`
- `--scientific-chunk-size`, `--scientific-chunk-overlap`
- `--force` overwrite existing config

### `setup-rag`
Indexes references and writes ChromaDB to `.cursor/rag_db`.

Useful options:
- `--force` rebuild from scratch
- `--collection-name` override config collection
- `--chunk-size`, `--chunk-overlap` runtime overrides

### `mcp`
Starts the stdio MCP server for Cursor or compatible MCP clients.

## Cursor MCP Configuration

Example `~/.cursor/mcp.json` entry:

```json
{
  "mcpServers": {
    "rag-ai-scientist": {
      "command": "rag-ai-scientist",
      "args": ["mcp", "--project-root", "/absolute/path/to/analysis-repo"]
    }
  }
}
```

## Running Agents With Separate Training Environments

If agents should run training/inference scripts and update configs, use two
environments in parallel:

- `rag-ai-scientist` environment: runs MCP server and agent logic.
- analysis/training environment: runs model training and inference commands.

This avoids dependency conflicts while still letting agents orchestrate the full
workflow for another repository.

### Recommended architecture

1) Keep a dedicated environment for `rag-ai-scientist`:

```bash
cd /path/to/rag-ai-scientist-installable
uv venv .venv
source .venv/bin/activate
uv pip install -e .
```

2) Keep your analysis repository and its own environment separate:

- repo: `/path/to/analysis-repo`
- env: `/path/to/analysis-env` (conda or venv)

3) Start MCP from the `rag-ai-scientist` environment, but point it to the
analysis repo:

```bash
rag-ai-scientist mcp --project-root /path/to/analysis-repo
```

4) Let agents launch analysis commands explicitly inside the analysis
environment (for example via `conda run -p`), instead of relying on ambient
shell state.

### Safe command wrapper for agent execution

Create a wrapper script in the analysis repo (example:
`/path/to/analysis-repo/scripts/run_training.sh`) and let agents call only this
script:

```bash
#!/usr/bin/env bash
set -euo pipefail

ANALYSIS_ENV="/path/to/analysis-env"
ANALYSIS_REPO="/path/to/analysis-repo"

cd "$ANALYSIS_REPO"
exec conda run -p "$ANALYSIS_ENV" python scripts/train.py "$@"
```

This gives deterministic execution and avoids accidental environment drift.

### Guardrails for autonomous edits and runs

- Restrict editable files to a whitelist (for example `configs/**/*.yaml`).
- Keep one output directory per run (`runs/<timestamp>_<tag>`).
- Save the exact config snapshot and command used for each run.
- Use a lock file to prevent concurrent training launches.
- Require human approval before expensive or long GPU jobs.

## Package Layout

```text
rag_ai_scientist/
  cli.py                  # Installable CLI entrypoint
  mcp_server.py           # MCP server implementation
  skills/                 # Packaged reusable skills (e.g. cms-higgs-opendata)
rag/
  index_documents.py      # Indexing backend used by setup-rag
configs/
  references.example.yaml # Example indexing config
docs/
  examples/               # RAG-friendly example notes (CMS Higgs open data, …)
```

Indexed examples and pointers: [`docs/examples/README.md`](docs/examples/README.md).

## Development

Contributor workflow, editable installs, and **PyPI release steps** are documented in [`DEV_README.md`](./DEV_README.md).

## License

- Open-source: AGPL-3.0-or-later (`LICENSE`)
- Commercial: see `LICENSE-COMMERCIAL.md`

## Security Notes

- Never commit secrets (`.env`, API keys, tokens).
- Keep local vector stores and credentials in gitignored paths.
- Review indexed sources before sharing databases externally.
