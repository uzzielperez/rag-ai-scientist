# Step 1: Preselection

Apply trigger and offline cuts to raw tuples.

## Typical commands

```bash
cd python/preselection
./run_preselection.sh
```

or per sample key:

```bash
python preselection.py -s Data16_Lb2L0Gamma_MagDown
```

## Verify

- output ROOT files exist
- entry counts are non-zero
