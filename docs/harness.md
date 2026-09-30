# Verification harness (`ras`)

The harness is **domain-free**: it verifies that a local corpus can answer a
hand-checked set of questions, fully offline, with every claim cited. This
release ships one loop mode, `A-retrieval`, which is entirely deterministic —
no network calls, no LLM calls.

## Quick start

```bash
ras init-project --project-root .   # scaffold configs/harness.yaml + data dirs
ras run     --project-root .        # PLAN/EXECUTE/VALIDATE/CORRECT loop
ras eval    --project-root .        # score the run against the golden set
ras report  --project-root .        # re-render report.md for a run
ras skills list --project-root .    # skills from passing runs
```

`ras run` exits non-zero unless every gate passes. Useful flags: `--set
KEY=VALUE` (repeatable config override), `--run ID` / `--resume`, `--json`.

## Project layout

```text
configs/harness.yaml   # config (see below)
evals/golden/*.json    # golden set (exactly one file, or set questions.path)
docs/references/papers # default corpus (corpus.paths)
runs/<run-id>/         # one directory per run
```

## Configuration (`configs/harness.yaml`)

All keys are optional; defaults:

| Section | Key | Default | Meaning |
|---|---|---|---|
| run | name | retrieval-verification | Run/skill name |
| run | mode | A-retrieval | Loop mode (this release: A-retrieval) |
| run | max_attempts | 2 | EXECUTE/VALIDATE attempts before a gap |
| corpus | paths | [docs/references/papers] | Files or directories to index |
| corpus | extensions | [.pdf, .md, .txt] | Extensions to pick up |
| index | chunk_chars | 1200 | Chunk size (min 200) |
| index | chunk_overlap | 200 | Overlap, must be < chunk_chars |
| retrieval | top_k | 5 | Chunks retrieved per question |
| retrieval | min_score | 8.0 | Minimum BM25 score for a hit |
| retrieval | min_terms | 2 | Informative matched terms required |
| questions | path | null | Golden set; null = single file in evals/golden/ |
| questions | tier1_min | 1.0 | Required Tier 1 pass ratio |
| questions | tier23_min | 0.8 | Required Tier 2/3 pass ratio |
| skills | generate | true | Write a skill for each passing run |
| skills | mirror_to_cursor | false | Also mirror the skill to .cursor/skills/ |
| budgets | max_steps | 40 | Plan step budget |
| budgets | max_seconds | 900 | Wall-clock budget |

Override anything on the CLI: `ras run --set retrieval.min_score=4.0`.

## Golden set

A golden set is a JSON (or YAML) file with `name`, `description` and
`questions`. Each question looks like:

```json
{
  "id": "Q01",
  "tier": 1,
  "question": "What integrated luminosity was collected for this measurement?",
  "expect": "supported",
  "expect_keywords": ["9 fb", "luminosity"],
  "notes": "Abstract and introduction both state 9 fb-1."
}
```

- `expect` is `supported` (the corpus must contain the answer) or `unresolved`
  (negative control — the corpus must stay silent).
- `tier` 1 = must-pass fact; tiers 2 and 3 = secondary / negative controls.
- If `questions.path` is null and `evals/golden/` contains exactly one data
  file it is used; several files are an error (the harness refuses to guess).

## The loop

1. **PLAN** — the `deterministic-planner` builds `artifacts/plan.json`: four
   steps (`index`, `answer`, `skills`, `report`), each declaring its gates.
2. **EXECUTE** — steps run in order and write artifacts under the run dir.
3. **VALIDATE** — gates of the executed steps run; failures are listed by id.
4. **CORRECT** — the planner applies the first matching remedy and re-plans:
   - `widen_chunk_window` — raise `index.chunk_chars`
   - `lower_min_score` — floor `retrieval.min_score` at 4.0
   - `increase_top_k` — raise `retrieval.top_k`
   - `loosen_min_terms` — lower `retrieval.min_terms`

   After `run.max_attempts` failing attempts the run ends as a **gap**: a
   `gap.md` explains what to change (corpus, golden set or a new planner
   remedy). `report`-stage gates are checked once at finalization, after
   `report.md` exists.

## Gates

| Gate | Step | Checks |
|---|---|---|
| index_files | index | declared index artifacts exist |
| index_integrity | index | index verifies against `chunks.jsonl` |
| index_deterministic | index | rebuild produces identical chunks and ids |
| analysis_map_shape | answer | `analysis_map.json` has every required key |
| analysis_map_nonempty | answer | at least one question item |
| citations_resolve | answer | every evidence hash resolves in the index |
| claim_status_valid | answer | statuses come from the allowed vocabulary |
| golden_tiers | answer | tier ratios meet `tier1_min` / `tier23_min` |
| skill_gate_consistency | skills | the skill's gate list matches the plan |
| report_sections | report | `report.md` has every required section |

## Run directory

```text
runs/<run-id>/
  state.json            # phase, iteration, applied remedies, gate history
  manifest.json         # inputs (corpus files + golden set) with hashes, outcome
  report.md             # final report (Summary, Corpus, Plan, Coverage, ...)
  gap.md                # only when the outcome is a gap
  index/                # chunks.jsonl + index.json
  artifacts/            # plan.json, analysis_map.json, retrieval traces
  logs/                 # per-step output + gate PASS/FAIL lines
  skills/<name>/        # generated skill (SKILL.md, answer, report, ...)
```

`ras run --resume` (or `--resume --run <id>`) skips steps whose artifacts and
plan revision already validate, then re-validates and finalizes.

## Skills

Passing runs generate a skill under `runs/<id>/skills/<name>/` containing
`SKILL.md`, the answer, index notes, report and skills summary. Resolution
order at read time: run dir → project data dir (`.rag-ai-scientist/skills/`)
→ IDE mirror (`.cursor/skills/`) → packaged (`_template` only; nothing is
written into `site-packages`). Promote with `ras skills promote <name>`; set
`skills.mirror_to_cursor: true` to also write `.cursor/skills/<name>/` after
each run.

## Legacy profile interface

`rag-ai-scientist harness list|run` and the MCP tools `harness_list_profiles`
/ `harness_run` expose the older profile-based interface. **No profiles ship
with this release**: `--profile` (and the MCP `profile` argument) is required,
and you register your own with `harness.registry.register(...)`.

