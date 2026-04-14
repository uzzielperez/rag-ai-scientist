# Scientific review: LHCb-PAPER-2026-015 — Angular analysis of the B⁺→π⁺μ⁺μ⁻ decay

**Paper:** B⁺→π⁺μ⁺μ⁻ (angular observables A_FB and F_H)  
**Review based on:** Indexed RAG content (vector DB)  
**Review date:** 2025-03-11  
**References:** [LHCb Publication Procedure](https://lhcb.web.cern.ch/lhcb_page/collaboration/organization/editorial_board/PublicationProcedureNovember2011.pdf), [Editorial Board](https://lhcb.web.cern.ch/lhcb_page/collaboration/organization/editorial_board/default.html)

---

# Part 1 — High-level review

## 1. Physics review

- **Correctness:** Eq. (1) and the definitions of A_FB and F_H are correct; |A_FB| ≤ F_H/2 is stated. Two q² bins (1.1–6.0 and 15.0–22.0 GeV²/c⁴) avoid charmonium. Signal and background modelling (Legendre efficiency, Gaussian with tails, Chebyshev, Feldman–Cousins) is appropriate. Control channels (B⁺→J/ψπ⁺, B⁺→J/ψK⁺) and J/ψ veto are clearly described. Table 2 and results (89±13, 135±15 events; A_FB, F_H intervals) are consistent with the described method.
- **Completeness:** Detector, simulation, selection, angular model, systematics (Table 1), and results are covered. Supplementary material (efficiency, B⁺→J/ψK⁺ fit, Table 3, confidence intervals) is referenced. Placeholder "CERN-EP-20XX-ZZZ" should be updated at submission.
- **Clarity:** Introduction and motivation are clear; Eq. (1) and Fig. 1 support the narrative. Selection and angular efficiency (fourth-order Legendre, J/ψ veto) are logical. Results section states consistency with SM at 99% CL (low q²) and 68% CL (high q²).
- **Consistency:** Charge-conjugate inclusion stated. Notation (q², θ_l, A_FB, F_H) used consistently. References to SM predictions and B⁺→K⁺μ⁺μ⁻ [16] are appropriate.

## 2. Language / editorial review

- **Clarity:** Sentence structure is generally clear. Some section headings in the indexed export show duplicated numbers (e.g. "### 1 1 Introduction"); in the LaTeX source, ensure a single section number (e.g. "1 Introduction").
- **English:** One grammar issue in Section 5 (Systematic uncertainties): "The impact of various sources of systematic uncertainty are estimated" — subject is "impact" (singular), so verb should be "is estimated". See line-by-line Edit 5.1 below.
- **LHCb style:** Abstract, author list note, "Submitted to JHEP", and CC BY 4.0 are present. Replace "CERN-EP-20XX-ZZZ" with the actual preprint number when available. Acknowledgements: fix diacritic in "Marie Skłodowska-Curie" (see Edit 8.1). Author list: use period after initial "Y" in "Y. Yuan" (Edit 9.1).
- **Consistency:** Notation cos θ_l and units (GeV²/c⁴, MeV/c²) are consistent. "Normalised" (UK spelling) is acceptable for LHCb.

## 3. Summary and recommendations

- **Must address:** (1) Grammar: "impact ... are estimated" → "is estimated". (2) Replace CERN-EP-20XX-ZZZ with preprint number at submission. (3) Acknowledgements: correct "Marie Skłodowska-Curie". (4) Author list: "Y. Yuan" with period after initial.
- **Suggested improvements:** (1) In LaTeX source, ensure section headings do not produce duplicated numbers (e.g. "1 1 Introduction") in compiled output. (2) Optional: add a short sentence in Results reiterating the two q² bin ranges for readers who skim.
- **References:** LHCb Publication Procedure; Editorial Board guidelines for writing papers.

---

# Part 2 — Line-by-line edit instructions

**Reference:** Use the exact "Find" strings below to locate each edit. **L*n*** = approximate line or location in the draft (adjust if your LaTeX/PDF numbering differs).

---

## 1. Section 1 — Introduction

*No mandatory language edits identified in the introduction from the indexed text. If the compiled PDF shows a duplicated section number (e.g. "1 1 Introduction"), fix in LaTeX so the section title is "1 Introduction" only.*

---

## 2. Section 2 — Detector and simulation

### Edit 2.1 — Word break: "cham" + "bers" — **~L54–55**
- **Find:** `multiwire proportional cham`
- **Replace with:** `multiwire proportional chambers`
- **Note:** If the source has a line break or hyphenation that splits "chambers" across two lines, join to a single word "chambers". (If already correct in LaTeX, ignore.)

---

## 3. Section 3 — Candidate selection

*No additional line-by-line edits beyond the high-level review.*

---

## 4. Section 4 — Angular model

*No additional line-by-line edits.*

---

## 5. Section 5 — Systematic uncertainties

### Edit 5.1 — Grammar: subject–verb agreement — **~L188**
- **Find:** `The impact of various sources of systematic uncertainty are estimated using pseudoexperiments`
- **Replace with:** `The impact of various sources of systematic uncertainty is estimated using pseudoexperiments`
- **Note:** Subject is "impact" (singular), so verb must be "is estimated".

---

## 6. Section 6 — Results

*No additional line-by-line edits.*

---

## 7. Section 7 — Summary

*No additional line-by-line edits.*

---

## 8. Acknowledgements

### Edit 8.1 — Diacritic in name — **Acknowledgements**
- **Find:** `Marie Sklodowska-Curie Actions` (or `Marie Sk lodowska-Curie Actions` if the ł is missing)
- **Replace with:** `Marie Skłodowska-Curie Actions`
- **Note:** Use Unicode ł (U+0142) or LaTeX `\l{}` in "Skłodowska".

---

## 9. Author list

### Edit 9.1 — Initial with period — **Author list**
- **Find:** `Y Yuan` (in the author list)
- **Replace with:** `Y. Yuan`
- **Note:** Use a period after the initial "Y" for consistency with other authors.

---

## 10. Science comments (methodology, physics, interpretation)

*These are reviewer comments on the analysis and presentation of the physics. They are separate from the language/typo edits above.*

### Strengths

- **Angular framework:** Eq. (1) and the use of A_FB and F_H are standard and correctly implemented. Feldman–Cousins is appropriate for small samples and the physical boundary |A_FB| ≤ F_H/2.
- **Efficiency and veto:** Fourth-order Legendre (even terms only) and the discontinuous function for the J/ψ veto are well motivated. Control channels (B⁺→J/ψπ⁺, B⁺→J/ψK⁺) validate the strategy.
- **Background model:** Misidentified B⁺→K⁺μ⁺μ⁻ (Chebyshev, no odd terms), combinatorial (exponential + Chebyshev), and hadronic contributions are clearly described. Table 1 summarises systematics; total uncertainties are combined in quadrature.
- **Results:** Quoting 68% and 99% CL and the comparison to SM in both q² bins is clear. Signal yields (89±13, 135±15) and Table 2/Fig. 6–7 are consistent with the text.
- **Stability and cross-checks:** BDT working point, PID, and alternative fit (|cos θ_l|) are mentioned; B⁺→K⁺μ⁺μ⁺ with same selection shows no significant asymmetry.

### Suggestions (optional)

- **Tail parameters (Section 4):** The paper states tail parameters are fixed from simulation. A brief mention of any sensitivity (e.g. floating one tail in a variant) would strengthen systematics.
- **Table 3 vs main text yields:** Table 3 gives 90±15 and 134±30 for signal; main text gives 89±13 and 135±15. If these differ due to bootstrap vs likelihood, a short clarification (e.g. "statistical uncertainties from bootstrap" in main text vs "from likelihood" in table caption) would avoid confusion.
- **High q² covariance:** The note that for the high-q² interval "the covariance matrix is not positive definite and therefore the uncertainties should be interpreted with caution" is helpful; consider adding one sentence on how the Feldman–Cousins intervals incorporate this.

### Accuracy check

- Eq. (1) and the boundary |A_FB| ≤ F_H/2 are correct. References to Refs. [8,9], [39] (Feldman–Cousins), and PDG [36] are appropriate. Table 1 and Table 2 are consistent with the described procedure.

---

## Summary table (quick reference)

| Location | § | Find (key phrase) | Change |
|----------|---|-------------------|--------|
| **~L54** | 2 | multiwire proportional cham | **chambers** (single word) |
| **~L188** | 5 | impact ... uncertainty are estimated | **is** estimated |
| **Acknowledgements** | 8 | Marie Sklodowska / Sk lodowska | Marie **Skłodowska** |
| **Author list** | 9 | Y Yuan | **Y.** Yuan |

---

*End of review. Review file saved to: `.cursor/reviews/review_2025-03-11_LHCb-PAPER-2026-015_angular-analysis-B+pi+mu+mu-.md`*
