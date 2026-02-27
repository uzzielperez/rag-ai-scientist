# Hackathon Task Board - Reliability Loop

This board defines parallel workstreams to deliver a first usable reliability loop.

## Hackathon objective

Ship a v1 loop with:
- execution orchestration,
- validation (HTML + numeric checks + rules checks),
- correction traceability,
- one-command run for humans.

---

## Parallel tracks

## Track A - Execution layer
- Owner: `TBD`
- Scope:
  - build `workflow/Snakefile` (or robust bash runner),
  - add resume support (`--from`, `--until`),
  - standardize per-step logs under `runs/<run_id>/logs/`.
- Deliverable:
  - orchestration file + successful dry-run DAG.
- Manual check:
  - run command manually and verify ordered steps + logs.

## Track B - Validation layer (deterministic checks)
- Owner: `TBD`
- Scope:
  - implement `validation/check_published_values.py`,
  - add `configs/reference_values_2016.yaml` with tolerances,
  - emit `validation_out/checks.json`.
- Deliverable:
  - pass/fail JSON + CLI summary table.
- Manual check:
  - run checker manually and inspect per-metric pass/fail.

## Track C - Validation layer (human reports)
- Owner: `TBD`
- Scope:
  - generate/report bundle for HTML pages,
  - ensure linked plots resolve from bundled paths,
  - include replication instructions and timestamps.
- Deliverable:
  - publish-ready HTML bundle and index.
- Manual check:
  - open reports in browser and verify all plots load.

## Track D - Cursor rules compliance checks
- Owner: `TBD`
- Scope:
  - implement `validation/check_cursor_rules.py`,
  - add `configs/cursor_rules_tests.yaml`,
  - output `validation_out/rules/<run_id>.json`.
- Deliverable:
  - rule smoke tests with pass/fail output.
- Manual check:
  - run smoke prompts manually and compare expected markers.

## Track E - Correction layer (provenance logging)
- Owner: `TBD`
- Scope:
  - implement `corrections/apply_corrections.py` wrapper,
  - define `corrections/correction_registry.yaml`,
  - log run provenance and before/after stats.
- Deliverable:
  - one correction run with full trace logs.
- Manual check:
  - inspect JSON/YAML logs and checksum consistency.

## Track F - Integration and operations
- Owner: `TBD`
- Scope:
  - provide one top-level command (example: `scripts/reliability_loop.sh`),
  - wire tracks A-E outputs,
  - finalize runbook and troubleshooting notes.
- Deliverable:
  - end-to-end demo run with status summary.
- Manual check:
  - execute one command and validate all artifacts are produced.

---

## Dependency map

- A, B, C, D, E can start in parallel.
- F can start with stubs, then integrate A-E outputs.
- Final demo depends on F and at least one successful run from B, C, and E.

---

## Suggested team split

- 4 people:
  - A, (B+D), C, (E+F)
- 5 people:
  - A, B, C, D, (E+F)
- 6 people:
  - A, B, C, D, E, F

---

## Timebox (2-day example)

- Day 1 AM:
  - kickoff and define file/output contracts.
- Day 1 PM:
  - parallel implementation on tracks A-E.
- Day 2 AM:
  - integration in track F, interface fixes.
- Day 2 PM:
  - end-to-end run, docs polish, demo rehearsal.

---

## Output contracts (required for each track)

Each track must provide:
- CLI command,
- input/output paths,
- output schema (json/yaml where applicable),
- failure codes/messages,
- quick manual verification checklist.

---

## Definition of done (hackathon)

- `./scripts/reliability_loop.sh` runs without manual code edits.
- HTML reports are generated and browsable.
- Published-number checks output pass/fail JSON.
- Cursor-rules checks output pass/fail JSON.
- Correction run logs include parameters, hashes, and git SHA.
- README contains manual run steps and troubleshooting.

---

## Immediate next actions

1. Assign owners to tracks A-F.
2. Create issue tickets from each track section.
3. Lock output schemas before coding.
4. Hold 30-minute integration checkpoint every half day.
