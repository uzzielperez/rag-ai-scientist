# Golden question set

Exactly one `*.json` / `*.yaml` file in this directory is used by the
harness (or point `questions.path` at one explicitly). Each question has:

- `tier`: 1 (must resolve), 2 or 3 (may miss up to `questions.tier23_min`)
- `expect`: `supported` or `unresolved` (negative control)
- `expect_keywords`: exact terms that must appear in the retrieved text
  for the claim to count as supported
