# Getting Started

This guide is for new users onboarding to `rag-ai-scientist`.

## 1) Install Cursor

1. Download Cursor from `https://cursor.com`.
2. Install it for your operating system.
3. Open this repository folder in Cursor.
4. Sign in if needed.

## 2) System prerequisites

- Python 3.10+.
- Access to your data paths (AFS/EOS/local).
- Optional: `git` for provenance SHA in correction logs.

## 3) Create Python environment

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4) Configure data and references

```bash
cp configs/datasets.example.yaml configs/datasets.yaml
cp configs/references.example.yaml configs/references.yaml
```

Then edit:

- `configs/datasets.yaml` to point to your own data.
- `configs/references.yaml` to include your papers/notes/code references.

## 5) Build the RAG vector database

```bash
./scripts/build_rag_db.sh
```

## 6) Run the reliability loop

```bash
./scripts/reliability_loop.sh
```

Use resume controls:

```bash
./scripts/reliability_loop.sh --from deterministic_validation
./scripts/reliability_loop.sh --until cursor_rules
```

## 7) Inspect outputs

- `runs/<run_id>/logs/`
- `validation_out/checks.json`
- `validation_out/rules/<run_id>.json`
- `validation_out/reports/<run_id>/index.html`
- `runs/<run_id>/corrections/provenance.json`
