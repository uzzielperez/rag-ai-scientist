# Stage 1–2: Iterate and validate locally

## Preconditions

- `whest-starterkit` cloned and `uv sync` completed
- `estimator.py` exists at repo root
- Optional: RAG indexed (see main SKILL.md)

## Steps

1. **Baseline comparison**

```bash
cd /path/to/whest-starterkit
uv run python estimator.py
uv run python estimator.py --baseline mean_propagation
uv run python estimator.py --baseline covariance_propagation
```

2. **Copy a baseline into your estimator** (start from mean propagation)

```bash
cp examples/02_mean_propagation.py estimator.py
# Edit class name if needed; keep Estimator(BaseEstimator)
```

3. **Implement your idea in `predict()`**

Query RAG first:

```
query: "low-rank covariance propagation ReLU MLP flopscope"
query: "ReLU expectation formula Phi alpha mean propagation"
```

4. **Validate contract**

```bash
uv run whest validate --estimator estimator.py
```

5. **Profile FLOPs**

```python
import flopscope as flops
from estimator import Estimator
from local_engine import build_mlp

mlp = build_mlp(256, 32, 0)
with flops.BudgetContext(flop_budget=272_000_000_000) as b:
    Estimator().predict(mlp, b.flop_budget)
print(b.summary())
```

## Success criteria

- `whest validate` passes
- `final_layer_mse` on one MLP (from `estimator.py` output) < mean propagation (~0.0017 at 100k MC samples)
