# VJ-B04 Forensic Audit

Generated 2026-10-08T05:50:11+00:00

Implementation identifier: `dcc4f506965d57e99bf0bb54bdd1c429`
Prompt SHA-256: `43d20b8be806e7ba`
Experiment artifact SHA-256: `b5219afb275c39830d8ffc3f11594450`

Runs used:

- `VJ-B04:run1@2026-10-08T05:25:01+00:00`
- `VJ-B04:run2@2026-10-08T05:25:23+00:00`
- `VJ-B04:run3@2026-10-08T05:25:53+00:00`

Payload hashes (raw provider output, per run):

- run 1: `7768c9e1c7489bc2a0d7c6809243c753`
- run 2: `4caa151a9dbc7babad2d9719dd1f19c8`
- run 3: `f0e07334c52c61f3c5ab9cb1c41281d0`

## Counts

| | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| raw requirements | 17 | 17 | 24 |
| canonical requirements | 17 | 17 | 24 |
| score | 54.25 | 54.25 | 52.96 |
| recommendation | STRETCH | STRETCH | STRETCH |

Distinct requirements appearing in any run: **29**
Present in all three runs: **10**

## Run-3-only requirements

| Requirement | Importance | Source context | Evidence in posting |
|---|---|---|---|
| desire to build something strategically important and make | SOFT_SIGNAL | AMBIGUOUS | True |
| ex-founder mentality or the mindset of an early engineer w | SOFT_SIGNAL | BEHAVIORAL_EXPECTATION | True |
| reliable systems | REQUIRED | AMBIGUOUS | None |
| scalable systems | REQUIRED | AMBIGUOUS | None |
| senior, highly autonomous, and unusually strong at turning | SOFT_SIGNAL | EMPLOYER_MARKETING | True |
| strong backend engineering skills and good judgment around | PREFERRED | AMBIGUOUS | True |

## Absent from Run 3

| Requirement | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| desire to build strategically important products and make  | SOFT_SIGNAL | None | - |
| ex-founder mentality or early-engineer mindset focused on  | SOFT_SIGNAL | None | - |
| excellent taste and technical judgment | SOFT_SIGNAL | None | - |
| founders, very early startup engineers, senior builders wh | PREFERRED | PREFERRED | - |
| hybrid work in berlin office, typically 4 days per week | SOFT_SIGNAL | None | - |
| scalable reliable systems | REQUIRED | None | - |
| strong track record of owning systems or products end-to-e | PREFERRED | None | - |

## Run-3-only source context distribution

- AMBIGUOUS: 4
- BEHAVIORAL_EXPECTATION: 1
- EMPLOYER_MARKETING: 1

## Shared-source-quote clusters

The same verbatim source quote was emitted under different requirement names in different runs. These are paraphrase/granularity variants of one underlying requirement, not new requirements.

| Source quote (identical) | Names observed |
|---|---|
| `a desire to build something strategically important and make decisions that matt` | a desire to build something strategically important and make<br>desire to build something strategically important and make d<br>desire to build strategically important products and make de |
| `a strong track record of owning systems or products end-to-end, not just contrib` | a strong track record of owning systems or products end-to-e<br>strong track record of owning systems or products end-to-end |
| `an ex-founder mentality or the mindset of an early engineer who likes real owner` | an ex-founder mentality or the mindset of an early engineer <br>ex-founder mentality or the mindset of an early engineer who |

## Three-way matrix

| Requirement | Category | r1 | r1 imp | r2 | r2 imp | r3 | r3 imp | Selection | Classification |
|---|---|---|---|---|---|---|---|---|---|
| a desire to build something strategically im | EXPERIENCE,TECHNICAL | - | - | Y | SOFT_SIGNAL | Y | PREFERRED | PARTIAL_PRESENCE | NOT_APPLICABLE |
| a strong track record of owning systems or p | EXPERIENCE | - | - | Y | PREFERRED | Y | PREFERRED | PARTIAL_PRESENCE | NOT_APPLICABLE |
| agent-driven development | TECHNICAL | Y | REQUIRED | Y | REQUIRED | Y | REQUIRED | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| an ex-founder mentality or the mindset of an | EXPERIENCE,SOFT_SIGNAL | - | - | Y | SOFT_SIGNAL | Y | SOFT_SIGNAL | PARTIAL_PRESENCE | NOT_APPLICABLE |
| automation | TECHNICAL | Y | REQUIRED | Y | REQUIRED | Y | REQUIRED | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| backend engineering | TECHNICAL | Y | REQUIRED | Y | REQUIRED | Y | REQUIRED | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| coding-agent workflows | TECHNICAL | Y | REQUIRED | Y | REQUIRED | Y | REQUIRED | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| data pipelines | TECHNICAL | Y | REQUIRED | Y | REQUIRED | Y | REQUIRED | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| deep hands-on experience with agent-driven d | EXPERIENCE | Y | PREFERRED | Y | PREFERRED | Y | PREFERRED | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| desire to build something strategically impo | TECHNICAL | - | - | - | - | Y | SOFT_SIGNAL | RUN_3_ONLY | NOT_APPLICABLE |
| desire to build strategically important prod | TECHNICAL | Y | SOFT_SIGNAL | - | - | - | - | RUN_1_ONLY | NOT_APPLICABLE |
| ex-founder mentality or early-engineer minds | SOFT_SIGNAL | Y | SOFT_SIGNAL | - | - | - | - | RUN_1_ONLY | NOT_APPLICABLE |
| ex-founder mentality or the mindset of an ea | SOFT_SIGNAL | - | - | - | - | Y | SOFT_SIGNAL | RUN_3_ONLY | NOT_APPLICABLE |
| excellent taste and technical judgment | TECHNICAL | Y | SOFT_SIGNAL | - | - | - | - | RUN_1_ONLY | NOT_APPLICABLE |
| excellent taste and technical judgment - you | TECHNICAL | - | - | Y | SOFT_SIGNAL | Y | SOFT_SIGNAL | PARTIAL_PRESENCE | NOT_APPLICABLE |
| experience building around brittle external  | EXPERIENCE | Y | PREFERRED | Y | PREFERRED | Y | PREFERRED | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| founders, very early startup engineers, seni | EXPERIENCE | Y | PREFERRED | Y | PREFERRED | - | - | PARTIAL_PRESENCE | NOT_APPLICABLE |
| high agency, strong prioritization skills, a | TECHNICAL | Y | SOFT_SIGNAL | Y | SOFT_SIGNAL | Y | SOFT_SIGNAL | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| hybrid work in berlin office, typically 4 da | WORK_CONDITION | Y | SOFT_SIGNAL | - | - | - | - | RUN_1_ONLY | NOT_APPLICABLE |
| hybrid work in berlin-mitte office, typicall | WORK_CONDITION | - | - | Y | SOFT_SIGNAL | Y | SOFT_SIGNAL | PARTIAL_PRESENCE | NOT_APPLICABLE |
| operational workflows | TECHNICAL | - | - | Y | REQUIRED | Y | REQUIRED | PARTIAL_PRESENCE | NOT_APPLICABLE |
| reliable systems | TECHNICAL | - | - | - | - | Y | REQUIRED | RUN_3_ONLY | NOT_APPLICABLE |
| scalable reliable systems | TECHNICAL | Y | REQUIRED | - | - | - | - | RUN_1_ONLY | NOT_APPLICABLE |
| scalable systems | TECHNICAL | - | - | - | - | Y | REQUIRED | RUN_3_ONLY | NOT_APPLICABLE |
| scraping | TECHNICAL | Y | REQUIRED | Y | REQUIRED | Y | REQUIRED | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| senior, highly autonomous, and unusually str | TECHNICAL | - | - | - | - | Y | SOFT_SIGNAL | RUN_3_ONLY | NOT_APPLICABLE |
| significant experience as a software enginee | EXPERIENCE | Y | SOFT_SIGNAL | Y | SOFT_SIGNAL | Y | SOFT_SIGNAL | STABLE_ALL_RUNS | STABLE_IMPORTANCE |
| strong backend engineering skills and good j | EXPERIENCE | - | - | - | - | Y | PREFERRED | RUN_3_ONLY | NOT_APPLICABLE |
| strong track record of owning systems or pro | EXPERIENCE | Y | PREFERRED | - | - | - | - | RUN_1_ONLY | NOT_APPLICABLE |