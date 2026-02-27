# Runbook

## Standard run

```bash
./scripts/reliability_loop.sh
```

## Stage controls

```bash
./scripts/reliability_loop.sh --from deterministic_validation
./scripts/reliability_loop.sh --until cursor_rules
./scripts/reliability_loop.sh --run-id my_test_run
```

## Validate outputs

1. Check run logs:
   - `runs/<run_id>/logs/*.log`
2. Check deterministic output:
   - `validation_out/checks.json`
3. Check rules output:
   - `validation_out/rules/<run_id>.json`
4. Check report bundle:
   - `validation_out/reports/<run_id>/index.html`
5. Check correction provenance:
   - `runs/<run_id>/corrections/provenance.json`

## Optional Snakemake orchestration

```bash
snakemake -s workflow/Snakefile --config run_id=my_run repo_root=$(pwd) -j 1
```
