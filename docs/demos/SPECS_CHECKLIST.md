# Specs Execution Checklist (Dev)

Use this checklist for every agent task derived from `docs/AGENT_SPECSLIST_DEV.md`.

## 0) Task Header

- [ ] `run_id` assigned
- [ ] date/time recorded (UTC)
- [ ] owner agent + reviewer identified
- [ ] target branch is `dev`
- [ ] task scope and non-goals written in 3-6 lines

## 1) Inputs and Evidence

- [ ] references/datasets listed with versions or immutable IDs
- [ ] licenses/usage constraints verified
- [ ] expected outputs defined before execution
- [ ] evaluation metrics and pass/fail thresholds set

## 2) Security Preconditions

- [ ] confirm no secrets in task payload (tokens, keys, cookies, kerberos/session data)
- [ ] ingestion allowlist applied (only approved files/sources)
- [ ] external network usage decision recorded (default: disabled)
- [ ] prompt-injection risk noted for retrieved untrusted content

## 3) Execution Setup

- [ ] environment fingerprint captured (python, packages, platform)
- [ ] deterministic config snapshot saved
- [ ] random seeds fixed and recorded
- [ ] command wrapper/script selected (no ad-hoc unsafe commands)

## 4) Run and Capture

- [ ] full command log captured
- [ ] stdout/stderr artifacts archived
- [ ] run outputs saved under a unique run folder
- [ ] provenance links captured (input -> code/config -> output)

## 5) Validation Gates

- [ ] baseline comparison executed
- [ ] metric deltas reported against thresholds
- [ ] uncertainty/stability checks passed
- [ ] failure modes documented if any gate fails

## 6) HEP-Specific Checks (when applicable)

- [ ] preselection and trigger-line consistency confirmed
- [ ] MC/data correction versions pinned and logged
- [ ] fit stability checked (convergence, pulls, uncertainty sanity)
- [ ] final physics formulae and uncertainty propagation documented

## 7) Security Post-Checks

- [ ] artifact redaction pass completed
- [ ] logs/transcripts scanned for sensitive leakage
- [ ] publication/export policy check passed
- [ ] any blocked output recorded with reason

## 8) Deliverables

- [ ] `summary.md` created
- [ ] `metrics.json` created
- [ ] artifact index produced (`artifacts/`)
- [ ] limitations/risks section included

## 9) Review and Sign-Off

- [ ] independent reviewer assigned
- [ ] reproducibility replay attempted (same manifest)
- [ ] replay consistency result recorded
- [ ] final status: `pass` / `conditional` / `fail`

## 10) Demo Profile (pick one)

- [ ] AutoResearch-style literature map
- [ ] Higgs Open Dataset baseline
- [ ] Mini-AlphaFold toy workflow
- [ ] LHC tracking benchmark
- [ ] other approved demo (name: ____________________)

## 11) Quick Failure Taxonomy

- [ ] data issue
- [ ] config drift
- [ ] environment mismatch
- [ ] model instability
- [ ] security policy violation
- [ ] other: ____________________

## 12) Minimal Completion Record

Fill this section at task close:

- `run_id`:
- branch:
- commit(s):
- scenario:
- outcome:
- key metrics:
- reproducibility replay:
- security findings:
- reviewer:
- follow-up actions:
