# Pipeline

The reliability loop has six stages:

1. `execution`
2. `deterministic_validation`
3. `human_reports`
4. `cursor_rules`
5. `corrections`
6. `integration_summary`

## Command interface

- Full run: `./scripts/reliability_loop.sh`
- Resume: `./scripts/reliability_loop.sh --from <stage>`
- Partial: `./scripts/reliability_loop.sh --until <stage>`
- Custom run ID: `./scripts/reliability_loop.sh --run-id <id>`

## Stage contracts

### A) Execution layer

- CLI: `./scripts/reliability_loop.sh --from execution --until execution`
- Inputs: `configs/reference_values_2016.yaml`
- Outputs:
  - `runs/<run_id>/artifacts/observed_values.json`
  - `runs/<run_id>/logs/execution.log`

### B) Deterministic checks

- CLI: `python validation/check_published_values.py ...`
- Inputs:
  - `configs/reference_values_2016.yaml`
  - `runs/<run_id>/artifacts/observed_values.json`
- Outputs:
  - `validation_out/checks.json`
  - `runs/<run_id>/logs/deterministic_validation.log`

### C) Human reports

- CLI: `python scripts/generate_report_bundle.py ...`
- Inputs: `validation_out/checks.json`
- Outputs:
  - `validation_out/reports/<run_id>/index.html`
  - `validation_out/reports/<run_id>/report.json`
  - `runs/<run_id>/logs/human_reports.log`

### D) Cursor rules checks

- CLI: `python validation/check_cursor_rules.py ...`
- Inputs:
  - `configs/cursor_rules_tests.yaml`
  - `runs/<run_id>/artifacts/cursor_rules_smoke.json`
- Outputs:
  - `validation_out/rules/<run_id>.json`
  - `runs/<run_id>/logs/cursor_rules.log`

### E) Corrections layer

- CLI: `python corrections/apply_corrections.py ...`
- Inputs:
  - `corrections/correction_registry.yaml`
  - `validation_out/checks.json`
- Outputs:
  - `runs/<run_id>/corrections/corrected_checks.json`
  - `runs/<run_id>/corrections/provenance.json`
  - `runs/<run_id>/logs/corrections.log`

### F) Integration summary

- CLI: `python scripts/summarize_run.py ...`
- Inputs: artifacts from stages B-E
- Outputs:
  - `runs/<run_id>/summary.json`
  - `runs/<run_id>/logs/integration_summary.log`
