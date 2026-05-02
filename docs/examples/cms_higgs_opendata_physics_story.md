# CMS Higgs discovery (~125 GeV) — physics story and open-data replication

This note is meant to be **indexed into your vector database** so agents can answer questions about the analysis narrative, datasets, and limitations of educational reproductions. It is **not** an official CMS document.

## After `pip install rag-ai-scientist`

The **`cms-higgs-opendata`** skill ships inside the wheel (`rag_ai_scientist/skills/`). Agents can load it anytime via MCP tool **`get_skill`** with `skill: "cms-higgs-opendata"` — **no indexing required** for that checklist.

**Semantic retrieval** (`query_analysis_knowledge`) only sees files you have **indexed** for the chosen `--project-root`. To retrieve this note:

1. Point `configs/references.yaml` at a path that contains this file (or copy this markdown into your references directory).
2. From the package source tree, `configs/references.example.yaml` already includes `../docs`, so `docs/examples/*.md` is indexed when you run indexing from that repo layout.
3. Run:

   ```bash
   rag-ai-scientist setup-rag --project-root /path/to/project --force
   ```

4. Start MCP with the **same** project root:

   ```bash
   rag-ai-scientist mcp --project-root /path/to/project
   ```

If you only installed from PyPI and have **no** checkout of this documentation, copy this file (or a shortened derivative) into the directory you passed to **`init-references --references-dir`**, then rerun **`setup-rag`**.

## Publication anchor

The observation of a new boson consistent with the Standard Model Higgs at **mass near 125 GeV** was reported by CMS using **pp collisions at 7 and 8 TeV** (Run 1). A canonical public summary of the paper line is the CMS results page for **CMS-HIG-12-028** (“Observation of a new boson…”). See the experiment publication list and arXiv entry linked from [CMS results](https://cms-results.web.cern.ch/cms-results/public-results/publications/HIG-12-028/).

## Physics story (what we replicate in spirit)

1. **Motivation** — In the SM, electroweak symmetry breaking can be implemented with a scalar doublet; the physical **Higgs boson** couples to mass (fermion Yukawas, gauge-boson strengths). Production at the LHC is dominated by **gluon fusion** and **vector boson fusion** (channel-dependent), with important associated production modes.

2. **Signature channels used for discovery-level messaging** — CMS combined several decay modes. The clearest “mass bump” stories for pedagogy are:
   - **\(H \to \gamma\gamma\)** — narrow resonance on a smoothly falling diphoton background; excellent mass resolution.
   - **\(H \to ZZ \to 4\ell\)** (\(\ell = e,\mu\)) — very clean four-lepton invariant mass; low rate but high purity.

3. **Statistical idea** — Parameter of interest is typically signal strength **\(\mu\)** relative to the SM prediction (\(\mu=1\)). Searches use **binned likelihoods** (Poisson counts per bin) with **signal and background models**; discovery-style statements come from **significance** against background-only.

4. **What “125 GeV” refers to** — Combined measurements indicated compatibility with a mass **near 125 GeV** (specific quoted values and uncertainties appear in the publication tables).

## What CMS open data provides

CMS **released Run 1 open data** including material suited for **rediscovery-style exercises** (simplified skims, examples, and guides). These resources **do not** automatically reproduce every table in CMS-HIG-12-028 bit-for-bit; they reproduce the **same physics storyline**: selections → invariant mass spectra → discussion of background vs excess.

Authoritative portals and guides:

- [CERN Open Data Portal](https://opendata.cern.ch/) — dataset records, metadata, citations.
- [CMS Open Data Guide](https://cms-opendata-guide.web.cern.ch/) — workflows, tools (ROOT, CMSSW containers/VMs), object basics.
- [CMS guide for education](https://opendata.cern.ch/docs/cms-guide-for-education) — learning paths.

## Hands-on replication stack (recommended starting points)

1. **GitHub tutorial repository** — [cms-opendata-analyses/HiggsExample20112012](https://github.com/cms-opendata-analyses/HiggsExample20112012) walks through reproducing a **four-lepton style** Higgs discovery narrative using **2011–2012** open data, with **multiple difficulty levels** (from histogram exercises toward fuller analyses). Treat this as the default **code companion** for the same physics story.

2. **Local analysis environment** — Depending on path:
   - **Notebook-first / Python** — Use reduced CSV-like outputs or ROOT via `uproot` where examples provide them; follow portal notebook links (Binder) where available.
   - **Full CMSSW path** — Follow CMS Open Data Guide for container/VM and release compatibility for the **specific dataset record** you choose.

3. **Agent workflow with this package** — Use **`get_skill`** / skill name **`cms-higgs-opendata`** for the operational checklist (datasets → environment → invariant mass → honest comparison to the paper). Use **`query_analysis_knowledge`** for methodology questions **after** this note (or your own notes) are indexed.

## Citations users should include

- **CMS open data** record citation — use the **DOI** from each dataset page on the CERN Open Data Portal when you publish plots or teaching materials.
- **Original discovery paper** — cite CMS-HIG-12-028 / the corresponding journal article when comparing qualitative features to the published observation.

## Explicit limitations (avoid over-claiming)

- Open-data skims and tutorials use **simplified** detector emulation, smaller statistics, or **pre-selected** candidate collections compared to the internal 2012 analysis.
- Systematic uncertainties (energy scale, resolution tails, efficiency correlations) are **reduced** in teaching pipelines.
- Any statement like “we reproduced CMS’s significance” should be replaced by “we **illustrate** the same discovery channel idea with public data.”

## Glossary (quick)

| Term | Meaning |
|------|---------|
| **Invariant mass** | Lorentz-invariant mass computed from final-state four-momenta; peaks at parent resonance if resolution permits. |
| **Signal strength \(\mu\)** | Ratio of observed coupling scale to SM expectation in simplified fits (\(\mu=1\) is SM). |
| **Sideband** | Mass regions away from the hypothesised signal, used to constrain background shape/normalisation. |
