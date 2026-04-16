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

### From source (recommended while developing)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

### Verify install

```bash
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

## Package Layout

```text
rag_ai_scientist/
  cli.py                  # Installable CLI entrypoint
  mcp_server.py           # MCP server implementation
  skills/                 # Packaged reusable skills
rag/
  index_documents.py      # Indexing backend used by setup-rag
configs/
  references.example.yaml # Example indexing config
```

## Development

```bash
python -m pip install -e .
python -m pip install build
python -m build
```

## License

- Open-source: AGPL-3.0-or-later (`LICENSE`)
- Commercial: see `LICENSE-COMMERCIAL.md`

## Security Notes

- Never commit secrets (`.env`, API keys, tokens).
- Keep local vector stores and credentials in gitignored paths.
- Review indexed sources before sharing databases externally.
