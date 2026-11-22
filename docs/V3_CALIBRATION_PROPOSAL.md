# V3 — Calibration Proposal

Written **after** diagnostic analysis, per the phase structure. Phase 1
(diagnostic), Phase 2 (benchmark expansion) and Phase 3 (requirement-level
analysis) are complete. This document is Phase 4.

---

## 1. Summary

**One change is proposed and implemented. Four are documented as candidates and
deliberately NOT implemented**, because the evidence needed to justify them does
not yet exist.

No threshold was changed. No weight was changed. No scoring rule was changed.

| ID | Change | Priority | Status |
|---|---|---|---|
| D1 | Report years-less experience requirements | P0 — correctness | **Implemented** |
| C1 | Require human labels for the 23 new benchmark cases | P0 — blocks calibration | **Requested, not implementable by me** |
| D2 | Make requirement extraction reproducible | P0 — correctness | Open, deferred |
| D3 | Replace free-text blocker detection with structured conditions | P1 — correctness | Open, deferred |
| C2 | Separate suitability from application action | P1 — design change | Open, deferred |
| C3 | Re-weight dimensions / retune thresholds | P2 | **Rejected — no evidence** |
| C4 | Improve experience discrimination | P2 | Open, deferred |
| C5 | Narrow the "Other" dimension | P2 | Open, deferred |

## 2. Implemented: D1 — report years-less experience requirements

**Defect.** `engine._score_experience` only branches on requirements that carry
`years_required`. An `EXPERIENCE` requirement without one appeared in no output
list — not `matched`, not `gaps`, not `blockers`, not `unknowns`. 81 such
requirements exist across the 26-case benchmark.

**Why this is defensible without human labels.** The fix changes *reporting*, not
arithmetic. A requirement with no duration cannot contribute to the years ratio
either before or after, so the score is identical by construction. Verified two
ways: a dedicated test asserting equivalence to having no such requirement, and a
26/26 revalidation reproducing every recommendation.

**Fix.** Such requirements are recorded in `unknowns` with the detail
"cannot be scored numerically… not established in your recorded evidence and not
treated as met."

**Verification.**

| Check | Result |
|---|---|
| Test suite | 307/307 pass |
| Recommendation-neutral | VJ-01/VJ-02/VJ-03 unchanged |
| Benchmark revalidation | 26/26 reproduced from frozen inputs |
| Audit verification | 26/26 |

## 3. C1 — human labels are required before calibration (P0, blocking)

**This is the most important item in this document.**

The specification requires ~15–25 human-labelled jobs. Three exist. I expanded
the benchmark to 26 real postings, but **I did not and cannot supply the human
labels**: I am not the candidate, and a YES/MAYBE/NO I assign would measure
agreement with my own priors — exactly the failure mode §24 prohibits.

Measured agreement on the three labelled cases is 2/3. That is not a calibration
signal.

**Requested action:** an independent human reviewer labels the 23 cases in
`docs/benchmark/matching_benchmark_v3.json` using the §10 format. Until then,
every scoring change below stays blocked.

## 4. Deferred: D2 — requirement extraction reproducibility (P0)

**Finding.** Re-running the same 26 postings produced different requirement lists
in 20 cases and flipped 5 recommendations. The matching engine is deterministic
given inputs; its primary input is not.

**Candidate change.** Persist the extracted requirement set with the job and make
re-matching operate on the stored set, so a match is reproducible against the
requirements actually reviewed. Alternatively, constrain extraction to a fixed
schema and pin the prompt/version.

**Why deferred.** Changing extraction changes every score in the benchmark.
Without human labels (§3) there is no way to tell whether the result improves
decisions or merely shifts them.

**Interim mitigation applied.** The benchmark artifact freezes the requirement
lists, so all V3 measurements are repeatable today.

## 5. Deferred: D3 — structured blocker detection (P1)

**Finding.** `_is_hard_location_block` fires on the substrings `must`,
`required`, `based in`, `relocat` anywhere in a requirement's text. Blocker status
— which can flip a 95/100 job to SKIP — therefore depends on wording. This is
exactly how VJ-01 becomes SKIP.

**Candidate change.** Make location restrictions a structured field extracted
deliberately (e.g. `requires_presence_in_country`, `relocation_required`) rather
than inferred from prose, and require an affirmative structured signal before a
blocker is raised.

**Why deferred.** It changes recommendations on 8 of 26 cases. Needs §3.

## 6. Deferred: C2 — separate suitability from application action (P1)

**Finding.** H7 is strongly supported. VJ-01 is technically a perfect match
(100/100, 80.5 overall) and is returned as SKIP because location is a gate. The
single scalar cannot represent "strong fit, one unresolved condition".

**Candidate change.** Report the score and the action separately: keep the
recommendation as the *action*, and expose suitability as the score with its
component breakdown, plus an explicit named list of unresolved conditions. This
is a presentation and semantics change, not a scoring change — it would let a
candidate override the action while seeing exactly why.

**Why deferred.** Even a presentation change alters what the user does with 54%
of the benchmark (SKIP-heavy). It should be agreed before the human-labelled
benchmark exists.

**Note.** V2 already provides most of the substrate for this: `ApplicationStrategy`
carries blockers, gaps, review notes and an action plan. The missing piece is
that the recommendation and the score remain fused.

## 7. Rejected: C3 — re-weight dimensions or retune thresholds

**Rejected on evidence grounds.**

The obvious temptation, given 14/26 SKIPs, is to lower the APPLY threshold.
The diagnostic shows this would be wrong:

- H1 is **refuted**: the cases that look like high-score SKIPs are blocked, not
  mis-thresholded. Lowering the threshold changes nothing for them.
- The overall score distribution is median 52.0 with maximum 80.5 — the engine
  has produced exactly **one** score in the APPLY band across 26 real jobs.
  That reflects a genuine capability mismatch on most of these senior/staff
  roles, not a mis-set threshold.

Per §18, "more jobs should be APPLY, so lower the threshold" is not a valid
reason. No weight or threshold is changed.

## 8. Deferred: C4 — experience discrimination (P2)

**Finding.** H9 supported: experience range 80–100, median 84, 6 cases ≥95. The
years ratio saturates whenever a 6-year candidate meets a 2–5 year requirement, so
the dimension barely separates "adequate" from "excellent".

**Candidate change.** Use a bounded, saturating-but-discriminating curve (e.g.
credit between 1.0× and 1.5× the requirement) and incorporate relevance of
experience type, not only duration and title.

**Why deferred.** Changes 26/26 scores.

## 9. Deferred: C5 — narrow the "Other" dimension (P2)

**Finding.** H10 supported. `_score_other` averages salary, employment type and
every requirement the extractor could not type. Each unverifiable REQUIRED item is
assigned a flat 40/100 by construction, so unrelated concepts are averaged as if
comparable. The dimension ranges 42.7–73.8 and is effectively noise.

**Candidate change.** Split salary and employment type into explicit dimensions;
route genuinely unclassifiable requirements to a low-weight residual.

**Why deferred.** Changes 26/26 scores.

## 10. Confounded evidence — do not calibrate on this

The candidate profile deliberately leaves `preferred_roles`,
`preferred_locations`, `remote_preference` and `minimum_salary` unset, because
the CV did not state them. This depresses the location dimension (no remote
preference, no preferred locations → base 70 rather than 100) and the salary
component of `other` (70 @ 0.4 rather than a real comparison).

**Any conclusion about the location dimension is confounded by incomplete
profile data** and must not be read as a property of the engine. The CV may
simply not have recorded a remote preference.

## 11. Recommended sequence

1. Independent human labels 23 benchmark cases (§3). Unblocks everything else.
2. Complete profile fields that are legitimately unknown — or record them as
   explicitly unknown rather than absent — then re-run. Removes the §10 confound.
3. D2 reproducibility fix, so a match is reproducible against reviewed inputs.
4. Re-run this diagnostic with real agreement metrics.
5. Then and only then consider C2, C4, C5, and only with §18-style justification.

Thresholds and weights stay frozen until step 4 produces evidence.