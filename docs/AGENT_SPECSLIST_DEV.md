# Agent Specslist Plan (Dev Branch)

This document defines a practical, implementation-oriented specslist for agents that continue developing `rag-ai-scientist` in the `dev` branch.

## Scope and Branch Policy

- This plan applies only to `dev` unless explicitly promoted to release branches.
- Agents must refuse direct edits on `main` for features described here.
- Every feature task must include:
  - reproducible test evidence,
  - security checks for secret leakage,
  - a short model-card style note for limitations and risks.

## Product Objectives

- Build a reliable autonomous research assistant for scientific software and analyses.
- Support reproducible workflows from data/reference ingestion to report generation.
- Provide domain templates with explicit evaluation metrics (not only generic demos).
- Keep all private credentials, sessions, and filesystem secrets out of agent outputs.

## Agent Roles and Responsibilities

### 1) Orchestrator Agent

- Decomposes user goal into ordered, auditable subtasks.
- Assigns tasks to specialized agents (retrieval, coding, validation, reporting).
- Enforces branch policy, run IDs, and artifact traceability.

### 2) Retrieval-and-Evidence Agent

- Queries local RAG index and external open datasets/papers when allowed.
- Returns citation-grounded context with confidence scores.
- Flags weak evidence and requests human confirmation before high-impact actions.

### 3) Execution Agent

- Runs code modifications and analysis commands inside approved environments only.
- Uses deterministic wrappers (`scripts/*.sh`) instead of ad-hoc shell commands.
- Stores command, environment fingerprint, and outputs per run.

### 4) Validation Agent

- Executes tests, statistical checks, and physics-specific sanity constraints.
- Compares new outputs against baselines and reports deltas with thresholds.
- Blocks completion when uncertainty, fit instability, or data-quality alarms appear.

### 5) Security and Compliance Agent

- Scans prompts, logs, artifacts, and generated markdown for sensitive material.
- Enforces denylist/redaction rules for Kerberos, tokens, keys, and host metadata.
- Prevents upload/publication of artifacts that fail policy checks.

## Milestones and Deliverables

### Milestone A: Reliable Core Loop

- Task graph + retry policy + bounded autonomy (timeouts, max retries, approval gates).
- Structured run ledger: `run_id`, inputs, outputs, model/tool versions, hashes.
- Standardized report bundle (`summary.md`, `metrics.json`, `artifacts/`).

### Milestone B: Security Hardening

- Secret scrubber middleware in all agent I/O channels.
- Policy checks before saving transcripts or publishing validation pages.
- Explicit threat model and failure-mode tests (prompt injection, exfiltration attempts).

### Milestone C: Reproducibility-First Workflows

- One-command replay from stored run metadata.
- Deterministic configs and immutable references for benchmark runs.
- Provenance graph linking references -> code change -> output figures/tables.

### Milestone D: Domain Demo Packs

- Reusable curated demo tasks with pass/fail rubrics and expected artifacts.
- Lightweight datasets and scripts so contributors can run end-to-end locally.
- Comparison dashboards for baseline vs current agent behavior.

## Demo Examples to Implement

### Open-source and Papers-with-Code style demos

1. **AutoResearch-style literature agent (Andrej Karpathy inspiration)**
   - Goal: generate a concise literature map and implementation shortlist for a topic.
   - Inputs: arXiv metadata + selected repos.
   - Output: ranked candidates with reproducibility score and setup friction estimate.

2. **Higgs Open Dataset classification baseline**
   - Goal: reproduce a baseline signal-vs-background model with transparent preprocessing.
   - Metrics: ROC AUC, calibration, training stability across seeds.
   - Deliverables: notebook/script, config snapshot, reproducibility report.
   - RAG story + pip workflow: `docs/examples/cms_higgs_opendata_physics_story.md`; packaged skill **`cms-higgs-opendata`**.

3. **Mini-AlphaFold workflow demo**
   - Goal: run a simplified structure-prediction style pipeline (toy-scale).
   - Focus: dependency management, deterministic feature generation, benchmark replay.
   - Deliverables: run manifest, timing breakdown, quality metrics.

4. **LHC tracking problem benchmark**
   - Goal: demonstrate agent-assisted experimentation for track reconstruction models.
   - Metrics: efficiency, fake rate, duplicate rate, runtime budget.
   - Deliverables: standardized evaluation script and result comparison table.

5. **Additional recommended demos**
   - Time-series anomaly detection in detector-control style telemetry.
   - Fast simulation surrogate-model benchmark with uncertainty reporting.
   - Trigger-rate forecasting with drift monitoring and retraining policy.

## Security Specifications (Must-Have)

### Data and Credential Safety

- Never expose:
  - Kerberos ticket paths or cache contents (`KRB5CCNAME`, `klist` outputs),
  - SSH keys, tokens, API keys, passwords, cookie/session material,
  - private filesystem topology beyond minimal required context.
- Apply redaction before logs are persisted or displayed.
- Use strict allowlist for files eligible for RAG ingestion and publication.

### Runtime Isolation

- Run untrusted parsing and external-content processing in constrained environments.
- Disable arbitrary outbound network calls by default; require opt-in policy.
- Enforce per-tool permission scopes and auditable reason strings for escalations.

### Prompt-Injection and Exfiltration Defenses

- Treat retrieved text as untrusted; never execute embedded instructions blindly.
- Separate "content channel" from "policy/control channel" in agent prompts.
- Add regression tests with known injection payloads to verify refusal behavior.

### Security Testing Requirements

- Add CI checks for secret scanning and unsafe serialization patterns.
- Include red-team fixtures:
  - malicious markdown,
  - poisoned repository docs,
  - fake "debug" requests asking for credentials.

## HEP Reproducibility Specifications

### Reproducible Analysis Contract

- Each run must store:
  - dataset identifiers and selection versions,
  - code revision + diff summary,
  - full configuration and random seeds,
  - environment snapshot (Python, key packages, platform).
- Re-running with same manifest must produce statistically consistent outputs.

### Physics-Specific Validation Gates

- Preselection and trigger-line consistency checks.
- Mass-fit stability checks (fit convergence, parameter pulls, uncertainty sanity).
- Efficiency pipeline checks (MC/data correction provenance and version pinning).
- Branching-ratio report must include explicit formula, propagated uncertainties, and inputs.

### Example HEP Tasks for Agent Regression Suite

1. Reproduce a toy BR pipeline from preselection to final yield table.
2. Validate MC correction impact against stored reference curves.
3. Detect and explain a deliberate config drift in selection cuts.
4. Regenerate final plots/tables from manifest without manual intervention.

## Engineering Backlog (Prioritized)

1. Implement centralized provenance ledger and artifact schema.
2. Add security middleware for redaction + policy enforcement.
3. Add benchmark harness for open-source and HEP demo packs.
4. Add replay command (`rag-ai-scientist replay --run-id ...`).
5. Add compliance report generator (security + reproducibility checklist).

## Acceptance Criteria for "Ready in Dev"

- All milestone-A features merged and smoke-tested.
- At least 3 demo packs runnable end-to-end (including 1 HEP case).
- Secret leakage tests pass on prompts/logs/artifacts.
- Reproducibility replay succeeds on stored manifests.
- Documentation includes contributor instructions for adding new demo packs.

## Suggested File/Folder Additions

- `docs/demos/` for scenario definitions and expected outputs.
- `validation/benchmarks/` for scoring scripts and reference metrics.
- `workflow/security/` for redaction/policy utilities.
- `workflow/reproducibility/` for manifests, replayers, and provenance graph logic.

## Notes for Contributors

- Keep demo dependencies lightweight and openly accessible when possible.
- Prefer deterministic toy datasets when licensing/distribution is restricted.
- When using external content, include citation metadata and license notes.
