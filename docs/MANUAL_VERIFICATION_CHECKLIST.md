# Manual Verification Checklist

## Execution layer

- [ ] Run `./scripts/reliability_loop.sh --from execution --until execution`
- [ ] Confirm `runs/<run_id>/logs/execution.log` exists
- [ ] Confirm `runs/<run_id>/artifacts/observed_values.json` exists

## Deterministic checks

- [ ] Run until `deterministic_validation`
- [ ] Confirm `validation_out/checks.json` exists
- [ ] Inspect per-metric pass/fail entries

## Human reports

- [ ] Run until `human_reports`
- [ ] Open `validation_out/reports/<run_id>/index.html`
- [ ] Verify table rows and status values render correctly

## Paper and TDR draft updates

- [ ] Run until `paper_drafts`
- [ ] Confirm `runs/<run_id>/papers/manifest.json` exists
- [ ] Open generated `main.tex` files and verify placeholders are resolved

## Cursor rules checks

- [ ] Run until `cursor_rules`
- [ ] Confirm `validation_out/rules/<run_id>.json` exists
- [ ] Verify missing markers list is empty for pass cases

## Corrections and provenance

- [ ] Run until `corrections`
- [ ] Confirm `runs/<run_id>/corrections/corrected_checks.json` exists
- [ ] Confirm `runs/<run_id>/corrections/provenance.json` includes parameters, hashes, git SHA

## End-to-end integration

- [ ] Run full `./scripts/reliability_loop.sh`
- [ ] Confirm `runs/<run_id>/summary.json` exists
- [ ] Verify summary points to all expected artifacts
