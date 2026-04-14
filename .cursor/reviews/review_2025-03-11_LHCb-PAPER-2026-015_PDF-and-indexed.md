# Scientific review: LHCb-PAPER-2026-015 (1st CWR)
## Angular analysis of the B⁺→π⁺μ⁺μ⁻ decay

**Paper:** B⁺→π⁺μ⁺μ⁻ (angular observables A_FB and F_H)  
**Review based on:** PDF draft (primary) + indexed RAG content (cross-check)  
**Review date:** 2025-03-11  
**Reference:** Use the exact "Find" strings below to locate each edit. **L*n*** = line or location in the PDF extract (adjust if your LaTeX/PDF numbering differs).

---

# Part 1 — High-level review

## 1. Physics review

- **Correctness:** Eq. (1) and definitions of A_FB and F_H are correct; |A_FB| ≤ F_H/2 stated. Two q² bins (1.1–6.0 and 15.0–22.0 GeV²/c⁴) avoid charmonium. Signal and background modelling (Legendre efficiency, Gaussian with tails, Chebyshev, Feldman–Cousins) is appropriate. Control channels (B⁺→J/ψπ⁺, B⁺→J/ψK⁺) and J/ψ veto are clearly described. Table 2 and results (89±13, 135±15 events; A_FB, F_H intervals) are consistent with the method.
- **Completeness:** Detector, simulation, selection, angular model, systematics (Table 1), results, and supplementary material are covered. Replace "CERN-EP-20XX-ZZZ" at submission.
- **Clarity:** Introduction and motivation are clear; Eq. (1) and Fig. 1 support the narrative. Selection and angular efficiency are logical. Results state consistency with SM at 99% CL (low q²) and 68% CL (high q²).
- **Consistency:** Charge-conjugate inclusion stated. Notation (q², θ_l, A_FB, F_H) used consistently.

## 2. Language / editorial review

- **Clarity:** Generally clear. A few hyphenation breaks in the PDF extract (e.g. "cham-" / "bers", "momentum-" / "vector") are typesetting; in LaTeX ensure correct hyphenation or use `\mbox{}` where a break is undesirable.
- **English:** Grammar fixes needed: "impact ... are estimated" → "is estimated"; "is obtained adding" → "is obtained by adding"; "Potential imperfections ... is a further source" → "are a further source". See line-by-line edits below.
- **LHCb style:** Abstract, author list note, "Submitted to JHEP", CC BY 4.0 present. Fix "Marie Skłodowska-Curie" (diacritic) and "Y. Yuan" (period after initial). Replace CERN-EP-20XX-ZZZ when available.
- **Consistency:** Notation and units consistent. UK spelling "parameterise", "normalised", "optimised" is acceptable for LHCb.

## 3. Summary and recommendations

- **Must address:** All line-by-line edits below (grammar, wording, diacritic, author initial, "by adding"). Replace CERN-EP-20XX-ZZZ at submission.
- **Suggested improvements:** Optional comma in "normalised by the total decay rate, is given by" (can remove comma for flow). Ensure no undesirable line breaks in the compiled PDF (e.g. "chambers", "momentum vector").
- **References:** LHCb Publication Procedure; Editorial Board guidelines.

---

# Part 2 — Line-by-line edit instructions (from PDF)

---

## 1. Section 1 — Introduction

### Edit 1.1 — Spacing: add space before "decay" (title) — **~L5–6**
- **Find:** `B+ →π+µ+µ−decay`
- **Replace with:** `B+ →π+µ+µ− decay`
- **Note:** In the title/abstract, add a space between the decay chain and the word "decay" where it appears without a space (e.g. "B+ →π+µ+µ−decay" → "B+ →π+µ+µ− decay"). Apply in title and anywhere the same pattern appears.

### Edit 1.2 — Spacing: add space before "is" — **~L27**
- **Find:** `The decay B+ →π+µ+µ−is, in the Standard Model`
- **Replace with:** `The decay B+ →π+µ+µ− is, in the Standard Model`
- **Note:** Missing space between decay formula and "is".

---

## 2. Section 2 — Detector and simulation

### Edit 2.1 — Hyphenation: "cham-" + "bers" → "chambers" — **~L53–54**
- **Find:** `multiwire proportional cham-`
- **Replace with:** `multiwire proportional chambers`
- **Note:** Word split across lines; join to "chambers". (If in LaTeX the line break is automatic, consider `\mbox{chambers}` or allow hyphenation only at a different point.)

### Edit 2.2 — Optional: hyphen in "momentum-vector" — **~L102–103**
- **Find:** `the B+ momentum-`
- **Replace with (if desired):** `the B+ momentum ` (then ensure next line starts with `vector`)
- **Note:** Optional; "momentum vector" (two words) is standard. If the source has "momentum-vector" as a compound, either is acceptable; if it was hyphenated only by line break, use "momentum vector".

---

## 3. Section 3 — Candidate selection

### Edit 3.1 — Spacing: "µ−and" → "µ− and" — **~L118**
- **Find:** `containing a π+, µ+, µ−and`
- **Replace with:** `containing a π+, µ+, µ− and`
- **Note:** Add space before "and".

---

## 4. Section 4 — Angular model

*No additional edits beyond high-level review.*

---

## 5. Section 5 — Systematic uncertainties

### Edit 5.1 — Grammar: subject–verb agreement — **~L187–188**
- **Find:** `The impact of various sources of systematic uncertainty are estimated using pseudoexperi-`
- **Replace with:** `The impact of various sources of systematic uncertainty is estimated using pseudoexperi-`
- **Note:** Subject is "impact" (singular), so verb must be "is estimated".

### Edit 5.2 — Add "by" after "obtained" — **~L398 / Table 1 caption**
- **Find:** `the total uncertainty is obtained adding the individual sources`
- **Replace with:** `the total uncertainty is obtained by adding the individual sources`
- **Note:** "Obtained by adding" is correct.

### Edit 5.3 — Grammar: subject–verb agreement — **~L208**
- **Find:** `Potential imperfections in the matching of true decays to reconstructed candidates in the simulation is a further source of uncertainty.`
- **Replace with:** `Potential imperfections in the matching of true decays to reconstructed candidates in the simulation are a further source of uncertainty.`
- **Note:** Subject is "Potential imperfections" (plural), so verb must be "are".

### Edit 5.4 — Optional: spacing "π+ and" — **~L223**
- **Find:** `B+ →π+π−π+and B0`
- **Replace with:** `B+ →π+π−π+ and B0`
- **Note:** Add space before "and" if missing in source.

---

## 6. Section 6 — Results

*No additional edits.*

---

## 7. Section 7 — Summary

*No additional edits.*

---

## 8. Supplementary material

### Edit 8.1 — Comma / wording: "B+ →J/ψK+, signal" — **~L302**
- **Find:** `populates the region to the right of the B+ →J/ψK+, signal is small`
- **Replace with:** `populates the region to the right of the B+ →J/ψK+ signal is small`
- **Note:** Remove comma before "signal" so it reads "to the right of the B+ →J/ψK+ signal". (Or rephrase to "to the right of the B+ →J/ψK+ peak; this contribution is small and is neglected" if the sentence structure in the source differs.)

### Edit 8.2 — Optional: comma in "normalised by the total decay rate, is given by" — **~L317**
- **Find:** `the angular distribution normalised by the total decay rate, is given by`
- **Replace with (optional):** `the angular distribution normalised by the total decay rate is given by`
- **Note:** Removing the comma avoids a slight pause; both are grammatically acceptable.

---

## 9. Acknowledgements

### Edit 9.1 — Diacritic: "Sk lodowska" → "Skłodowska" — **~L288**
- **Find:** `Marie Sk lodowska-Curie Actions`
- **Replace with:** `Marie Skłodowska-Curie Actions`
- **Note:** Use Unicode ł (U+0142) or LaTeX `\l{}` in "Skłodowska". Fix the space or wrong character that appears as "Sk lodowska" in the PDF.

---

## 10. Author list

### Edit 10.1 — Initial with period — **Author list**
- **Find:** `Y Yuan`
- **Replace with:** `Y. Yuan`
- **Note:** Use a period after the initial "Y" for consistency with other authors (e.g. "Y. Song", "Y. Wang").

---

## 11. Science comments (methodology, physics, interpretation)

*Separate from the language/typo edits above.*

### Strengths

- **Angular framework:** Eq. (1) and A_FB, F_H correctly implemented. Feldman–Cousins appropriate for small samples and |A_FB| ≤ F_H/2.
- **Efficiency and veto:** Fourth-order Legendre (even terms), J/ψ veto model, control channels (B⁺→J/ψπ⁺, B⁺→J/ψK⁺) validate the strategy.
- **Background model:** Misidentified B⁺→K⁺μ⁺μ⁻, combinatorial, and hadronic contributions clearly described. Table 1 summarises systematics.
- **Results:** 68% and 99% CL and comparison to SM in both q² bins are clear. Signal yields and Table 2/Figs. 6–7 consistent with the text.
- **Stability:** BDT, PID, and alternative fit (|cos θ_l|) mentioned; B⁺→K⁺μ⁺μ⁻ cross-check shows no significant asymmetry.

### Suggestions (optional)

- **Tail parameters:** Brief mention of any sensitivity study (e.g. floating one tail) would strengthen systematics.
- **Table 3 vs main text:** If the difference between Table 3 yields and main-text yields is due to bootstrap vs likelihood, a short clarification would help.
- **High q² covariance:** The note on the covariance matrix not being positive definite is helpful; one sentence on how Feldman–Cousins intervals incorporate this could be added.

### Accuracy check

- Eq. (1) and boundary correct. References [8,9], [39], PDG [36] appropriate. Tables 1 and 2 consistent with the procedure.

---

## Summary table (quick reference)

| Location | § | Find (key phrase) | Change |
|----------|---|-------------------|--------|
| **~L5–6** | 1 | B+ →π+µ+µ−decay | B+ →π+µ+µ− **space** decay |
| **~L27** | 1 | B+ →π+µ+µ−is, in the | B+ →π+µ+µ− **space** is, in the |
| **~L53–54** | 2 | multiwire proportional cham- | **chambers** (single word) |
| **~L102** | 2 | B+ momentum- | (optional) momentum **space** vector |
| **~L118** | 3 | µ−and | µ− **space** and |
| **~L187** | 5 | impact ... uncertainty are estimated | **is** estimated |
| **Table 1** | 5 | is obtained adding the | is obtained **by** adding the |
| **~L208** | 5 | imperfections ... simulation is a further | **are** a further |
| **~L223** | 5 | π+π−π+and B0 | π+π−π+ **space** and B0 |
| **~L302** | Supp. | J/ψK+, signal is small | J/ψK+ signal is small (remove comma) |
| **~L317** | Supp. | rate, is given by | (optional) rate is given by |
| **~L288** | Ack. | Marie Sk lodowska | Marie **Skłodowska** |
| **Author list** | 10 | Y Yuan | **Y.** Yuan |

---

*End of review. Based on PDF draft and cross-check with indexed content. Saved to: `.cursor/reviews/review_2025-03-11_LHCb-PAPER-2026-015_PDF-and-indexed.md`*
