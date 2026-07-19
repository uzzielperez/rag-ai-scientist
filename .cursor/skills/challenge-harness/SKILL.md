---
name: challenge-harness
description: Run the rag-ai-scientist challenge harness — reusable RAG → skill → validate → score loops. The reference profile is whest (ARC WhiteBox Estimation Challenge 2026). Use when the user wants the example loop, harness_run, or to add a new challenge profile.
---

# Challenge harness (example loop)

## Purpose

`rag-ai-scientist` ships a **harness**: named profiles that turn a scientific challenge into a repeatable agent loop.

**Reference profile: `whest`** — ARC WhiteBox Estimation Challenge 2026.

```
retrieve → skill → baseline → validate → score_local → [score_subprocess] → package → [submit] → [document]
```

## CLI

```bash
rag-ai-scientist harness list
rag-ai-scientist harness run --project-root /path/to/whest-starterkit --profile whest --dry-run
rag-ai-scientist harness run --project-root /path/to/whest-starterkit --profile whest --until-stage validate
rag-ai-scientist harness run --project-root /path/to/whest-starterkit --profile whest --from-stage score_local --until-stage package
```

Optional stages (`submit`, `document`, `score_subprocess`) need `--include-optional`.

## MCP tools

```json
{ "name": "harness_list_profiles" }
{ "name": "harness_run", "arguments": { "profile": "whest", "dry_run": true } }
{ "name": "harness_run", "arguments": { "profile": "whest", "until_stage": "validate" } }
```

Always load the profile skill first:

```json
{ "skill": "whest-estimation-challenge" }
{ "skill": "whest-estimation-challenge", "step": "iterate" }
```

## Agent operating order (whest)

1. Point MCP `--project-root` at `whest-starterkit` (not an unrelated repo).
2. `get_skill(whest-estimation-challenge)` then `query_analysis_knowledge` for algorithm ideas.
3. Edit `estimator.py` (start from `examples/02_mean_propagation.py`).
4. `harness_run` with `--until-stage validate`, then `score_local`.
5. Package: `whest package --estimator estimator.py --output submission.tar.gz` (note: `--output`, not `-o`).
6. Optional: Overleaf notes via `overleaf-paper-sync` / `overleaf_sync_bundle`.

## Adding a new profile

1. Add `rag_ai_scientist/harness/profiles/<name>.py` with a `Profile` + `Stage` tuple.
2. Register it in `rag_ai_scientist/harness/registry.py`.
3. Ship a matching skill under `rag_ai_scientist/skills/<name>/`.
4. Document the example in `docs/examples/`.

## Success criteria

- `harness list` shows `whest`
- Dry-run prints all non-optional stages
- Validate + score_local succeed on a working estimator
- Summary written under `runs/harness_whest_<id>/summary.json`
