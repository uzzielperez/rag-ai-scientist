---
name: an-pipeline-runner
description: Runs the full Lb2Lgamma BR analysis pipeline autonomously step-by-step - from environment setup through preselection, MC corrections, BDT, gPID, mass fit, efficiency, and branching-ratio extraction. Use when the user asks to run the pipeline, execute analysis steps, or resume the analysis from a specific point.
---

# Analysis Pipeline Runner

Autonomous agent for executing the Lb->Lambda gamma branching-ratio measurement
pipeline. Each step is self-contained: verify prerequisites, run, check
outputs, report. The agent stops on first failure and proposes a fix.

## Pipeline overview

```text
Step 0  Environment setup        source setLCG.sh
Step 1  Preselection             python/preselection/
Step 2  MC corrections           python/mc_corrections/ (Snakemake)
Step 3  BDT training + apply     python/bdt/
Step 4  Photon PID (gPID)        python/preselection/ (cut file)
Step 5  Mass fit                 python/massfit/
Step 6  Efficiency               python/massfit/calculate_efficiencies.py
Step 7  Branching ratio          python/massfit/calculate_br_magdown.py
Step 8  Validation               compare to reference values
```

## Guiding principles

1. **Run in small verified steps.** After each command, check exit code
   and expected output before proceeding.
2. **Stop on first failure.** Print the failing command, its stderr, and
   a proposed fix. Do not continue until the user confirms.
3. **Never overwrite data silently.** All writes go to `validation_out/`
   or documented output paths. Ask before overwriting existing files.
4. **Confirm before long-running steps.** BDT training and Snakemake can
   take hours. Show the command and estimated wall time; wait for YES.
5. **Use per-step skill files** for detailed checklists. Call
   `get_skill(skill="an-pipeline-runner", step="<name>")` before each
   step for the exact commands and validation criteria.
6. **Use the orchestrator script for real runs.** Prefer
   `scripts/run_step_with_corrector.sh` for pre-flight checks,
   checkpointing, feedback capture, and rollback.

## Progress checklist

```text
Lb->Lambda gamma Pipeline Progress
- [ ] Step 0: Environment setup
- [ ] Step 1: Preselection
- [ ] Step 2: MC corrections
- [ ] Step 3: BDT training + application
- [ ] Step 4: gPID cut
- [ ] Step 5: Mass fit
- [ ] Step 6: Efficiency calculation
- [ ] Step 7: Branching-ratio extraction
- [ ] Step 8: Validation against reference
```

## Per-step details

| Step | File |
|------|------|
| 0 | [setup.md](setup.md) |
| 1 | [preselection.md](preselection.md) |
| 2 | [mc-corrections.md](mc-corrections.md) |
| 3 | [bdt.md](bdt.md) |
| 4 | [gpid.md](gpid.md) |
| 5 | [massfit.md](massfit.md) |
| 6-7 | [br.md](br.md) |
| 8 | [validate.md](validate.md) |

