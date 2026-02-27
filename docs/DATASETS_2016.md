# 2016 Dataset References

This repository ships sample 2016 path references and supports fully custom user data.

## Seeded references

Seed values are provided in `configs/datasets.example.yaml`, based on known locations from:

- `lb02lbgammabr/data/README.md`
- `lb02lbgammabr/data/samplelist.py`

Representative examples:

- Signal data:
  - `/eos/lhcb/wg/RD/Lb2L0Gamma/Data/2016/S28-recalib/...`
- Signal MC:
  - `/eos/lhcb/wg/RD/Lb2L0Gamma/MC/2016/15102307/S28-v41r4p4-postcalib/...`
- Normalization:
  - `/eos/lhcb/wg/RD/Lb2L0Gamma/Bd2KstGamma/...`

## Bring your own data

1. Copy template:
   - `cp configs/datasets.example.yaml configs/datasets.yaml`
2. Replace paths with your own EOS/AFS/local files.
3. Keep key names stable if downstream scripts depend on them.

Recommended contract per dataset entry:

- `name`/map key
- `path`
- `required` (`true`/`false`)

## Validation behavior

The v1 loop is path-agnostic; it uses configured values and can be extended with strict path existence checks if desired.
