# Scientific Run Harness

The harness separates reusable execution/provenance from workflow-specific science:

- A `Profile` defines ordered `Stage`s. Each stage can run a command or describe an agent/MCP action.
- The runner executes a selected stage window, stops on the first failed command, and records stage status and duration.
- Every run writes `summary.json` plus a versioned `manifest.json` under `runs/harness_<profile>_<run-id>/`.
- A profile supplies domain-specific metrics and artifact paths; the manifest builder fingerprints explicit configs, inputs, and artifacts without copying their contents.

## Define A Workflow

Profiles can be registered by an application or analysis-specific adapter. A RAG skill is optional:

```python
import sys
from pathlib import Path

from rag_ai_scientist.harness import Profile, Stage, register_profile, run_harness

profile = Profile(
    name="closure_check",
    description="Run a frozen closure validation.",
    stages=(
        Stage(
            name="closure",
            description="Evaluate the configured reference closure.",
            command=(sys.executable, "validation/run_closure_test.py", "--step", "efficiency"),
        ),
    ),
)
register_profile(profile)

result = run_harness(
    project_root=Path("."),
    profile_name="closure_check",
    run_id="efficiency-20260929-01",
    task_id="task-14",
    seed=42,
    config_paths=("configs/closure_tests.yaml",),
    input_paths=("validation/overlays/efficiency.yaml",),
    dataset_ids=("analysis-sample:v1",),
    metrics={"closure_pull": 0.02},
    software_versions={"ROOT": "6.32.02"},
)
```

For workflows that already own their execution loop, use `build_run_manifest()` and `write_run_manifest()` from `rag_ai_scientist.harness`; this avoids forcing them into the stage runner. Record exact commands, frozen criteria, metrics, and artifacts from that workflow.

## Manifest Contents

`manifest.json` uses `schema_version: 1` and records:

- run/task IDs, timestamps, status, Git commit/branch/dirty state, and submodule status;
- command and seed, Python/platform and caller-supplied software versions;
- dataset identifiers and SHA-256 fingerprints for explicitly selected configs, input paths, and artifacts;
- per-stage command details, outcome, and duration, plus domain metrics.

Directory fingerprints hash each regular file and its relative name in sorted order. Symlinks are excluded; a symlink supplied as the root path is rejected. Inputs are fingerprinted, not copied. Hashing a large directory can take time, so pass only the paths needed to identify a run and use dataset IDs for remote or externally managed data.

The CLI accepts `--task-id`, `--seed`, repeated `--config`, `--input`, and `--dataset-id` options for registered profiles available in that process. `run_harness()` additionally accepts metrics, artifact paths, and software-version metadata.

This manifest is provenance, not a guarantee of bitwise reproducibility. It cannot freeze remote datasets or an uncontrolled environment by itself; review manifests before sharing because explicitly supplied external paths may be absolute.