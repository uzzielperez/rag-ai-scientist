# Generating an HTML Validation Report

Generate reports when pipeline outputs are updated or when a user requests refreshed validation.

## Common outputs

- `python/mc_corrections/MASS_FIT_VERIFICATION_RESULTS.html`
- `docs/KSTGAMMA_MASS_FIT_VERIFICATION_RESULTS.html`
- `python/bdt/BDT_VERIFICATION_RESULTS.html`
- `python/mc_corrections/MC_CORRECTIONS_PLOTS_2016.html`
- `python/mc_corrections/MC_CORRECTIONS_PLOTS_2016_LbJpsipK.html`
- `docs/EFFICIENCY_VERIFICATION_RESULTS.html`
- `docs/BR_CALCULATION_VERIFICATION_RESULTS.html`
- `docs/EFFICIENCY_COMPARISON.html`

## Minimum report structure

1. Configuration and input paths
2. Results table (measured/reference/uncertainty/status)
3. Key plots (PNG with PDF links)
4. Status badge and generation timestamp

Use style conventions from `report-style.md`.

