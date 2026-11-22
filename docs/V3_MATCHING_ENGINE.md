# V3 — Matching Engine Reference (as implemented)

Frozen baseline. Nothing in this document is aspirational: it describes the code
that runs. `packages/matching/matching/{engine,config,normalize}.py` is
authoritative if this document and the code ever disagree.

---

## 1. Pipeline

```
JobProfile.requirements ─┬─► _score_technical   (weight 0.40)
                          ├─► _score_experience (weight 0.25)
                          ├─► _score_education  (weight 0.10)
                          ├─► _score_location   (weight 0.10)
                          └─► _score_other      (weight 0.15)
                                    ↓
overall = Σ (dimension_score × weight), clamped 0..100
                                    ↓
recommendation = policy.decide(overall, has_blocker)
```

## 2. Overall score

```
overall = clamp(
    technical × 0.40
  + experience × 0.25
  + education  × 0.10
  + location   × 0.10
  + other      × 0.15
)
```

Weights are normalised at construction; they sum to exactly 1.0.

## 3. Requirement importance weights

Applied *within* a dimension, not to the overall score.

| Importance | Weight |
|---|---:|
| `REQUIRED` | 1.00 |
| `PREFERRED` | 0.45 |
| `SOFT_SIGNAL` / `INFORMATIONAL` | 0.05 |
| anything else (e.g. `UNKNOWN`) | 0.65 |

Soft signals receive 0.05 specifically so aspirational boilerplate cannot
materially penalise a candidate.

## 4. Technical dimension (weight 0.40)

```
score = 100 × Σ(weight_i × credit_i) / Σ(weight_i)
```

`credit_i` comes from `_skill_names_match(required, held)`:

| Condition | Credit | Exact |
|---|---:|---|
| Canonical names equal after alias resolution | 1.00 | yes |
| Token overlap ≥ 0.99 and token-set ratio ≥ 0.70 | 1.00 | yes |
| Any token overlap | `overlap × 0.70` | no |
| No shared token | 0.00 | no |

Alias resolution is a fixed table (`DEFAULT_SKILL_ALIASES`) mapping surface
variants onto ~40 canonical names. **Matching is exact-alias or token overlap
only. No semantic inference.**

Routing of the outcome:

| Outcome | Recorded as |
|---|---|
| credit ≥ 0.999 | `matched` |
| 0 < credit < 0.999 | `gaps` (partial, never a full match) |
| credit == 0 and `REQUIRED` | `gaps` |
| credit == 0 and not `REQUIRED` | `unknowns` |

If no SKILL requirements exist, the dimension takes the flat
`unknown_requirement_score` = **70.0**. If the candidate has no skills at all,
technical = **0.0**.

## 5. Experience dimension (weight 0.25)

```
title_component = 50 + title_similarity × 50

if any EXPERIENCE requirement carries years_required AND candidate years known:
    score = title_component × 0.5 + years_ratio × 0.5
elif candidate years known:
    score = title_component × 0.8 + 20 × 0.2
else:
    score = title_component × 0.8
```

`years_ratio = clamp(candidate_years / years_required × 100)`, capped at 100.

`title_similarity` = best `token_overlap` between the job title and the
candidate's held titles / professional title / preferred roles, combined with a
seniority-level term: `level_score = clamp(100 − max(0, delta)×22 − max(0, −delta)×10)`
where `delta = candidate_rank − job_rank`. Below `title_similarity_partial`
(0.35) the contribution is zero; at or above `title_similarity_match` (0.60) it
is 1.0.

Candidate years come from `years_of_experience`, or are estimated by summing the
durations of recorded roles.

**An EXPERIENCE requirement with no `years_required` cannot influence this
dimension.** As of V3 defect D1 it is reported in `unknowns` instead of being
silently discarded.

## 6. Education dimension (weight 0.10)

Degree levels: PhD = 5, Master = 4, Bachelor = 3, Associate/diploma = 2.
The candidate's `max_level` is the highest of their recorded degrees.

| Case | Earned | Recorded as |
|---|---:|---|
| Open-ended ("any degree", "or equivalent") or no recognisable level | `0.9 × w` | `unknowns` |
| Level unresolvable on either side | `0.6 × w` | `unknowns` |
| `max_level ≥ required_level` | `1.0 × w` | `matched` |
| Below level, `REQUIRED` | `0` | **`blockers` + `gaps`** |
| Below level, not `REQUIRED` | `0` | `gaps` |

No education requirements → flat **70.0**. No candidate education → flat **70.0**
with unknowns recorded.

## 7. Location dimension (weight 0.10)

Work-mode base score:

| Job remote class | Candidate preference | Score |
|---|---|---:|
| `UNKNOWN` (job silent) | — | 70.0 |
| `REMOTE` | REMOTE / ANY / unset | 100.0 |
| `REMOTE` | ONSITE / HYBRID | 70.0 |
| `ONSITE` | REMOTE | 35.0 |
| `ONSITE` | HYBRID | 55.0 |
| `ONSITE` | other | 85.0 |

Then, if both locations are stated:

| Condition | Effect |
|---|---|
| Token overlap between the two locations | boost to ≥95 (unless severe remote conflict) |
| No overlap, job is `REMOTE` | no change — a remote role is not location-blocked |
| No overlap, **hard block** | `blockers` + `gaps`, score capped at 20.0 |
| No overlap, not a hard block | `gaps`, score capped at 55.0 |

A **hard block** requires *all* of: a `LOCATION` requirement with importance
`REQUIRED`, no location token overlap, and the requirement text containing one of
`must`, `required`, `based in`, `relocat`.

A job location matching one of the candidate's `preferred_locations` boosts to
≥98. If neither side states a location, the score is **65.0**.

Work-authorisation requirements are recognised but never scored: they are
recorded as `unknowns` with "verify manually", because the profile does not model
eligibility.

## 8. Other dimension (weight 0.15)

A weighted average of independent components, each `(score, weight)`:

| Component | Score | Weight |
|---|---:|---:|
| Posted max below candidate minimum salary | 15.0 | 1.0 |
| Salary range meets candidate minimum | 100.0 | 1.0 |
| Salary posted, candidate minimum unset | 70.0 | 0.7 |
| Salary not stated | 70.0 | 0.4 |
| Each unverifiable `REQUIRED` OTHER requirement | 40.0 | `_importance_weight` |
| Each non-`REQUIRED` OTHER requirement | 75.0 | `_importance_weight` |
| No OTHER requirements at all | 70.0 | 0.3 |

## 9. Blockers

**Exactly two code paths can emit a blocker.** This is a documented property,
now pinned by tests.

1. `engine._score_education` — a `REQUIRED` education requirement whose degree
   level exceeds the candidate's highest recorded level.
2. `engine._is_hard_location_block` → `engine._score_location` — the conditions in
   §7.

`_score_technical` and `_score_other` **can never** emit a blocker. A missing
required *skill* is recorded as a gap only; a missing required *degree* is
always a blocker. That asymmetry is implementation behaviour, not a stated policy.

## 10. Recommendation policy

```python
def decide(overall_score, has_blocker):
    if has_blocker:                        return "SKIP"
    if overall_score >= 80.0:              return "APPLY"
    if overall_score >= 65.0:              return "APPLY_WITH_TAILORING"
    if overall_score >= 50.0:              return "STRETCH"
    return "SKIP"
```

**A blocker overrides the score entirely.** A job scoring 95 with one blocker
returns `SKIP`. This is the mechanism behind the Monzo case.

## 11. Confidence

A profile-completeness sum (skills 0.30, experience 0.25, education 0.15,
location 0.10, years 0.10, requirements 0.10), minus 0.05 per dimension whose
notes indicate an unextracted requirement, mapped onto
`floor 0.35 → ceiling 0.95`. Confidence is **advisory only** and does not affect
the recommendation.

## 12. Reproducibility boundary

The engine is deterministic **given its inputs**. The upstream requirement
extraction is not: across two runs of the same 26 postings, 20 produced different
requirement lists and 5 flipped recommendation. End-to-end reproducibility
therefore requires freezing the extracted requirement list, which is what
`docs/benchmark/matching_benchmark_v3.json` does.

## 13. V3 change log

| Change | Effect on scores | Effect on recommendations |
|---|---|---|
| `matching/diagnostics.py` (new, additive) | none | none |
| D1: years-less EXPERIENCE requirements reported in `unknowns` | none | none |

No weight, threshold or scoring rule was modified.