---
name: whest-estimation-challenge
description: Guides the ARC WhiteBox Estimation Challenge 2026 (whest-starterkit) — predict per-neuron mean activations in ReLU MLPs under a FLOP budget using rag-ai-scientist retrieval and the whestbench harness. Use when the user wants to compete in whest, write estimator.py, run whest validate/run, compare mean/covariance propagation baselines, or submit to AIcrowd.
---

# ARC WhiteBox Estimation Challenge — AI scientist workflow

## Goal

Help the user **compete in the [ARC WhiteBox Estimation Challenge 2026](https://www.aicrowd.com/challenges/arc-white-box-estimation-challenge-2026)** by building a compute-efficient `estimator.py` that predicts expected neuron activations in randomly initialized ReLU MLPs — **without** brute-force Monte Carlo sampling.

## Before you improvise

1. Call **`get_skill`** with `skill=whest-estimation-challenge` and `step=iterate` or `step=score` for stage-specific checklists.
2. Call **`query_analysis_knowledge`** for algorithm ideas (mean propagation, covariance, low-rank, hybrids) **after** the project has indexed whest docs — see **Indexing** below.
3. Read bundled baselines in the starter kit: `examples/02_mean_propagation.py`, `examples/03_covariance_propagation.py`.

## The problem (one paragraph)

Given a width-`n`, depth-`d` ReLU MLP with He-initialized weights and `N(0,1)` inputs, predict the **mean activation of every neuron after every layer** — a `(depth, width)` array. Ground truth is Monte Carlo. Your score is **final-layer MSE × compute multiplier** (`max(0.1, flops_used / budget)`). Lower is better. Exceeding the FLOP budget zeros predictions.

Phase-1 competition shape: **256 × 32**. Budget: ~`2.72e11` FLOPs.

## Canonical repos and links

| Asset | URL |
|-------|-----|
| Challenge page | https://www.aicrowd.com/challenges/arc-white-box-estimation-challenge-2026 |
| Starter kit | https://github.com/AIcrowd/whest-starterkit |
| Public dataset | https://huggingface.co/datasets/aicrowd/arc-whestbench-public-2026 |
| MLP explorer | https://aicrowd.github.io/whestbench-explorer/ |
| ARC framing blog | https://www.alignment.org/blog/competing-with-sampling/ |

## Suggested user journey (5-stage ladder)

| Stage | What | Command |
|-------|------|---------|
| 1 | Local math, edit `predict()` | `uv run python estimator.py` |
| 2 | Contract validation | `uv run whest validate --estimator estimator.py` |
| 3 | Score on 100 public MLPs | `uv run whest run --estimator estimator.py --dataset hf://aicrowd/arc-whestbench-public-2026@v1-phase1 --split mini --runner local` |
| 4 | Subprocess isolation | same with `--runner subprocess` |
| 5 | Package + submit | `uv run whest submit --estimator estimator.py` |

### Harness (example loop)

This challenge is the **reference harness profile** for `rag-ai-scientist`:

```bash
rag-ai-scientist harness run --project-root . --profile whest --dry-run
rag-ai-scientist harness run --project-root . --profile whest --until-stage validate
```

MCP: `harness_run` with `profile=whest`. See skills **`challenge-harness`** and **`overleaf-paper-sync`**.

Package note: use `--output submission.tar.gz` (not `-o`).

## Algorithm ladder (accuracy vs FLOPs)

| Approach | `final_layer_mse` (mini) | FLOPs (256×32) | When |
|----------|--------------------------|----------------|------|
| Zeros baseline | ~0.91 | 0 | Starting point |
| Mean propagation | ~9.5e-4 | ~11M | Default first implementation |
| Covariance propagation | ~8.4e-5 | ~1.6B | Accuracy ceiling reference |
| Low-rank covariance | TBD | O(d·w²·k) | **Promising open direction** |
| Layer-adaptive hybrid | TBD | varies | Full cov early, diagonal late |
| Monte Carlo sampling | ~1/√k | O(samples·d·w²) | Sanity check only |

All bundled examples spend <1% of budget → score floor at 0.1 multiplier.

## pip-install + RAG integration

- **`get_skill`** with `skill=whest-estimation-challenge` works immediately after `pip install rag-ai-scientist` (packaged markdown).
- **`query_analysis_knowledge`** needs indexed whest docs. From the starter kit root:

```bash
pip install rag-ai-scientist
rag-ai-scientist init-references --project-root . --references-dir ./references --force
rag-ai-scientist setup-rag --project-root . --force
```

Populate `references/` with symlinks or copies of `docs/`, `examples/`, and this package's `docs/examples/whest_estimation_challenge_story.md`. See `RAG_SETUP.md` in whest-starterkit.

## Implementation rules (contract)

- Import **`flopscope.numpy as fnp`** and **`flopscope as flops`** — all math is FLOP-tracked.
- `predict(self, mlp, budget) -> fnp.ndarray` returns shape `(mlp.depth, mlp.width)`.
- Use `fnp.einsum("ij,ia,jb->ab", cov, w, w)` for symmetric covariance updates (not chained matmul).
- Seed RNGs from `mlp.seed` (per-MLP) and `ctx.seed` in `setup()` (submission-level).
- Free ops: `fnp.zeros`, `fnp.eye`, `fnp.transpose`, `fnp.stack`, indexing.

## Validation gates

- [ ] `uv run whest validate --estimator estimator.py` passes
- [ ] `uv run python estimator.py --baseline mean_propagation` shows MSE << 1.0
- [ ] `whest run` on mini split: `adjusted_final_layer_score` beats mean propagation baseline
- [ ] FLOP usage stays under budget (check `mean_score_multiplier` in report)
- [ ] `uv run whest doctor` shows no FAIL rows

## Failure recovery

| Issue | Action |
|-------|--------|
| `uv: command not found` | `brew install uv` or official installer |
| Shape mismatch | Return exactly `(depth, width)`; row `i` = layer `i` post-ReLU means |
| Budget exceeded | Predictions zeroed; profile with `flopscope.BudgetContext` + `budget.summary()` |
| RAG returns Higgs papers | Re-index with whest paths; confirm `references/` contains whest docs |
| Local score great, submission worse | Run Stage 4 subprocess; check for global state / RNG reuse |

## Next steps

- `get_skill` + `step=iterate` — local development loop
- `get_skill` + `step=score` — benchmarking and submission
- `get_skill` skill=`challenge-harness` — run the packaged example loop
- `get_skill` skill=`overleaf-paper-sync` — push notes/paper to Overleaf
