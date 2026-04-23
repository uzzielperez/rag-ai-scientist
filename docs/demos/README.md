# Demos Checklist Usage (Dev)

This folder contains templates for running demo scenarios under the `dev` branch specs.

## Files

- `SPECS_CHECKLIST.md`: master execution checklist template for one agent run.

## How agents should use this

1. Create one checklist copy per run:
   - recommended path: `docs/demos/runs/<run_id>_checklist.md`
2. Fill sections in order during execution (do not defer all fields to the end).
3. Attach or reference generated artifacts in the run summary.
4. Mark final status only after validation and security post-checks complete.

## Naming convention

- `run_id`: `<YYYYMMDD>-<short-topic>-<nn>`
- Example: `20260423-higgs-baseline-01`

## Minimum completion rule

A run is considered complete only if all of the following are present:

- recorded inputs and versions,
- deterministic execution metadata,
- validation outcome with metrics,
- security leakage check outcome,
- reproducibility replay result,
- reviewer sign-off.

## Branch policy reminder

- Templates and run records described here are for development in `dev`.
- Do not treat checklist completion as release approval for `main` by itself.
