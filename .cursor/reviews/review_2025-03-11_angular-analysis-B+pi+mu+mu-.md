# Review: Angular analysis of the B⁺→π⁺μ⁺μ⁻ decay (LHCb-PAPER-2026-015)

**Document:** LHCb-PAPER-2026-015-1CWR.pdf  
**Review based on:** Indexed RAG content (vector DB chunks)  
**Review date:** 2025-03-11  
**References:** [LHCb Publication Procedure](https://lhcb.web.cern.ch/lhcb_page/collaboration/organization/editorial_board/PublicationProcedureNovember2011.pdf), [Editorial Board](https://lhcb.web.cern.ch/lhcb_page/collaboration/organization/editorial_board/default.html)

---

## Clear title for the paper

**Recommended title:**  
**Angular analysis of the B⁺→π⁺μ⁺μ⁻ decay**

*(Subtitle or running head can note “first measurement of A_FB and F_H” if desired; the current #-style title in the draft is already clear and suitable for JHEP.)*

---

## 1. Physics review

- **Correctness**
  - The differential decay rate (Eq. 1) and the definitions of A_FB and F_H are stated correctly and in line with Refs. [8,9]. The constraint |A_FB| ≤ F_H/2 for positive-definite angular distribution is mentioned.
  - Two q² regions (1.1–6.0 and 15.0–22.0 GeV²/c⁴) avoid the charmonium peaks; motivation is clear.
  - Signal and background modelling (Legendre polynomial efficiency, Gaussian with tails for mass, Chebyshev for combinatorial and misidentified B⁺→K⁺μ⁺μ⁻) is appropriate. Use of Feldman–Cousins for confidence intervals is justified given small samples and the physical boundary.
  - Control channels (B⁺→J/ψπ⁺, B⁺→J/ψK⁺) and validation of the strategy are described. J/ψ veto and B⁺→K⁺μ⁺μ⁻ mis-ID as main background are clearly explained.

- **Completeness**
  - Detector, simulation, selection, and angular model are covered. The abstract states that results are consistent with SM predictions; the indexed chunks do not show the numerical results tables or central values. For a full review, the draft should be checked to ensure: quoted values and uncertainties for A_FB and F_H in each q² bin, systematic uncertainty breakdown, and comparison to SM (and references to theory predictions).
  - Minor: “CERN-EP-20XX-ZZZ” and “February 26, 2026” in the header should be finalised at submission (journal and preprint info).

- **Clarity**
  - Introduction motivates the decay and the first angular measurement well; connection to B⁺→K⁺μ⁺μ⁻ and tensor limits is clear. Figure 1 (Feynman diagrams) and Eq. (1) support the narrative.
  - Selection (trigger, BDT, PID, vetoes) and angular efficiency (fourth-order Legendre, even terms only; J/ψ veto modelled) are described in a logical order. A brief recap in the results section of the two q² bins would help the reader.

- **Consistency**
  - Charge-conjugate inclusion is stated. Notation (q², θ_l, A_FB, F_H) is used consistently. References to Refs. [5–7] (SM), [10] (tensor), [39] (Feldman–Cousins), etc. are appropriate. No conflict with “preliminary” vs “final” in the indexed text; if this is a CONF, figures/results should be marked preliminary per Publication Procedure.

---

## 2. Language / editorial review

- **Clarity of presentation**
  - Sentence structure is generally clear. Some long sentences (e.g. detector description, BDT training) could be split for readability. Section numbering in the indexed extract (e.g. “### 1 1 Introduction”) appears to mix heading level and paragraph numbers; ensure final draft has consistent heading hierarchy (e.g. “1 Introduction”, “2 Detector and simulation”) per LHCb style.

- **Correct use of English**
  - Minor: “for decays originating from” → “for candidates originating from” (or similar) where referring to combinatorial background. “The probability density of the angular distribution to remain” → “for the probability density … to remain” (grammar). Otherwise the English is of good standard.

- **LHCb style**
  - Author list and affiliations are at the end; “Authors are listed at the end of this paper” in the abstract is correct. CERN preprint number and “Submitted to JHEP” and CC BY 4.0 are present. Ensure journal name and submission status are updated at submission. Check that figure captions (e.g. Figure 1, Figure 2) match the EB template (caption style, “Figure” vs “figure” in text).
  - Reference formatting (e.g. [1,2], [5–7]) is consistent; verify against the template for journal submission.

- **Consistency**
  - Notation: B⁺, π⁺, μ⁺, μ⁻, q², θ_l, A_FB, F_H used consistently. “cos θl” vs “cos θ_l”: choose one (prefer subscript l for lepton). Ensure “GeV²/c⁴” and “MeV/c²” are used consistently for q² and masses.

---

## 3. Summary and recommendations

- **Must address**
  - Confirm that numerical results (A_FB, F_H and uncertainties in both q² bins), systematic breakdown, and comparison to SM are present and clearly stated in the full draft.
  - Replace placeholder “CERN-EP-20XX-ZZZ” with the correct preprint number when available.
  - Resolve any duplicate or inconsistent section/paragraph numbering in the source (e.g. “### 1 1 Introduction”) so headings follow the LHCb paper template.
  - If this is a conference report, ensure all figures and results are explicitly marked as preliminary per Publication Procedure.

- **Suggested improvements**
  - Add a short sentence in the results section reiterating the two q² bins (ranges and motivation) for readers who skim.
  - Consider one sentence in the abstract on the dataset (9 fb⁻¹, 2011–2018) and the two q² regions if not already there.
  - Unify notation for cos θ_l (subscript l) and check hyphenation (e.g. “forward-backward” vs “forward–backward” as in “Feynman”) if the EB template specifies.

- **References**
  - LHCb Publication Procedure (November 2011): referee role, editorial quality, preliminary vs final.
  - LHCb Editorial Board: [Guidelines for preparing LHCb documents](https://lhcb.web.cern.ch/lhcb_page/collaboration/organization/editorial_board/default.html), template for writing papers.
