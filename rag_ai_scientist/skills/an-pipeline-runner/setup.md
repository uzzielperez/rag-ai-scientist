# Step 0: Environment Setup

## Commands

```bash
source setLCG.sh
python -c "import ROOT; print(ROOT.gROOT.GetVersion())"
```

## Verify

- ROOT imports correctly
- kerberos ticket is valid (`klist`)
- required EOS paths are accessible

