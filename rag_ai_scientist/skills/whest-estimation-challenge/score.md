# Stage 3–5: Score, benchmark, submit

## Run on public mini split (100 MLPs)

```bash
cd /path/to/whest-starterkit
uv run whest run \
  --estimator estimator.py \
  --dataset hf://aicrowd/arc-whestbench-public-2026@v1-phase1 \
  --split mini \
  --runner local
```

## Calibration targets (mini split, 2.72e11 budget)

| Estimator | `final_layer_mse` | `adjusted_final_layer_score` |
|-----------|-------------------|-------------------------------|
| mean_propagation | ~9.5e-4 | ~9.5e-5 (0.1 floor) |
| covariance_propagation | ~8.4e-5 | ~8.4e-6 (0.1 floor) |

Your goal: beat mean propagation on `adjusted_final_layer_score` while staying under budget.

## Subprocess runner (closer to grader)

```bash
uv run whest run \
  --estimator estimator.py \
  --dataset hf://aicrowd/arc-whestbench-public-2026@v1-phase1 \
  --split mini \
  --runner subprocess
```

## Submit to AIcrowd

```bash
uv run whest login    # once, with API key
uv run whest submit --estimator estimator.py --watch
```

## Pre-submission checklist

- [ ] `whest validate` passes
- [ ] Subprocess runner score within ~10% of local runner
- [ ] `uv run whest doctor` — no FAIL
- [ ] `mean_score_multiplier` near 0.1 (using ≤10% budget) or accuracy justifies higher use
- [ ] No secrets in `estimator.py`

## Compare baselines on same split

```bash
uv run whest run --estimator examples/02_mean_propagation.py \
  --dataset hf://aicrowd/arc-whestbench-public-2026@v1-phase1 --split mini --runner local

uv run whest run --estimator examples/03_covariance_propagation.py \
  --dataset hf://aicrowd/arc-whestbench-public-2026@v1-phase1 --split mini --runner local
```
