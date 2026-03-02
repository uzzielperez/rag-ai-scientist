# rag-ai-scientist

Agentic RAG scientist repo for reliability-loop development, reproducible analysis support, and local Cursor assets.

## Minimal start (most important)

From this repository root:

```bash
# Environment first (important on lxplus/CVMFS)
python3 -m venv ~/mcp_env
source ~/mcp_env/bin/activate
python -m pip install --upgrade pip

# One-command setup + local RAG build
bash .cursor/setup_rag.sh

# Run reliability loop
./scripts/reliability_loop.sh
```

Equivalent explicit steps:

```bash
python -m pip install -r requirements.txt
python -m pip install -r .cursor/requirements.txt
python .cursor/index_documents.py
./scripts/reliability_loop.sh
```

If you want to use MCP tools from this repo, always index first and then start the server:

```bash
python .cursor/index_documents.py
bash .cursor/run_mcp_server.sh
```

Expected MCP startup output now includes:

- `Initializing MCP server components...`
- `Loading RAG database into memory...`
- `RAG database loaded: ...`
- `MCP server ready - waiting for connections...`

`run_mcp_server.sh` automatically prefers `~/mcp_env/bin/python` when available.
You can override interpreter selection with:

```bash
MCP_PYTHON=/path/to/python bash .cursor/run_mcp_server.sh
```

## What this repository provides

- A one-command reliability loop (`scripts/reliability_loop.sh`).
- Local `.cursor/rag_db` generation (`scripts/build_rag_db.sh`).
- Root `.cursorrules` ownership for project-specific agent rules.
- Resumable stage execution (`--from`, `--until`) with run logs in `runs/<run_id>/logs/`.
- Deterministic validation checks against published/reference values.
- Automatic LaTeX draft updates for papers and TDRs.
- Cursor-rules smoke checks with pass/fail JSON output.
- Correction wrapper with provenance logs (parameters, hashes, git SHA).
- RAG indexing and query utilities for papers, notes, and code references.

## Quick start

1. Create or activate your Python environment (recommended on lxplus/CVMFS):
   - `python3 -m venv ~/mcp_env`
   - `source ~/mcp_env/bin/activate`
2. Install dependencies:
   - `python -m pip install --upgrade pip`
3. Copy editable configs:
   - `cp configs/datasets.example.yaml configs/datasets.yaml`
   - `cp configs/references.example.yaml configs/references.yaml`
4. Run one-command setup for dependencies + RAG index:
   - `bash .cursor/setup_rag.sh`
5. Run the full reliability loop:
   - `./scripts/reliability_loop.sh`

If you see `OSError: [Errno 30] Read-only file system` pointing to `/cvmfs/.../site-packages`,
`pip` is using the read-only LCG/CVMFS Python. Reactivate your venv and verify:

- `source ~/mcp_env/bin/activate`
- `which python`
- `python -m pip -V`

`python -m pip -V` should point to `~/mcp_env/...`, not `/cvmfs/...`.
`.cursor/setup_rag.sh` now checks this and exits early if pip resolves to `/cvmfs/...`.

## One-command run

Run all stages:

- `./scripts/reliability_loop.sh`

Resume from a stage:

- `./scripts/reliability_loop.sh --from deterministic_validation`

Run only part of the pipeline:

- `./scripts/reliability_loop.sh --until cursor_rules`

Supported stages:

- `execution`
- `deterministic_validation`
- `human_reports`
- `paper_drafts`
- `cursor_rules`
- `corrections`
- `integration_summary`

## Data and references

- Default 2016 references are provided in `configs/datasets.example.yaml`.
- Users can provide custom AFS/EOS/local data paths in `configs/datasets.yaml`.
- Seed and custom references for RAG are configured in `configs/references.yaml`.

### Add your own files to RAG

1. Put your files in a readable location (recommended shared location):
   - `/afs/cern.ch/user/<username>/public/my_references/`
   - Avoid `/work/.../private/...` paths if collaborators need access.
2. Add those paths to `configs/references.yaml` under `sources[].paths`.
3. Set matching `extensions` for your files (for example: `.pdf`, `.md`, `.txt`, `.tex`, `.py`).
4. Rebuild the index:
   - `source ~/mcp_env/bin/activate`
   - `python .cursor/index_documents.py --force`
5. Start MCP server (after indexing completes):
   - `bash .cursor/run_mcp_server.sh`
   - If startup fails with `ModuleNotFoundError: No module named 'mcp'`, verify the interpreter:
     - `MCP_PYTHON=~/mcp_env/bin/python bash .cursor/run_mcp_server.sh`

Example `configs/references.yaml` entry:

```yaml
sources:
  - name: "my_references"
    paths:
      - "/afs/cern.ch/user/<username>/public/my_references/papers"
      - "/afs/cern.ch/user/<username>/public/my_references/notes.md"
    extensions: [".pdf", ".md", ".txt", ".tex"]
```

## Key outputs

- Run logs: `runs/<run_id>/logs/`
- Validation checks: `validation_out/checks.json`
- Rules checks: `validation_out/rules/<run_id>.json`
- Report bundle: `validation_out/reports/<run_id>/`
- Paper drafts: `runs/<run_id>/papers/`
- Correction provenance: `runs/<run_id>/corrections/provenance.json`
- RAG DB: `.cursor/rag_db/`

## Documentation

- `docs/GETTING_STARTED.md`
- `docs/PIPELINE.md`
- `docs/DATASETS_2016.md`
- `docs/REFERENCES.md`
- `docs/RAG_VECTOR_DB.md`
- `docs/PAPERS_AND_TDRS.md`
- `docs/HACKATHON_TASK_BOARD.md`
