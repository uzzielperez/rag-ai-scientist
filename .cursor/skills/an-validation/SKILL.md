---
name: an-validation
description: Generates HTML validation reports from analysis pipeline outputs, bundles them with plot assets, and publishes to CERN webEOS. Use when the user asks to create validation plots, generate HTML reports, update the validation bundle, publish results, or check the webEOS site.
---

# Validation Report Agent

Agent that generates self-contained HTML validation reports from pipeline
outputs, bundles them, and publishes to CERN webEOS.

## What this agent does

1. **Generate** HTML reports from pipeline step outputs (ROOT files,
   fit results, efficiency numbers, BR values).
2. **Bundle** all reports and their plot assets into `validation/`.
3. **Publish** to CERN webEOS and optionally Surge.
4. **Verify** the published site is accessible.

## Guiding principles

1. **Reports are self-contained HTML.** Each report embeds its own CSS
   and links to plot images (PNG/PDF) via relative paths. No external
   JS libraries required.
2. **Follow the existing style.** Match the look of the current reports:
   card layout, status badges (green/amber/red), `value-box` sections,
   blue/teal header accents. See [report-style.md](report-style.md).
3. **Every number needs a reference.** Tables must show measured value,
   reference value, uncertainty, and pass/fail status.
4. **Plots must exist before bundling.** The HTML links to PNGs in
   known directories (`plots/`, `splots*/`, `final_config_recalib/`).
   If a plot is missing, generate it or flag it - never publish broken
   image links.
5. **Confirm before publishing.** Show what will be synced to EOS and
   ask for YES before running `sync_public_html.sh`.

## Workflow

```text
Validation Report Progress
- [ ] Generate/update HTML reports from latest outputs
- [ ] Verify all linked plots exist
- [ ] Bundle into validation/ (update_validation_reports.py)
- [ ] Publish to webEOS (sync_public_html.sh)
- [ ] Run webEOS checks (check_webeos.sh)
- [ ] Optionally publish to Surge
```

## Per-step details

| Step | File |
|------|------|
| Generate an HTML report | [generate-report.md](generate-report.md) |
| Report CSS/layout conventions | [report-style.md](report-style.md) |
| Bundle and publish | [publish.md](publish.md) |
