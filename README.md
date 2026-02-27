# rag-ai-scientist

Agentic RAG scientist starter repo for reliability-loop development and reproducible analysis support.

## What this repository provides

- A one-command reliability loop (`scripts/reliability_loop.sh`).
- Resumable stage execution (`--from`, `--until`) with run logs in `runs/<run_id>/logs/`.
- Deterministic validation checks against published/reference values.
- Cursor-rules smoke checks with pass/fail JSON output.
- Correction wrapper with provenance logs (parameters, hashes, git SHA).
- RAG indexing and query utilities for papers, notes, and code references.

## Quick start

1. Create or activate your Python environment.
2. Install dependencies:
   - `python -m pip install -r requirements.txt`
3. Copy editable configs:
   - `cp configs/datasets.example.yaml configs/datasets.yaml`
   - `cp configs/references.example.yaml configs/references.yaml`
4. Build the local RAG database:
   - `./scripts/build_rag_db.sh`
5. Run the full reliability loop:
   - `./scripts/reliability_loop.sh`

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
- `cursor_rules`
- `corrections`
- `integration_summary`

## Data and references

- Default 2016 references are provided in `configs/datasets.example.yaml`.
- Users can provide custom AFS/EOS/local data paths in `configs/datasets.yaml`.
- Seed and custom references for RAG are configured in `configs/references.yaml`.

## Key outputs

- Run logs: `runs/<run_id>/logs/`
- Validation checks: `validation_out/checks.json`
- Rules checks: `validation_out/rules/<run_id>.json`
- Report bundle: `validation_out/reports/<run_id>/`
- Correction provenance: `runs/<run_id>/corrections/provenance.json`
- RAG DB: `.cursor/rag_db/`

## Documentation

- `docs/GETTING_STARTED.md`
- `docs/PIPELINE.md`
- `docs/DATASETS_2016.md`
- `docs/REFERENCES.md`
- `docs/RAG_VECTOR_DB.md`
- `docs/HACKATHON_TASK_BOARD.md`
