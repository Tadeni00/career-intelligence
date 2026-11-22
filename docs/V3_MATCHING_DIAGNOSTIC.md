# V3 — Matching Engine Diagnostic Report

Benchmark: `docs/benchmark/matching_benchmark_v3.json` (26 cases: 3 frozen
regression cases with pre-existing human labels, 23 real postings collected from
public job boards). Candidate profile unchanged since V1.

---

## 1. Headline finding

The engine is **internally sound and fully explainable**, and the Monzo
disagreement is **not** a threshold problem. It is a structural conflation of
*suitability* with *application action*, combined with a requirement-extraction
layer that is not reproducible.

No calibration change is proposed. The evidence does not yet support one.

## 2. Baseline (Gate A)

| Job | Human | System | Score | Blocker | Result |
|---|---|---|---:|---:|---|
| VJ-01 Monzo | MAYBE | SKIP | 80.5 | 1 | Disagreement (near) |
| VJ-02 Affirm | NO | SKIP | 49.5 | 1 | Agreement |
| VJ-03 SEAhub | YES | APPLY_WITH_TAILORING | 74.9 | 0 | Agreement |

- Exact agreement **2/3 (67%)**
- False skips **0**
- False applies **0**
- Severe (YES↔NO) disagreements **0**
- Near (MAYBE↔) disagreements **1**

All 26 cases reproduce exactly from frozen inputs; all 26 audits verify.

**n = 3 is not a calibration dataset.** No threshold, weight or policy change can
be justified from this.

## 3. Monzo root cause (spec §12)

Question asked: why is a job scoring 80.5 returned as SKIP?

Decomposition:

| Dimension | Score | Weight | Contribution |
|---|---:|---:|---:|
| Technical | 100.0 | 0.40 | 40.00 |
| Experience | 84.0 | 0.25 | 21.00 |
| Education | 70.0 | 0.10 | 7.00 |
| Location | **20.0** | 0.10 | 2.00 |
| Other | 70.0 | 0.15 | 10.50 |
| **Total** | | | **80.50** |

80.50 is inside the `APPLY` band. The recommendation is nevertheless `SKIP`
because `RecommendationPolicy.decide` returns `SKIP` whenever *any* blocker is
present, regardless of score.

The blocker is `LOCATION / REQUIRED / "UK location"`, raised by
`_is_hard_location_block` because the requirement text contains a mandatory
marker, while the candidate is in Lagos and the role is
`Cardiff, London or Remote (UK)`.

**Root-cause classification: decision policy interacting with blocker semantics
(H7 + H6), not scoring and not thresholds.**

Supporting evidence:
- Technical is a perfect 100.0 — the engine agrees the candidate is technically
  strong.
- Across the 23 real postings, **2 cases score ≥65 and are still SKIP** purely
  because of a blocker gate.
- Location blocks **8 of 26** cases despite carrying only 10% weight, because it
  behaves as a gate rather than a weighted term.

The human labelled this MAYBE, not NO: the reviewer weighed a perfect technical
score against a location condition the candidate may be able to resolve. The
engine cannot express that trade-off, because it collapses "does the evidence
support a strong match" and "should this person apply today" into one value.

## 4. Score decomposition (Gate B)

Every dimension is reconstructed from its requirement list and asserted equal to
the engine's own output. **26/26 audits verify**, so no scoring contribution is
unexplained.

## 5. Blocker integrity (Gate C)

| Source | Cases |
|---|---:|
| `_is_hard_location_block` → `_score_location` | 8 |
| `_score_education` | 4 |

Every blocker names its originating code path. `_score_technical` and
`_score_other` cannot emit blockers; a missing required skill never blocks, while
a missing required degree always does. This asymmetry is now pinned by tests so
it cannot drift silently, but it is undocumented product behaviour.

## 6. Diagnostic state distribution (26 cases)

| State | Count |
|---|---:|
| F Supported | 61 |
| B Material gap | 178 |
| C Competitive disadvantage | 22 |
| D Tailoring gap | 12 |
| E Evidence unknown | 96 |
| A Hard blocker | 12 |

## 7. Hypothesis results

| # | Hypothesis | Verdict | Evidence |
|---|---|---|---|
| H1 | Threshold mismatch | **Refuted** | 2 cases enter the APPLY band on score and are overridden by the blocker gate. Thresholds are not the cause. |
| H2 | Component weighting mismatch | **Weak** | Technical spread is 96.9 points at 40% weight; location spread 80.0 at 10%. Weight is not the distortion — input coverage is. |
| H3 | Location penalty mismatch | **Supported** | Location blocks 8/26 cases and caps scores at 20; 18/26 score ≤55. A gate at 10% weight. |
| H4 | Missing evidence treated too negatively | **Partly** | Engine already separates `unknowns` from `gaps` for non-required skills. But required skills with no match land in `gaps`, framed as deficiency (178 cases). |
| H5 | Requirement classification error | **Supported** | Median 16 requirements/job (max 32). 81 EXPERIENCE requirements carry no duration. Importance distribution 351 REQUIRED / 94 PREFERRED. |
| H6 | Hard blocker semantics | **Supported** | Only 2 of 5 dimensions can block. Education and location can; skills and other cannot. |
| H7 | Suitability/action conflation | **Strongly supported** | VJ-01: technical 100, score 80.5, SKIP. This is the clearest finding. |
| H8 | Evidence coverage too keyword-oriented | **Supported** | Matching is exact-alias or token overlap; 96 requirements unmappable despite a populated alias table. |
| H9 | Experience scoring insufficiently discriminative | **Supported** | Range 80–100, median 84, 6 cases ≥95. Years ratio saturates when a 6-year candidate meets a 2–5 year requirement. |
| H10 | Other category too broad | **Supported** | Mixes salary, employment type and unclassifiable requirements; each unverifiable REQUIRED item is a flat 40/100. |

## 8. Reproducibility defect

Re-running the same 26 postings produced **different requirement lists in 20
cases and flipped the recommendation in 5**. The matching engine is
deterministic given inputs; requirement extraction is not.

Consequence: end-to-end reproducibility of a recommendation is not currently
achievable. The benchmark artifact freezes the requirement lists so that every
measurement in this report is repeatable, and re-running from the frozen artifact
reproduces 26/26.

## 9. Defects found

### D1 — P0, fixed (defect — years-less experience requirement was invisible)

An `EXPERIENCE` requirement extracted from a posting but carrying no
`years_required` appeared in **no output list at all**: not `matched`, not
`gaps`, not `blockers`, not `unknowns`. Adding a duration made it appear. 81 such
requirements exist across the benchmark.

The requirement contributed nothing to the score in either case, so the defect is
purely one of visibility — but it means "why did you recommend this?" had an
unreported input, violating Gate B and §19.

Fixed by reporting such requirements in `unknowns` with an explicit
"cannot be scored numerically / not established" detail. **Score-neutral and
recommendation-neutral**, verified by test and by 26/26 revalidation.

### D2 — P0, open (defect — requirement extraction is not reproducible)

See §8. The fix is outside the matching package and belongs to the extraction
layer. Not addressed here because changing extraction changes every score, which
requires human labels.

### D3 — P1, open (fragility — blocker detection is free-text substring matching)

`_is_hard_location_block` fires on `must` / `required` / `based in` / `relocat`
appearing anywhere in the requirement text. "Based in" and "must" are also how
ordinary descriptive phrasing is written, so blocker status depends on wording
rather than structure. This is how VJ-01 becomes SKIP.

### D4 — P1, open (asymmetry — only some dimensions can block)

A missing required degree is a hard blocker; a missing required skill is not.
Pinned by tests, but the asymmetry is not a deliberate documented policy.

## 10. Candidate profile caveat

The profile under test deliberately leaves `preferred_roles`,
`preferred_locations`, `remote_preference` and `minimum_salary` unset, because
the CV did not state them. This directly depresses the location dimension (no
remote preference, no preferred locations) and the salary component of `other`.
Any conclusion about the location dimension is therefore **confounded** by
incomplete profile data, and should not be treated as a property of the engine
alone.

## 11. Gates

| Gate | Result |
|---|---|
| A — Baseline preservation | PASS (26/26 from frozen inputs) |
| B — Requirement traceability | PASS (26/26 verified) |
| C — Blocker integrity | PASS (every blocker has a named source) |
| D — Human benchmark integrity | PASS for 3 labelled cases; 23 PENDING |
| E — Decision metrics | PASS |
| F — Root cause | PASS for the one disagreement; others undetermined without labels |
| G — No safety regression | PASS (307/307, all V1.1/V1.2/V2 suites intact) |
| H — No unsupported inference | PASS (unknown never promoted to supported) |
| I — Calibration justification | PASS — **no change proposed without evidence** |
| J — Explainability | PASS (improved by D1 fix) |
| K — Controlled revalidation | PASS |