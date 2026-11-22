# V3.3 Benchmark Population Reconciliation

Offline. **No provider calls. No extraction result modified. Frozen benchmark
unmodified.** The V3.3 experimental population is explicit membership in the
frozen benchmark, not a collection index range.

## Headline counts

| quantity | value |
| --- | ---: |
| `benchmark_population` | 26 |
| `collected_population` | 28 |
| `benchmark_from_collection` | 23 |
| `frozen_regression` | 3 |
| `excluded_collection_records` | 5 |

Arithmetic: 23 + 3 = 26 == benchmark_population OK; and 23 + 5 = 28 == collected_population OK

## Frozen benchmark

- sha256 `4199f5d386e1fb8b9be1a6c053c0c9cc6f2e6e8afeadc31112e650c34f37345f` — UNCHANGED
- cases 26; population order is the benchmark's own case order

## Benchmark members (26)

| # | job_id | class | source_status | provenance_status | source_len | source_origin |
| ---: | --- | --- | --- | --- | ---: | --- |
| 0 | VJ-01 | FROZEN_REGRESSION | VERIFIED | VERIFIED | 8674 | `validation_jobs/VJ-01_job*.json (archived capture)` |
| 1 | VJ-02 | FROZEN_REGRESSION | VERIFIED | VERIFIED | 5615 | `validation_jobs/VJ-02_job*.json (archived capture)` |
| 2 | VJ-03 | FROZEN_REGRESSION | VERIFIED | VERIFIED | 3070 | `validation_jobs/VJ-03_job*.json (archived capture)` |
| 3 | VJ-B01 | COLLECTED_BACKED | RESOLVED | VERIFIED | 3886 | `validation_jobs/postings/collected.json` |
| 4 | VJ-B02 | COLLECTED_BACKED | RESOLVED | VERIFIED | 3569 | `validation_jobs/postings/collected.json` |
| 5 | VJ-B03 | COLLECTED_BACKED | RESOLVED | VERIFIED | 1826 | `validation_jobs/postings/collected.json` |
| 6 | VJ-B04 | COLLECTED_BACKED | RESOLVED | VERIFIED | 4412 | `validation_jobs/postings/collected.json` |
| 7 | VJ-B05 | COLLECTED_BACKED | RESOLVED | VERIFIED | 3531 | `validation_jobs/postings/collected.json` |
| 8 | VJ-B06 | COLLECTED_BACKED | RESOLVED | VERIFIED | 3386 | `validation_jobs/postings/collected.json` |
| 9 | VJ-B07 | COLLECTED_BACKED | RESOLVED | VERIFIED | 3531 | `validation_jobs/postings/collected.json` |
| 10 | VJ-B08 | COLLECTED_BACKED | RESOLVED | VERIFIED | 3405 | `validation_jobs/postings/collected.json` |
| 11 | VJ-B09 | COLLECTED_BACKED | RESOLVED | VERIFIED | 7956 | `validation_jobs/postings/collected.json` |
| 12 | VJ-B10 | COLLECTED_BACKED | RESOLVED | VERIFIED | 2906 | `validation_jobs/postings/collected.json` |
| 13 | VJ-B11 | COLLECTED_BACKED | RESOLVED | VERIFIED | 4798 | `validation_jobs/postings/collected.json` |
| 14 | VJ-B12 | COLLECTED_BACKED | RESOLVED | VERIFIED | 5454 | `validation_jobs/postings/collected.json` |
| 15 | VJ-B13 | COLLECTED_BACKED | RESOLVED | VERIFIED | 5480 | `validation_jobs/postings/collected.json` |
| 16 | VJ-B14 | COLLECTED_BACKED | RESOLVED | VERIFIED | 5116 | `validation_jobs/postings/collected.json` |
| 17 | VJ-B15 | COLLECTED_BACKED | RESOLVED | VERIFIED | 3276 | `validation_jobs/postings/collected.json` |
| 18 | VJ-B16 | COLLECTED_BACKED | RESOLVED | VERIFIED | 5087 | `validation_jobs/postings/collected.json` |
| 19 | VJ-B17 | COLLECTED_BACKED | RESOLVED | VERIFIED | 3879 | `validation_jobs/postings/collected.json` |
| 20 | VJ-B18 | COLLECTED_BACKED | RESOLVED | VERIFIED | 7404 | `validation_jobs/postings/collected.json` |
| 21 | VJ-B19 | COLLECTED_BACKED | RESOLVED | VERIFIED | 4458 | `validation_jobs/postings/collected.json` |
| 22 | VJ-B20 | COLLECTED_BACKED | RESOLVED | VERIFIED | 3098 | `validation_jobs/postings/collected.json` |
| 23 | VJ-B21 | COLLECTED_BACKED | RESOLVED | VERIFIED | 4816 | `validation_jobs/postings/collected.json` |
| 24 | VJ-B23 | COLLECTED_BACKED | RESOLVED | VERIFIED | 6012 | `validation_jobs/postings/collected.json` |
| 25 | VJ-B28 | COLLECTED_BACKED | RESOLVED | VERIFIED | 4366 | `validation_jobs/postings/collected.json` |

Population provenance-verified: **26/26**; unresolved: 0.

## Excluded collected records (5)

| job_id | employer | population_status | exclusion_reason | identity |
| --- | --- | --- | --- | --- |
| VJ-B22 | ClickUp | EXCLUDED | `EXCLUDED_BY_PER_COMPANY_CAP` | DISTINCT |
| VJ-B24 | ClickUp | EXCLUDED | `EXCLUDED_BY_PER_COMPANY_CAP` | DISTINCT |
| VJ-B25 | ClickUp | EXCLUDED | `EXCLUDED_BY_PER_COMPANY_CAP` | DISTINCT |
| VJ-B26 | ClickUp | EXCLUDED | `EXCLUDED_BY_PER_COMPANY_CAP` | DISTINCT |
| VJ-B27 | ClickUp | EXCLUDED | `EXCLUDED_BY_PER_COMPANY_CAP` | DISTINCT |

### Per-exclusion detail

**VJ-B22** — Staff AI Engineer - AI Platform (ClickUp)  
- url : https://jobicy.com/jobs/152638-staff-ai-engineer-ai-platform
- posting text sha256 : `ed52bf84f79bea21b407b8a0e0da08b72b0fb9374a88ae70dd3fd0be1d089fde`
- identity : DISTINCT
- reason : selection keeps the first 2 postings per employer in collected.json file order; ClickUp contributed 2 benchmark case(s) (VJ-B20, VJ-B21) and this posting appears later in file order

**VJ-B24** — Senior AI Engineer - Multi-Agent Frameworks (ClickUp)  
- url : https://jobicy.com/jobs/152627-senior-ai-engineer-multi-agent-frameworks
- posting text sha256 : `f0fa43124c98d5f287ae6f37060a9369084b120e40ed244f7a3ec626c463a519`
- identity : DISTINCT
- reason : selection keeps the first 2 postings per employer in collected.json file order; ClickUp contributed 2 benchmark case(s) (VJ-B20, VJ-B21) and this posting appears later in file order

**VJ-B25** — Senior AI Engineer - AI Platform (ClickUp)  
- url : https://jobicy.com/jobs/152631-senior-ai-engineer-ai-platform
- posting text sha256 : `e6796574e71c226c9af440b9c343b28d5d7c7e164e00f0eca7277f66d33c3457`
- identity : DISTINCT
- reason : selection keeps the first 2 postings per employer in collected.json file order; ClickUp contributed 2 benchmark case(s) (VJ-B20, VJ-B21) and this posting appears later in file order

**VJ-B26** — Staff AI Engineer - Multi-Agent Frameworks (ClickUp)  
- url : https://jobicy.com/jobs/152636-staff-ai-engineer-multi-agent-frameworks
- posting text sha256 : `4c30bd3f855d2ac33cb94900f0c4476c912da49d3d4f48e891d827dec124406e`
- identity : DISTINCT
- reason : selection keeps the first 2 postings per employer in collected.json file order; ClickUp contributed 2 benchmark case(s) (VJ-B20, VJ-B21) and this posting appears later in file order

**VJ-B27** — Senior AI Engineer - AI Product (ClickUp)  
- url : https://jobicy.com/jobs/152634-senior-ai-engineer-ai-product
- posting text sha256 : `03427301323de415dbc2e2732ed2a580ff32d3d2edea7cc43a3ecd5648075f55`
- identity : DISTINCT
- reason : selection keeps the first 2 postings per employer in collected.json file order; ClickUp contributed 2 benchmark case(s) (VJ-B20, VJ-B21) and this posting appears later in file order

## Frozen regression provenance

Governing rule: a current database row alone is never sufficient; it is accepted only where an independent immutable archive pins byte-identical text.

| job_id | provenance_status | source_sha256 | len | archive | retrieved | evidence |
| --- | --- | --- | ---: | --- | --- | --- |
| VJ-01 | VERIFIED | `9f16157c97d1cd4c..` | 8674 | `validation_jobs/VJ-01_job1.json` | 2026-10-07 | A: exact source text artifact; D: database snapshot pinned by archive |
| VJ-02 | VERIFIED | `a88b8bb9254710b9..` | 5615 | `validation_jobs/VJ-02_job2.json` | 2026-10-07 | A: exact source text artifact; D: database snapshot pinned by archive |
| VJ-03 | VERIFIED | `45fb6961c84e22c6..` | 3070 | `validation_jobs/VJ-03_job3.json` | 2026-10-07 | A: exact source text artifact; D: database snapshot pinned by archive |

Evidence classes searched: A exact source text artifact; B prior
extraction-run input (no frozen case appears in any recorded run);
C benchmark embeds source text (it does not); D database snapshot accepted
only where an independent archive pins byte-identical text.

## Identity audit across all 28 collected postings

- duplicate source URLs : 0
- duplicate posting texts : 1 {'6c0f262137c7cdc6..': ['VJ-B05', 'VJ-B07']}
- duplicate title+employer : 0

No duplicate source URLs across the 28 collected postings. One identical posting-text hash pair exists (same employer, two different URLs); both are distinct benchmark members, so this is a source-side duplicate listing, not a benchmark defect.

## Harness selector

- module : `validation_jobs/benchmark_selector.py`
- definition : explicit benchmark membership -> job ids -> provenance-checked source
- `--from/--to` address : ordered benchmark member ids
- collection index used as population : False
- tests : `tests/test_v33_benchmark_selector.py`

