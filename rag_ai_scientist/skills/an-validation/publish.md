# Bundle and Publish Validation Reports

## One-shot command

```bash
./scripts/publish_validation_webeos.sh
```

## Manual sequence

1. Build bundle:

```bash
python scripts/update_validation_reports.py
```

2. Sync to EOS:

```bash
./scripts/sync_public_html.sh
```

3. Verify deployment:

```bash
./scripts/check_webeos.sh
```

Always confirm with the user before live publishing.

