# Troubleshooting

## `ModuleNotFoundError: yaml` or sklearn

- Install dependencies:
  - `python -m pip install -r requirements.txt`

## `Permission denied` when running scripts

- Ensure executable bits are set:
  - `chmod +x scripts/reliability_loop.sh scripts/build_rag_db.sh`

## No documents indexed

- Verify reference config exists:
  - `configs/references.yaml` or `configs/references.example.yaml`
- Check paths in `sources[].paths` are valid and readable.

## Reliability loop fails in deterministic validation

- Confirm:
  - `configs/reference_values_2016.yaml` exists
  - `runs/<run_id>/artifacts/observed_values.json` was generated

## Rules checks fail

- Inspect:
  - `configs/cursor_rules_tests.yaml`
  - `runs/<run_id>/artifacts/cursor_rules_smoke.json`

## Correction provenance shows `git_sha: unknown`

- This is expected when running outside a git repository.
- Initialize git in this repo if SHA tracking is required.
