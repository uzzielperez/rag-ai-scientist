# ARC WhiteBox Estimation Challenge 2026 — challenge story and AI-scientist integration

This note is meant to be **indexed into your vector database** so agents can answer questions about the whest challenge, scoring, algorithm trade-offs, and the estimator contract. It complements the packaged **`whest-estimation-challenge`** skill (load via MCP `get_skill` without indexing).

## After `pip install rag-ai-scientist`

The **`whest-estimation-challenge`** skill ships inside the wheel (`rag_ai_scientist/skills/`). Agents load it via **`get_skill`** with `skill: "whest-estimation-challenge"` — **no indexing required** for the workflow checklist.

**Semantic retrieval** (`query_analysis_knowledge`) needs whest docs indexed at your `--project-root`. Recommended layout inside `whest-starterkit`:

```bash
pip install rag-ai-scientist
cd whest-starterkit
mkdir -p references
# Symlink or copy challenge docs (see RAG_SETUP.md in the starter kit)
rag-ai-scientist init-references --project-root . --references-dir ./references --force
rag-ai-scientist setup-rag --project-root . --force
rag-ai-scientist mcp --project-root .
```

Index these paths for best retrieval: `docs/concepts/`, `docs/how-to/algorithm-ideas.md`, `examples/02_mean_propagation.py`, `examples/03_covariance_propagation.py`, and this file.

## The research question

> Can you predict a model's behavior by analyzing its structure, rather than just running it on many inputs?

The natural baseline is **Monte Carlo sampling**: draw random `N(0,1)` inputs, forward through the MLP, average per neuron. Accurate but slow (error ∝ 1/√k). **Mechanistic estimation** exploits weight statistics and activation math to reach similar accuracy in far less compute.

ARC frames this as ["competing with sampling"](https://www.alignment.org/blog/competing-with-sampling/).

## Problem setup

- **Architecture**: dense ReLU MLP, width `n`, depth `d`. Layer: `y = ReLU(W.T @ x)`, He init `N(0, 2/n)`.
- **Input**: each neuron i.i.d. `N(0, 1)`.
- **Output**: `(depth, width)` array — row `i` = expected activation after layer `i`.
- **Budget**: integer `flop_budget`; all ops tracked by **flopscope**.
- **Phase-1 shape**: 256 × 32. Budget ~2.72×10¹¹ FLOPs.

## Why depth makes it hard

Shallow networks: **mean propagation** (diagonal variance, independence assumption) works well.

Deep networks: dense weights create **correlations** between neurons. ReLU clips negatives, so each output depends on the **joint** pre-activation distribution — not just marginals. Error accumulates layer by layer.

## Scoring model

Leaderboard metric: **`adjusted_final_layer_score`** = mean over MLPs of:

```
final_layer_mse × max(0.1, effective_compute / flop_budget)
```

- `effective_compute = F_m + λ·R_m` (analytical FLOPs + residual wall-time penalty)
- Multiplier rewards using less compute, floor at 0.1 (10% budget)
- **Exceed budget** → predictions zeroed, multiplier forced to 1.0 (worst outcome)
- Lower is better

Diagnostic fields (no multiplier): `final_layer_mse`, `all_layers_mse`.

## Algorithm reference points (public mini split)

| Estimator | final_layer_mse | FLOPs | Notes |
|-----------|-----------------|-------|-------|
| Zeros | ~0.91 | 0 | Default starter template |
| Mean propagation | ~9.5e-4 | ~11M | O(d·w²); ~1000× better than zeros |
| Covariance propagation | ~8.4e-5 | ~1.6B | O(d·w³); ~11× better than mean prop |
| Monte Carlo | ~1/√k | O(samples·d·w²) | ~4M FLOPs per sample at 256×32 |

Bundled examples all hit the **0.1 score multiplier floor** (<1% budget).

## ReLU expectation (mean propagation core)

For pre-activation `z ~ N(μ, σ²)`:

```
E[ReLU(z)] = μ·Φ(α) + σ·φ(α)    where α = μ/σ
```

Φ = standard normal CDF, φ = PDF. Propagate `μ` and diagonal `σ²` through `W.T @ μ` and `(W²).T @ var`.

## Covariance propagation (full matrix)

Linear layer (exact): `μ_pre = W.T @ μ`, `cov_pre = W.T @ cov @ W`.

ReLU (approximate): `gain[i] = Φ(μ_pre[i]/σ_pre[i])`, off-diagonals `cov_post[i,j] ≈ gain[i]·gain[j]·cov_pre[i,j]`, diagonal from exact marginal variance.

Use `fnp.einsum("ij,ia,jb->ab", cov, w, w)` for symmetry tracking in flopscope.

## Open directions (organizer-suggested)

1. **Low-rank covariance** — `cov ≈ U U.T`, rank `k`; cost O(d·w²·k)
2. **Layer-adaptive routing** — full/low-rank cov early, diagonal late
3. **Spectral methods** — SVD of weights in `setup()` (off-budget)
4. **Importance sampling** — biased MC with re-weighting
5. **Higher-order moments** — skewness corrections to Gaussian ReLU formula

## Five-stage harness ladder

1. `uv run python estimator.py` — local Monte Carlo comparison table
2. `uv run whest validate --estimator estimator.py`
3. `uv run whest run ... --split mini --runner local`
4. `uv run whest run ... --runner subprocess`
5. `uv run whest submit --estimator estimator.py`

## Explicit limitations

- Ground truth is Monte Carlo (large N), not exact closed form.
- Covariance ReLU update is approximate; full matrix is costly.
- Leaderboard uses contest-configured λ for residual wall-time; local `--lambda-flops-per-second` may differ.
- Educational/agent workflow does not replace reading the official [estimator contract](https://github.com/AIcrowd/whest-starterkit/blob/main/docs/reference/estimator-contract.md).

## Glossary

| Term | Meaning |
|------|---------|
| **flopscope** | NumPy-compatible library counting analytical FLOPs |
| **whestbench** | Evaluation harness and MLP suite |
| **mini split** | 100 public MLPs with baked ground truth (N=1e9) |
| **adjusted_final_layer_score** | Leaderboard ranking metric |
