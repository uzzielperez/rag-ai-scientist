# Tutorial — your first gated run in ten minutes

Everything here runs offline. The index is lexical, so there is no model to
download, no API key to paste and no nondeterminism to fight: run it twice and
you get the same verdict, which is exactly the point of the harness.

**What you are building:** a project that answers questions from your own
documents, refuses to answer when the documents do not support an answer, and
proves both claims in a written report.

## Before you start

```bash
python -m pip install rag-ai-scientist
ras --help
```

If `ras` is missing, the install did not land on your `PATH` — check
`python -m rag_ai_scientist.ras_cli --help` instead.

## Step 0 — watch it happen first

```bash
ras demo          # animated, about a minute
ras demo --fast   # same show, instant, safe to pipe
```

The show builds a throwaway project, clears every gate and deletes itself.
Nothing you are about to do will differ from what you just saw, except the
documents. Add `--keep` and it prints the directory so you can read
`runs/<run-id>/report.md` from a run you did not have to write.

## Step 1 — scaffold a project

```bash
ras init-project --project-root ~/my-paper
```

```text
Wrote: /Users/you/my-paper/configs/harness.yaml
Corpus directory: /Users/you/my-paper/docs/references/papers
Golden set directory: /Users/you/my-paper/evals/golden
```

`configs/harness.yaml` is the whole personality of the run: retrieval
thresholds, tier thresholds, gates and the remedies the loop is allowed to
reach for. It refuses to overwrite an existing config unless you pass `--force`.

## Step 2 — feed the corpus

Drop `.pdf`, `.md` or `.txt` files into `docs/references/papers/`. Two habits
make gates pass instead of fight you:

- **One fact per file where you can.** `gates.min_terms` requires a supporting
  term to appear in at most a share of chunks, so a fact living in a single file
  is easy for the harness to pin down and hard to fake.
- **Keep numbers literal.** If the paper says `9 fb^-1`, keep that string;
  "about 9 inverse femtobarns" will not match `expect_keywords`.

## Step 3 — write the exam

Exactly one `*.json`/`*.yaml` file goes in `evals/golden/` (or point
`questions.path` at a file explicitly):

```json
{
  "name": "my-questions",
  "questions": [
    {
      "id": "Q01",
      "tier": 1,
      "question": "What integrated luminosity did the detector record?",
      "expect": "supported",
      "expect_keywords": ["9 fb", "luminosity"]
    },
    {
      "id": "Q02",
      "tier": 2,
      "question": "What mass window is used for candidates?",
      "expect": "supported",
      "expect_keywords": ["5260", "5300"]
    },
    {
      "id": "Q99",
      "tier": 1,
      "question": "What was the solenoid field strength?",
      "expect": "unresolved",
      "expect_keywords": ["tesla"]
    }
  ]
}
```

- **`tier: 1`** must resolve — every single one (`questions.tier1_min`, 1.0).
  Tiers 2 and 3 may miss up to `tier23_min` (0.8).
- **`expect: "supported"`** means the corpus answers it; the keywords must appear
  literally in the *retrieved* text, not merely be plausible.
- **`expect: "unresolved"`** is a negative control: the corpus deliberately does
  **not** contain it. If the harness finds an answer, it is hallucinating and the
  run fails. Ship at least one in every project — this is the gate that catches a
  confident lie.

## Step 4 — build the index

```bash
ras index --project-root ~/my-paper
```

Documents become chunks (`index.chunk_chars`, default 1200, with `chunk_overlap`
of 200). The run records a **chunk fingerprint**, so a later run can prove the
index did not silently drift under you. Re-run `ras index` after editing the
corpus; the harness will not guess that you changed a file.

## Step 5 — run the loop

```bash
ras run --project-root ~/my-paper
```

```text
[1/4] index          ........................................ ok
[2/4] answer         ........................................ ok
[3/4] skills         ........................................ ok
[4/4] report         ........................................ ok
ALL GATES PASSED
```

Each step is PLAN → EXECUTE → VALIDATE. Gates are the only thing allowed to
declare a step acceptable. When one fails, the loop applies a **pre-declared
remedy** from `configs/harness.yaml` — typically lowering
`retrieval.min_score` or raising `top_k` — and retries, up to
`run.max_attempts`. It cannot invent a remedy, and it cannot edit your answer to
please a gate.

Useful variants: `ras run --json` for machine-readable output, `ras run --resume`
to continue an interrupted run, `--set retrieval.top_k=8` for a one-off config
nudge (recorded in the run manifest, so the report stays honest).

## Step 6 — read the verdict

```bash
ras eval --project-root ~/my-paper
```

```text
tier1 1.0  tier23 1.0  citations_valid True  negative control unresolved
```

Then the artifact you actually forward to a collaborator:

```bash
ras report --project-root ~/my-paper    # re-renders runs/<run-id>/report.md
```

`report.md` carries the config hash, the per-document inventory with sha256s, the
plan table including the **exact commands** to reproduce each step, and the gate
results. A run you cannot re-run is an anecdote, not a result.

## Step 7 — keep what worked

A passing run generates a skill (`SKILL.md` plus one file per planned step).
`ras skills list --project-root ~/my-paper`, `ras skills show <name>`, and when
you are satisfied:

```bash
ras skills promote <name> --project-root ~/my-paper
```

`promote` is deliberately a human action: it copies a run-scoped skill into the
project so later runs and MCP/IDE clients reuse it. Resolution order is run →
project → `.cursor/skills` → packaged defaults, so a project copy always wins.

## When a gate fails

| Gate | What it is telling you | What to do |
| --- | --- | --- |
| `index_files` | corpus empty or wrong extensions | check `corpus.paths` / `corpus.extensions`, then `ras index` |
| `index_integrity`, `index_deterministic` | index changed or unreadable | stop editing files mid-run; re-index |
| `analysis_map_nonempty`, `analysis_map_shape` | questions got no status | raise `retrieval.top_k`, lower `retrieval.min_score` |
| `citations_resolve` | a claim points at text that was never retrieved | fix the corpus so the fact is findable — never hand-edit the answer |
| `claim_status_valid` | supported/unresolved is dishonest | raise `gates.min_terms`; a term in every chunk proves nothing |
| `golden_tiers` | the exam failed | add the missing fact to the corpus, or accept a real gap |

The instinct to relax a gate is almost always wrong. A failure is a statement
about your corpus and your config, and both are editable.

## Troubleshooting

- **`Refusing to overwrite existing config`** — expected; pass `--force` on
  `ras init-project`.
- **`No runs found`** — you are pointed at a different `--project-root`, or the
  run never got as far as creating a directory. `ls runs/`.
- **Everything is `supported`** — suspicious. Your `min_terms` is too low or your
  keywords are trivia; add a negative control and watch it fail.
- **Nothing resolves** — the corpus is not where the config says it is. Start
  with `ras index` and confirm the document count it prints.
- **PDFs ignored** — scanned images have no text layer; `pymupdf4llm` can only
  read real text.

## Where to go next

- `docs/harness.md` — every config key, gate and remedy in the reference.
- `get_skill("harness-tutorial")` — the same walkthrough as an agent-facing
  skill, loaded by any MCP client (it ships inside the wheel).
- `ras demo --keep` — a finished run you can dissect, with a real `report.md`.

