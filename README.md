# rag-ai-scientist

Open-source, agentic reliability-loop framework with a local RAG stack, MCP server, and reusable skill system for scientific and technical workflows.

## Licensing

- Open-source: AGPL-3.0-or-later (see `LICENSE`)
- Commercial: available for proprietary deployments (see `LICENSE-COMMERCIAL.md`)

## Quick Start

```bash
python3 -m venv ~/mcp_env
source ~/mcp_env/bin/activate
python -m pip install --upgrade pip
bash .cursor/setup_rag.sh
```

Then run:

```bash
./scripts/reliability_loop.sh
```

## Core Components

- Reliability loop orchestrator: `scripts/reliability_loop.sh`
- Indexer pipeline (PDF/text/code to Chroma): `rag/index_documents.py`
- Cursor wrapper for indexing: `.cursor/index_documents.py`
- MCP server for semantic retrieval + skills: `.cursor/mcp_server.py`
- Curated-note ingestion utility: `.cursor/ingest.py`
- Embedding visualization: `.cursor/visualize_rag.py`
- Project skills: `.cursor/skills/`

## RAG Setup and Usage

Index references:

```bash
python .cursor/index_documents.py --force
```

Start MCP server:

```bash
bash .cursor/run_mcp_server.sh
```

Ingest a curated note:

```bash
python .cursor/ingest.py --title "fit fix" --file my_note.md --tags fitting,debug
```

Visualize embedding space:

```bash
python .cursor/visualize_rag.py --method umap --top-n 500
```

## Configuration

- Main references config: `configs/references.yaml`
- Example references config: `configs/references.example.yaml`
- Indexing options now include:
  - `collection_name`
  - chunking parameters
  - `doc_type_rules` classification hints

## Reliability Loop Stages

`scripts/reliability_loop.sh` supports:

- `execution`
- `deterministic_validation`
- `human_reports`
- `paper_drafts`
- `cursor_rules`
- `corrections`
- `integration_summary`

You can resume or truncate execution:

```bash
./scripts/reliability_loop.sh --from deterministic_validation
./scripts/reliability_loop.sh --until cursor_rules
```

## Skills

Included:

- `.cursor/skills/rag-setup/SKILL.md`
- `.cursor/skills/_template/SKILL.md` (copy and customize)

Use in Cursor by asking:

```text
Use the rag-setup skill and configure RAG for this repository.
```

## Open Source Notes

- Do not commit secrets (`.env`, API keys).
- Use `.cursor/.env.example` as template.
- For contribution terms and dual-licensing policy, see `CONTRIBUTING.md`.
