# Step 5: Mass Fit

Fit the signal mass spectrum to extract `N_sig` and uncertainties.

## Typical commands

```bash
cd python/massfit
./run_massfit.sh
```

or:

```bash
python fit_lb2l0gamma.py --data <data>.root --mc <mc>.root --tree Lb2L0GammaTuple/DecayTree --output plots/massfit_2016 --match-2016
```

## Verify

- fit converges
- JSON outputs are produced
- `N_sig` is physically sensible

