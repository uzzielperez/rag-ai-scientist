# Step 3: BDT Training and Application

Train A/B split BDTs, optimize cut with Punzi FoM, and apply cross-wise.

## Typical commands

```bash
cd python/bdt
./run_bdt_AB.sh
```

## Verify

- model files exist (`bdt.pkl`)
- cut files exist (`bdt_cut_punzi.txt`)
- selected output has non-zero entries
