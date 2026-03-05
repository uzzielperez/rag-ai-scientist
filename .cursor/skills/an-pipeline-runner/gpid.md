# Step 4: Photon PID (gPID)

Apply photon PID cuts to BDT-selected sample.

## Typical command

```bash
cd python/preselection
python applycuts2trees.py -t Lb2L0GammaTuple/DecayTree -c cuts/gPID.txt -s <bdt_selected>.root -p _gPID
```

## Verify

- `_gPID.root` file exists
- entries are reduced but non-zero
