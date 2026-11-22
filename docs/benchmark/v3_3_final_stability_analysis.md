# V3.3 Final Stability Analysis

Derived artifact. Read-only over frozen inputs. No inference call was made
and no experiment artifact was modified.

## 1. Executive verdict

- Canonical **count** reproducibility: 2/26 (7.7%) jobs had equal counts across all three runs.
- Canonical **identity-set** reproducibility: 0/26 (0.0%).
- Mean pairwise identity Jaccard: 0.3078 (median 0.3161, min 0.0, max 0.8824, n=78 pairs).
- Recommendation stability: 19/26 (73.1%); 7 jobs changed decision.

Full section-by-section results follow. No correctness or quality claim
is made anywhere in this report: the human-label set is 0/23.

## 2. Prerequisite and integrity verification

- ledger records : 81
- ledger sha256  : `6f8f6a1ee5f54acb1bd9d9270f89edf8c244c72118381c21931feb20740557c0`
- members with 3/3: 26/26
- partial triplets: none
- ledger conflicts: none
- preserved failures: [('VJ-B05', 1), ('VJ-B07', 3), ('VJ-B14', 1)]
- successful runs: 78
- runs with persisted raw_extraction: 66/78
- runs with persisted coerced_extraction: 66/78
- runs with measured usage: 66/78

## 3. Methods and metric definitions

- **identity_tuple** : (name, type, importance, category, years_required, evidence_status, work_condition) as persisted by canonical_requirements[].identity
- **identity_set_stability** : all three runs' full 7-field identity sets are equal
- **name_set_stability** : all three runs' field-0 sets are equal (selection unit)
- **jaccard** : J(A,B)=|A n B|/|A u B|; empty union returns None (undefined)
- **selection_denominator** : two distinct denominators reported and never mixed: UNIQUE identities per job, and total run-level requirement occurrences (sum of the three counts)
- **classification_alignment** : exact field-0 name match; a name must appear in >=2 of 3 runs to be classified as aligned
- **evidence_audit** : mechanical quote-correspondence only: normalised substring check of requirement source_text inside the frozen posting. PRELIMINARY -- does not adjudicate semantic support
- **missing_data** : runs without persisted raw/coerced extraction or usage are reported as null/absent; never imputed

## 4. Benchmark-wide aggregate tables

### A. Structural extraction stability

| metric | value | denominator |
| --- | --- | ---: |
| jobs, all 3 counts equal | 2 | 26 |
| jobs, identity sets identical | 0 | 26 |
| jobs, name sets identical | 0 | 26 |
| equal counts but different identities | 2 | 26 |
| Jaccard(identity) mean | 0.3078 | 78 pairs |
| Jaccard(identity) median | 0.3161 | 78 |
| Jaccard(identity) min | 0.0 | 78 |
| Jaccard(identity) max | 0.8824 | 78 |
| Jaccard(name) mean | 0.3509 | 78 pairs |
| count range mean | 5.462 | 26 |
| count range max | 23 | 26 |
| jobs with zero count range | 2 | 26 |

Lowest identity Jaccard:

| job | min pair Jaccard | counts |
| --- | ---: | --- |
| VJ-B03 | 0.0 | [7, 6, 6] |
| VJ-B11 | 0.0 | [23, 32, 9] |
| VJ-B20 | 0.0 | [20, 2, 1] |
| VJ-B28 | 0.0 | [19, 16, 19] |
| VJ-B09 | 0.05 | [12, 9, 9] |
| VJ-B12 | 0.0769 | [17, 9, 19] |
| VJ-B15 | 0.1111 | [10, 10, 13] |
| VJ-02 | 0.1389 | [16, 19, 25] |

Greatest count variation:

| job | count range | counts |
| --- | ---: | --- |
| VJ-B11 | 23 | [23, 32, 9] |
| VJ-B20 | 19 | [20, 2, 1] |
| VJ-B12 | 10 | [17, 9, 19] |
| VJ-02 | 9 | [16, 19, 25] |
| VJ-B13 | 9 | [11, 19, 10] |
| VJ-B14 | 9 | [24, 31, 33] |
| VJ-B05 | 8 | [19, 22, 27] |
| VJ-B23 | 8 | [8, 11, 16] |

### B. Requirement selection stability

Two denominators, never mixed.

| quantity | value | denominator |
| --- | ---: | --- |
| unique identity TUPLES in union | 814 | - (separate measure) |
| unique NAMES in union | 759 | 759 |
| names in all 3 runs | 164 | 759 |
| names in exactly 2 runs | 138 | 759 |
| names in exactly 1 run | 457 | 759 |
| run-level requirement occurrences | 1248 | 1248 |
| pairwise additions (total) | 602 | 78 pairs |
| pairwise removals (total) | 588 | 78 pairs |
| partition check (all3+two+one == name union) | True | - |

The identity-tuple union exceeds the name union because one name can carry
different importance or category across runs. The two are reported
separately and never used as each other's denominator.

### C. Classification stability

| quantity | value | denominator |
| --- | ---: | --- |
| aligned requirements | 302 | 302 |
| aligned and consistent | 257 | 302 |
| aligned and inconsistent | 45 | 302 |
| presence-stable but classification changed | 24 | 302 |
| importance values observed | {'REQUIRED': 532, 'SOFT_SIGNAL': 202, 'PREFERRED': 514} | - |
| INFORMATIONAL observed | 0 | - |

Importance transitions (exact-name aligned, present in all 3 runs, importance differs):

| job | name | values seen |
| --- | --- | --- |
| VJ-02 | airflow | PREFERRED -> REQUIRED |
| VJ-02 | catboost | PREFERRED -> REQUIRED |
| VJ-02 | claude code | PREFERRED -> REQUIRED |
| VJ-02 | cursor | PREFERRED -> REQUIRED |
| VJ-02 | kubeflow | PREFERRED -> REQUIRED |
| VJ-02 | lightgbm | PREFERRED -> REQUIRED |
| VJ-02 | mlflow | PREFERRED -> REQUIRED |
| VJ-02 | xgboost | PREFERRED -> REQUIRED |
| VJ-03 | python | PREFERRED -> REQUIRED |
| VJ-B01 | reliability | PREFERRED -> SOFT_SIGNAL |
| VJ-B01 | strong self-organizational skills | PREFERRED -> SOFT_SIGNAL |
| VJ-B02 | reliability | PREFERRED -> SOFT_SIGNAL |
| VJ-B04 | a desire to build something strategically important and  | PREFERRED -> SOFT_SIGNAL |
| VJ-B04 | excellent taste and technical judgment - you know when s | PREFERRED -> SOFT_SIGNAL |
| VJ-B05 | metabase | PREFERRED -> REQUIRED |
| VJ-B05 | n8n | PREFERRED -> REQUIRED |
| VJ-B05 | power bi | PREFERRED -> REQUIRED |
| VJ-B05 | python | PREFERRED -> REQUIRED |
| VJ-B05 | sql | PREFERRED -> REQUIRED |
| VJ-B11 | batching | PREFERRED -> REQUIRED |
| VJ-B11 | capacity planning | PREFERRED -> REQUIRED |
| VJ-B11 | distributed serving | PREFERRED -> REQUIRED |
| VJ-B11 | latency vs throughput optimization | PREFERRED -> REQUIRED |
| VJ-B11 | lora | PREFERRED -> REQUIRED |
| VJ-B11 | model distillation | PREFERRED -> REQUIRED |
| VJ-B11 | multi-gpu serving | PREFERRED -> REQUIRED |
| VJ-B11 | multi-node serving | PREFERRED -> REQUIRED |
| VJ-B11 | python | PREFERRED -> REQUIRED |
| VJ-B11 | quantization | PREFERRED -> REQUIRED |
| VJ-B11 | reinforcement learning (rlhf, rlvr) | PREFERRED -> REQUIRED |
| VJ-B11 | speculative decoding | PREFERRED -> REQUIRED |
| VJ-B14 | results-driven approach and rapid iteration | PREFERRED -> SOFT_SIGNAL |
| VJ-B15 | edge deployment optimization | PREFERRED -> REQUIRED |
| VJ-B16 | activation modeling | PREFERRED -> REQUIRED |
| VJ-B16 | lifecycle analytics | PREFERRED -> REQUIRED |
| VJ-B16 | retention modeling | PREFERRED -> REQUIRED |
| VJ-B19 | ai-assisted software development | PREFERRED -> REQUIRED |
| VJ-B19 | github copilot | PREFERRED -> REQUIRED |
| VJ-B20 | ai fluency | PREFERRED -> SOFT_SIGNAL |

Category transitions:

| job | name | values seen |
| --- | --- | --- |
| VJ-B01 | large language models (llms) or vllms | EXPERIENCE -> SKILL |
| VJ-B01 | rag or openai | EXPERIENCE -> SKILL |
| VJ-B02 | python | EXPERIENCE -> SKILL |
| VJ-B04 | a desire to build something strategically important and  | EXPERIENCE -> OTHER |
| VJ-B04 | an ex-founder mentality or the mindset of an early engin | EXPERIENCE -> OTHER |
| VJ-B04 | excellent taste and technical judgment - you know when s | EXPERIENCE -> OTHER |
| VJ-B05 | sql | EXPERIENCE -> SKILL |
| VJ-B09 | solid foundation in mathematical statistics | EXPERIENCE -> OTHER |
| VJ-B15 | edge deployment optimization | EXPERIENCE -> SKILL |
| VJ-B19 | healthcare and/or claims adjudication experience | EXPERIENCE -> OTHER |

### D. Evidence and source support (PRELIMINARY)

| metric | value | denominator |
| --- | ---: | --- |
| requirement instances examined | 1248 | 1248 |
| carrying an evidence quote | 615 | 1248 |
| **no evidence quote at all** | 633 | 1248 |
| quote found verbatim in source | 572 | 615 (evidence-bearing) |
| quote not found verbatim | 43 | 615 (evidence-bearing) |
| quote-found rate among evidence-bearing | 0.9301 | 615 |
| stripped-evidence notes | 0 | - |

No-evidence rate by requirement type:

| type | without quote | total | rate |
| --- | ---: | ---: | ---: |
| SKILL | 633 | 633 | 100.0% |
| EXPERIENCE | 0 | 268 | 0.0% |
| OTHER | 0 | 268 | 0.0% |
| LOCATION | 0 | 63 | 0.0% |
| EDUCATION | 0 | 16 | 0.0% |

**Root cause.** The extraction schema binds source_text to the structured requirement lists (experience/education/location/other) but not to required_skills or preferred_skills, which are list[str]. SKILL-type requirements are therefore unevidenced by construction, not by model omission. Persisted raw extraction confirms the model emitted 580 bare-string skill items and 492 dict items carrying source_text.

**Limitation.** NOT PERFORMED -- cannot be established mechanically. This audit measures quote correspondence only. A requirement whose quote appears in the posting may still misstate what the posting requires, and a paraphrased quote may fail a strict substring test while being faithful.

### E. Score stability

| metric | value | denominator |
| --- | ---: | --- |
| jobs with identical scores | 0 | 26 |
| identical scores but identity differs | 0 | 26 |
| score range mean | 5.788 | 26 |
| score range median | 2.25 | 26 |
| score range max | 27.75 | 26 |
| jobs with zero score range | 0 | 26 |

Causality: correlation between extraction change and score change is reported as co-occurrence only; no causal claim is made.

| job | score range | scores |
| --- | ---: | --- |
| VJ-B20 | 27.75 | [48.4, 76.15, 76.08] |
| VJ-B11 | 24.82 | [52.57, 44.38, 69.2] |
| VJ-B12 | 23.71 | [52.58, 76.29, 52.77] |
| VJ-B15 | 11.87 | [61.45, 61.45, 49.58] |
| VJ-02 | 8.02 | [55.7, 56.37, 48.35] |
| VJ-B14 | 7.11 | [72.12, 65.78, 65.01] |
| VJ-B06 | 5.55 | [48.68, 53.63, 54.23] |
| VJ-B13 | 5.45 | [53.71, 52.7, 58.15] |

### F. Recommendation stability

| quantity | value | denominator |
| --- | ---: | --- |
| jobs, all 3 recommendations equal | 19 | 26 |
| jobs with decision-changing variation | 7 | 26 |
| mean score range, stable-rec jobs | 2.293 | 19 |
| mean score range, unstable-rec jobs | 15.274 | 7 |
| mean identity Jaccard, stable-rec jobs | 0.3528 | 19 |
| mean identity Jaccard, unstable-rec jobs | 0.1857 | 7 |
| labels preserved (not merged) | ['APPLY', 'APPLY_WITH_TAILORING', 'SKIP', 'STRETCH'] | - |

| job | recommendations | scores | counts |
| --- | --- | --- | --- |
| VJ-02 | STRETCH -> STRETCH -> SKIP | [55.7, 56.37, 48.35] | [16, 19, 25] |
| VJ-B06 | SKIP -> STRETCH -> STRETCH | [48.68, 53.63, 54.23] | [17, 19, 18] |
| VJ-B07 | STRETCH -> STRETCH -> APPLY_WITH_TAILORING | [60.52, 59.86, 65.06] | [20, 21, 19] |
| VJ-B11 | STRETCH -> SKIP -> APPLY_WITH_TAILORING | [52.57, 44.38, 69.2] | [23, 32, 9] |
| VJ-B12 | STRETCH -> APPLY_WITH_TAILORING -> STRETCH | [52.58, 76.29, 52.77] | [17, 9, 19] |
| VJ-B15 | STRETCH -> STRETCH -> SKIP | [61.45, 61.45, 49.58] | [10, 10, 13] |
| VJ-B20 | SKIP -> APPLY_WITH_TAILORING -> APPLY_WITH_TAILORING | [48.4, 76.15, 76.08] | [20, 2, 1] |

## 5. Per-job results, all 26 members

| job | class | counts | ctr | ident sets | J(identity) mean | scores | range | recs | rec stable |
| --- | --- | --- | ---: | --- | ---: | --- | ---: | --- | --- |
| VJ-01 | REG | [9, 13, 9] | 4 | DIFF | 0.528 | [88.29, 88.63, 88.29] | 0.34 | APPLY/APPLY/APPLY | yes |
| VJ-02 | REG | [16, 19, 25] | 9 | DIFF | 0.331 | [55.7, 56.37, 48.35] | 8.02 | STRETCH/STRETCH/SKIP | NO |
| VJ-03 | REG | [11, 11, 11] | 0 | DIFF | 0.375 | [84.25, 83.26, 82.05] | 2.2 | APPLY/APPLY/APPLY | yes |
| VJ-B01 | COL | [18, 17, 17] | 1 | DIFF | 0.539 | [58.14, 56.73, 57.38] | 1.41 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B02 | COL | [16, 15, 16] | 1 | DIFF | 0.422 | [60.8, 62.48, 60.8] | 1.68 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B03 | COL | [7, 6, 6] | 1 | DIFF | 0.058 | [76.15, 76.58, 76.58] | 0.43 | APPLY_WITH_T/APPLY_WITH_T/APPLY_WITH_T | yes |
| VJ-B04 | COL | [17, 17, 24] | 7 | DIFF | 0.440 | [54.25, 54.25, 52.96] | 1.29 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B05 | COL | [19, 22, 27] | 8 | DIFF | 0.600 | [59.43, 59.58, 58.87] | 0.71 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B06 | COL | [17, 19, 18] | 2 | DIFF | 0.200 | [48.68, 53.63, 54.23] | 5.55 | SKIP/STRETCH/STRETCH | NO |
| VJ-B07 | COL | [20, 21, 19] | 2 | DIFF | 0.384 | [60.52, 59.86, 65.06] | 5.2 | STRETCH/STRETCH/APPLY_WITH_T | NO |
| VJ-B08 | COL | [9, 9, 10] | 1 | DIFF | 0.253 | [46.11, 47.07, 46.53] | 0.96 | SKIP/SKIP/SKIP | yes |
| VJ-B09 | COL | [12, 9, 9] | 3 | DIFF | 0.170 | [86.84, 85.97, 85.17] | 1.67 | APPLY/APPLY/APPLY | yes |
| VJ-B10 | COL | [12, 14, 16] | 4 | DIFF | 0.343 | [56.45, 54.15, 56.45] | 2.3 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B11 | COL | [23, 32, 9] | 23 | DIFF | 0.023 | [52.57, 44.38, 69.2] | 24.82 | STRETCH/SKIP/APPLY_WITH_T | NO |
| VJ-B12 | COL | [17, 9, 19] | 10 | DIFF | 0.181 | [52.58, 76.29, 52.77] | 23.71 | STRETCH/APPLY_WITH_T/STRETCH | NO |
| VJ-B13 | COL | [11, 19, 10] | 9 | DIFF | 0.217 | [53.71, 52.7, 58.15] | 5.45 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B14 | COL | [24, 31, 33] | 9 | DIFF | 0.396 | [72.12, 65.78, 65.01] | 7.11 | APPLY_WITH_T/APPLY_WITH_T/APPLY_WITH_T | yes |
| VJ-B15 | COL | [10, 10, 13] | 3 | DIFF | 0.180 | [61.45, 61.45, 49.58] | 11.87 | STRETCH/STRETCH/SKIP | NO |
| VJ-B16 | COL | [18, 19, 19] | 1 | DIFF | 0.495 | [59.46, 57.6, 59.46] | 1.86 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B17 | COL | [12, 18, 19] | 7 | DIFF | 0.361 | [64.75, 61.69, 60.43] | 4.32 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B18 | COL | [15, 16, 12] | 4 | DIFF | 0.180 | [55.6, 55.9, 54.79] | 1.11 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B19 | COL | [25, 27, 24] | 3 | DIFF | 0.623 | [47.65, 48.03, 47.42] | 0.61 | SKIP/SKIP/SKIP | yes |
| VJ-B20 | COL | [20, 2, 1] | 19 | DIFF | 0.000 | [48.4, 76.15, 76.08] | 27.75 | SKIP/APPLY_WITH_T/APPLY_WITH_T | NO |
| VJ-B21 | COL | [20, 20, 20] | 0 | DIFF | 0.349 | [57.15, 57.25, 57.86] | 0.71 | STRETCH/STRETCH/STRETCH | yes |
| VJ-B23 | COL | [8, 11, 16] | 8 | DIFF | 0.316 | [70.6, 70.75, 65.99] | 4.76 | SKIP/SKIP/SKIP | yes |
| VJ-B28 | COL | [19, 16, 19] | 3 | DIFF | 0.039 | [53.27, 55.26, 57.91] | 4.64 | STRETCH/STRETCH/STRETCH | yes |

## 6. Provider and execution anomalies

- HTTP 400 json_validate_failed events preserved: 3 at [('VJ-B05', 1), ('VJ-B07', 3), ('VJ-B14', 1)]
- runs with missing usage (null, not zero): [('VJ-B07', 3), ('VJ-B14', 1)]
- measured usage denominator: 66/78 calls
- measured total tokens: 317,537 (mean 4811.2/call)
- successful runs at exactly 3072 output tokens: 21
- link to extraction variability: NOT ESTABLISHED -- no persisted evidence links provider execution anomalies to extraction variability; reported separately

## 7. Focused case studies

| job | counts | identity sets | J mean | recs | distinct quotes | quotes reused | recovery |
| --- | --- | --- | ---: | --- | ---: | ---: | --- |
| VJ-B04 | [17, 17, 24] | DIFF | 0.440 | STRETCH/STRETCH/STRETCH | 17 | 10 | - |
| VJ-B11 | [23, 32, 9] | DIFF | 0.023 | STRETCH/SKIP/APPLY_WITH_TAI | 17 | 5 | - |
| VJ-B14 | [24, 31, 33] | DIFF | 0.396 | APPLY_WITH_TAI/APPLY_WITH_TAI/APPLY_WITH_TAI | 15 | 11 | VJ-B14/run1 |
| VJ-B15 | [10, 10, 13] | DIFF | 0.180 | STRETCH/STRETCH/SKIP | 11 | 8 | - |
| VJ-B20 | [20, 2, 1] | DIFF | 0.000 | SKIP/APPLY_WITH_TAI/APPLY_WITH_TAI | 3 | 1 | - |
| VJ-B23 | [8, 11, 16] | DIFF | 0.316 | SKIP/SKIP/SKIP | 14 | 4 | - |
| VJ-B28 | [19, 16, 19] | DIFF | 0.039 | STRETCH/STRETCH/STRETCH | 15 | 2 | - |
| VJ-02 | [16, 19, 25] | DIFF | 0.331 | STRETCH/STRETCH/SKIP | 13 | 6 | - |
| VJ-03 | [11, 11, 11] | DIFF | 0.375 | APPLY/APPLY/APPLY | 7 | 6 | - |
| VJ-01 | [9, 13, 9] | DIFF | 0.528 | APPLY/APPLY/APPLY | 14 | 7 | - |

## 8. Limitations and unresolved questions

- Human labels are 0/23. No accuracy, precision, recall, or recommendation
  correctness claim is possible. No proxy metric is substituted.
- `raw_extraction` / `coerced_extraction` are absent for the 12 pre-telemetry
  B01-B04 runs, so raw-vs-canonical divergence cannot be examined there.
- Evidence audit is mechanical quote matching only; semantic support is
  unresolved by construction.
- Classification alignment uses exact normalized-name matching, so a
  paraphrase pair is counted as one disappearance plus one appearance, not as
  a classification change.
- Three runs per job bound observed variability but do not characterise its
  distribution.
- The provider exposes no per-request reproducibility guarantee; nothing here
  separates model-sampling variability from contract ambiguity.

## 9. Conclusion

See the executive verdict and the six per-dimension verdicts in the chat
report. This artifact contains the measurements only.

