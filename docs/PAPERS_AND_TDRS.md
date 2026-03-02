# Papers and TDR Automation

This repository can automatically refresh LaTeX draft files as part of the reliability loop.

## What is auto-updated

During the `paper_drafts` stage, the script:

- reads `validation_out/checks.json`,
- loads template definitions from `configs/paper_templates.yaml`,
- generates updated LaTeX drafts in `runs/<run_id>/papers/`.

Generated placeholders include:

- `{{RUN_ID}}`
- `{{GENERATED_UTC}}`
- `{{CHECKS_SUMMARY}}`
- metric placeholders from deterministic checks, for example:
  - `{{N_LB_TO_LAMBDA_GAMMA}}`
  - `{{N_B0_TO_KST_GAMMA}}`
  - `{{BR_LB_TO_LAMBDA_GAMMA}}`

## Default templates

- `papers/templates/basic/paper/main.tex`
- `papers/templates/basic/tdr/main.tex`

## Add your own templates

1. Create a new directory under `papers/templates/`.
2. Add your LaTeX template files.
3. Register the template in `configs/paper_templates.yaml`:

```yaml
drafts:
  - name: my_custom_paper
    template_dir: ./papers/templates/my_group/paper
    main_file: main.tex
```

4. Run the loop:
   - `./scripts/reliability_loop.sh --from paper_drafts --until paper_drafts`
