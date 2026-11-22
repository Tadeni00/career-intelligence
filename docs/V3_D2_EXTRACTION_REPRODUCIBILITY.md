# V3 — D2: Extraction Reproducibility Diagnostic

Diagnostic continuation. **No scoring weight, threshold, blocker rule, or
recommendation rule was changed.** No prompt, model, temperature or parsing rule
was changed.

---

## 1. Run identity

Every extraction call is recorded with the following identity, not just a
timestamp:

| Field | Value |
|---|---|
| Provider | `openai` (OpenAI-compatible) |
| Base model | `openai/gpt-oss-120b` |
| Base URL | Groq |
| Temperature | `0.1` |
| **Seed** | **`None` — not sent** |
| Response format | `{"type": "json_object"}` |
| Max retries | 1 |
| Schema version | `ExtractedJobRequirements@1` |
| System prompt | SHA-256 recorded per run |
| User prompt | SHA-256 recorded per run |
| Source text | SHA-256 of the exact posting |
| Candidate profile | `val_profile_fixed.json`, unchanged since V1 |

## 2. Live re-sampling: BLOCKED

The controlled 3-run experiment could not be executed against the live provider:

```
429 rate_limit_exceeded — tokens per day
Limit 200000, Used 198852, Requested 2002
```

Daily quota is exhausted, so 78 fresh extraction calls were impossible. The
experiment harness is written and committed
(`validation_jobs/scripts/v3_extraction_experiment.py`) and runs unmodified once
quota resets.

**Consequence:** the per-case structural diff requested in §6 is **not available
for this milestone.** The aggregate result from the previous milestone
(20/26 unstable, 5 recommendation flips) is the only directly observed evidence,
and the pre/post artifact that held the per-case detail was deleted after that
milestone's report. This is a real gap and is recorded as such rather than
reconstructed from memory.

## 3. Deterministic severity measurement

Because live sampling is blocked, severity was established by exhaustively
applying each class of variation the extraction prompt *permits* to all 26 frozen
requirement sets. This covers every mechanism rather than a sample of them.

| ID | Mutation | n | score changed | blocker changed | **decision changed** | max Δ | Severity |
|---|---|---:|---:|---:|---:|---:|---|
| M1 | reordering only | 25 | 0 | 0 | **0** | 0.0 | Level 0 |
| M2 | alias / surface renaming | 9 | 0 | 0 | **0** | 0.0 | Level 0 |
| M3 | REQUIRED → PREFERRED (one skill) | 25 | 23 | 0 | **3** | 3.96 | Level 2 |
| M4 | PREFERRED → REQUIRED (one skill) | 14 | 12 | 0 | **0** | 1.68 | Level 2 |
| M5 | add an absent REQUIRED skill | 26 | 25 | 0 | **2** | 28.0 | Level 2 |
| M6 | remove a held REQUIRED skill | 25 | 23 | 0 | **3** | 8.0 | Level 2 |
| M7 | attach `years_required` to an EXPERIENCE req | 26 | 19 | 0 | **6** | 5.0 | Level 2 |
| M8 | add a hard LOCATION requirement | 26 | 19 | 19 | **9** | 3.5 | **Level 3** |
| M9 | drop an existing LOCATION requirement | 19 | 7 | 7 | **2** | 3.5 | **Level 3** |
| M10 | add a REQUIRED degree above level | 26 | 21 | 26 | **9** | 7.0 | **Level 3** |
| M11 | entire extraction lost (parse failure) | 26 | 26 | 4 | **23** | 32.21 | **Level 3** |

**Level 3 mutation classes: M8, M9, M10, M11.** The five previously observed
recommendation flips are the Level-2 classes M3/M5/M6/M7 acting on jobs that were
already near a threshold.

## 4. Root cause

### Primary — D2-D, schema/parsing instability (highest severity)

Deterministically demonstrated, no provider required:

| Input shape | `_coerce_job_requirements` repaired? | Schema result |
|---|---|---|
| `required_skills: [{"name": "Python", …}]` | **yes** → `["Python"]` | VALID |
| `required_skills: ["Python"]` | n/a | VALID |
| `experience_requirements: ["5+ years of ML"]` | **no** | **INVALID — entire extraction discarded** |

`_coerce_job_requirements` repairs only the four *string* arrays. The four
`*_requirements` object arrays pass through untouched. A bare string there
invalidates the whole `ExtractedJobRequirements`, so the job silently ends up with
**zero** requirements.

The consequence is the single most severe finding in this document:

> **M11 — a lost extraction produces a MORE positive recommendation.** With no
> requirements, technical/education/other fall back to their neutral 70.0 and
> experience keeps tenure credit, giving **72.0 → APPLY_WITH_TAILORING** for a job
> the system never actually read. It flips the decision in **23 of 26** cases and
> in every observed case moved the recommendation *upward*.

A parsing failure must never be more optimistic than a successful parse.

### Contributing — D2-C, requirement classification ambiguity

The prompt gives no calibration for *which* requirements are mandatory, and no
cap on list length; it says only "Do not treat every sentence as a hard
requirement". Measured consequence:

- One `REQUIRED → PREFERRED` flip moves the technical score in 23/25 cases.
- Because an unmet REQUIRED item dilutes the ratio with weight 1.00 against
  0.45, **downgrading** a requirement *raises* the score.
- Attaching or omitting `years_required` moves the experience score in 19/26.
- Requirement counts vary widely (median 16, max 32 per posting).

### Contributing — D2-A, model stochasticity

Temperature is `0.1` and **no seed is sent**, so identical input can yield
different output. This is the mechanism consistent with the observed 20/26
instability. It cannot be isolated from D2-C with the evidence available.

### Excluded

- **D2-E source instability** — posting text is fetched once, hashed, and frozen.
- **D2-F configuration drift** — one provider/model recorded for the whole run.
- **D2-G normalization instability** — M2 measured 0/9 score and 0/9 decision
  changes, so representation differences of this kind are not material.

### Severity

**LEVEL 3 — decision-changing.** M11 alone flips 23/26 cases.

## 5. Recommendation

```
D2 root cause:
  Schema/parsing instability (D2-D) - a single bare string in any
  *_requirements array discards the entire extraction - amplified by
  requirement-classification ambiguity (D2-C) and unseeded sampling (D2-A).

Severity: LEVEL 3 - decision-changing (23/26 cases for the parse-failure path)

Benchmark impact:
  A lost or degraded extraction makes the system MORE positive, not less.
  Recommendation flips are dominated by requirement classification, and the
  observed flips are near thresholds rather than deep in a band.

Recommended correction:
  1. Make the coercion symmetric: coerce the four *_requirements object arrays
     exactly as the four string arrays are coerced, so a bare string becomes
     {"name": <string>} instead of invalidating the extraction.
  2. Surface extraction failure explicitly. Zero extracted requirements should
     be recorded as an extraction failure, not treated as a requirement-free job.
     This is the single highest-value correction available.
  3. Require a non-empty requirement set before a job is matchable, or score a
     zero-requirement job as UNKNOWN rather than on neutral defaults.
  4. Add a seed and record it; freeze the extracted requirement set against the
     job so a re-match is reproducible against reviewed inputs.

Should extraction be made deterministic?
  YES for steps 1-3 (correctness, not tuning). The stochastic component cannot be
  removed without changing the model call, which is out of scope here.

Can the existing frozen benchmark remain valid?
  CONDITIONAL - see section 6.
```

Steps 1–3 are correctness fixes to the extraction boundary, not calibration of
the matching engine. They are **not implemented in this task** because §2.2
requires the cause to be documented first, and because implementing them would
change the benchmark before the labels exist.

## 6. Benchmark validity decision: **CONDITIONAL VALID**

**A — Valid.** Not chosen: D2 is Level 3 and 20/26 extractions were observed
unstable, so a live re-extraction would move the benchmark.

**C — Invalid.** Not chosen: the frozen artifact *is* reproducible — 26/26 cases
recompute identically from it — and the mutations above show the engine side is
deterministic given inputs.

**B — Conditionally valid.** Chosen. The frozen requirement sets are the
benchmark truth because they are hash-traceable and reproduce exactly. The
following annotation applies and is recorded in the benchmark artifact:

> Extraction stability is **unverified per case** for the 23 pending-label
> postings. Live re-sampling was blocked by provider quota, and the aggregate
> observation (20/26 unstable) cannot be attributed to individual cases. The
> frozen sets are used as-is and are NOT re-extracted; any future re-extraction
> invalidates the labels collected against them.

## 7. Reproducibility status (26/26)

| Status | Count | Detail |
|---|---:|---|
| Reproducible from frozen artifact | 26/26 | score and recommendation identical on recompute |
| Audit fully decomposed | 26/26 | every score traced to named requirements |
| Per-case extraction stability verified | **0/23** | blocked by provider quota |
| Aggregate instability observed | 20/26 | previous milestone |
| Recommendation flips observed | 5/26 | VJ-B04, B05, B07, B09, B18 |

The five flip cases are explained *mechanistically* by the mutation classes above
(M3/M5/M6/M7), but the specific requirement that differed in each case is **not
recoverable** without live re-sampling.