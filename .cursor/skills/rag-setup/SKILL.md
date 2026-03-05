---
name: rag-setup
description: Sets up local RAG dependencies and index for this repository on lxplus/CVMFS-safe Python environments. Use when the user asks to set up RAG, initialize embeddings, build/rebuild .cursor/rag_db, ingest curated notes, or run setup_rag.sh.
---

# RAG Setup (Project Skill)

## Goal

Prepare a working local RAG environment for this repo and build `.cursor/rag_db`.

## Quick Workflow (default)

From repository root, run:

```bash
python3 -m venv ~/mcp_env
source ~/mcp_env/bin/activate
python -m pip install --upgrade pip
bash .cursor/setup_rag.sh
```

Then, if requested:

```bash
./scripts/reliability_loop.sh
```

## Equivalent Explicit Workflow

Use this when `setup_rag.sh` is unavailable or debugging setup:

```bash
python -m pip install -r requirements.txt
python -m pip install -r .cursor/requirements.txt
python .cursor/index_documents.py
```

## Verification Checklist

After setup, verify:

1. `python -m pip -V` points to `~/mcp_env/...` and not `/cvmfs/...`.
2. `.cursor/rag_db/` exists and is populated.
3. No install errors from `requirements.txt` files.

## CVMFS Guardrail

If pip resolves to `/cvmfs/...`, stop and fix environment:

```bash
source ~/mcp_env/bin/activate
which python
python -m pip -V
```

Only continue when pip is in the writable venv.

## MCP Follow-up (when user asks for MCP tools)

Index first, then start server:

```bash
python .cursor/index_documents.py
bash .cursor/run_mcp_server.sh
```

Optional curated note ingestion:

```bash
python .cursor/ingest.py --title "My note" --file note.md --tags notes,workflow
```

If interpreter mismatch appears, use:

```bash
MCP_PYTHON=~/mcp_env/bin/python bash .cursor/run_mcp_server.sh
```

## Output Expectations

When complete, report:

- Python executable used
- pip location used
- whether `.cursor/rag_db` was rebuilt
- whether reliability loop and/or MCP server was started
