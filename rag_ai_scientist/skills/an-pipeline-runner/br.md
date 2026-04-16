# Steps 6-7: Efficiency and Branching Ratio

Compute efficiency ratio and branching ratio from yields, efficiencies, and constants.

## Formula

```
BR(signal) = BR(norm) * (N_sig / N_norm) * (eps_norm / eps_sig) * frag_factor * subdecay_factor
```

## Typical commands

```bash
cd python/massfit
python calculate_efficiencies.py
python calculate_br_magdown.py --signal-yield <N_sig> --signal-error <err> --norm-yield <N_norm> --norm-error <err>
```

## Verify

- efficiency ratio is in expected range
- BR value and uncertainties are propagated correctly

