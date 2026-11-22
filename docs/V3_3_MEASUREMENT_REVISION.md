# V3.3 Measurement Revision

Two measurement-path defects were found and corrected. **The V3.3 extraction
experiment is unchanged.** Extraction contract remains
`ExtractedJobRequirements@2`.

```text
experiment              : v3.3_deterministic_extraction  (UNCHANGED)
implementation          : a8c9d8039cbdb779e37a1052db1afa04a92fc518a281963f35284c00c444ddc9
previous implementation : dcc4f506965d57e99bf0bb54bdd1c429
harness                 : 05011783f5211a4c96519321657e8fd930b24acc836da875f4cafaf1030b2008
previous harness        : 715be9a26725a131
prompt sha256           : 43d20b8be806e7ba130d4f1120cc9a4fe9456110a95048092323c3c68afbd436  (UNCHANGED, 5123 chars)
provider / model        : openai (OpenAI-compatible Groq) / openai/gpt-oss-120b  (UNCHANGED)
temperature / seed      : 0.1 / none  (UNCHANGED)
engine / config         : f8913c528710e3f3 / 0af42435d68b9463  (UNCHANGED)
benchmark               : 4199f5d386e1  (UNCHANGED)
human labels            : 292841efc8b1  (UNCHANGED, 0/23)
blind review pack       : d70aace7ae28  (UNCHANGED)
```

## Change A — Token-usage telemetry

`_json_completion` returned `json.loads(content)` and discarded
`response.usage`, so no per-call token telemetry existed for any V3.3 run. The
only token figure available anywhere was a 4,556-token estimate inferred from a
single 429 denial message.

### Files changed

| file | scope |
| --- | --- |
| `apps/api/app/ai/openai_provider.py` | added `_usage_record`, `_usage_total`, `finalize_usage`, `last_usage` attribute, 2 telemetry assignments |
| `validation_jobs/scripts/v33_runs.py` | added `snapshot_usage`, 4 telemetry fields per run record |
| `tests/test_v33_usage_telemetry.py` | new, 8 tests |

No provider abstraction was introduced. The return type of `_json_completion`
was left alone, so none of its five call sites changed.

### Captured fields

```text
provider, model, timestamp, available, attempts,
input_tokens, output_tokens, total_tokens,
extra   (provider-specific prompt/completion detail, preserved but never required)
```

### Proof extraction semantics are unchanged

The function still has exactly one return statement, byte-identical to before:

```python
content = response.choices[0].message.content or ""
return json.loads(content)
```

The two inserted lines sit between `create()` and the `content` read, and write
only to `usage_records` and `self.last_usage`. Neither is read by the parse path.
The request shape is untouched: `temperature=0.1`,
`response_format={"type": "json_object"}`, no `seed`.

Behavioural proof: a stubbed response with usage and the same response without
usage produce an identical `ExtractedJobRequirements` (`model_dump()` equality),
while telemetry differs.

### Absence is recorded honestly

A missing `usage` object, or a missing individual field, yields `None` and
`available=False` — never `0`. A real zero would be indistinguishable from
unmeasured. Attempts that reported usage are summed, so retry consumption is
counted.

### No backfill

The 13 existing V3.3c run records carry no token fields. Historical token usage
is `UNAVAILABLE` and was not estimated into a measured value. Telemetry begins
with the next execution.

## Change B — Benchmark population reconciliation

Fully offline. No provider call. No extraction result altered. Frozen benchmark
not modified.

Artifacts: `docs/benchmark/v3_3_benchmark_reconciliation.{json,md}`

### Findings

The prior report claimed the discrepancy was 2 extra postings. It is **5**, and
the framing itself was the error:

```text
collected.json                28 postings  (VJ-B01..VJ-B28)
frozen benchmark              26 cases
  frozen regression cases      3   VJ-01..VJ-03  -- source text in dev DB, never in collected.json
  collected-backed cases      23   VJ-B01..B21, VJ-B23, VJ-B28
=> of the 28 collected postings, 23 are in the benchmark and 5 are excluded
```

The 5 excluded postings are **VJ-B22, VJ-B24, VJ-B25, VJ-B26, VJ-B27** — all
ClickUp. The build rule (`v3_benchmark_build.py:58-66`) keeps the first 2
postings per employer so one employer's ladder cannot dominate; ClickUp
contributed 7 collected postings and 2 were kept.

Reproducing that rule over `collected.json` file order **exactly** reproduces
the frozen benchmark's 23 collected-backed cases, with zero mismatches. The
benchmark is therefore internally consistent and not defective. It was left
unchanged.

Identity evidence (not ordering): 0 duplicate source URLs across all 28 postings;
1 duplicate posting-text hash pair — `VJ-B05` / `VJ-B07`, same employer, two
different URLs. Both are distinct benchmark cases, so this is a source-side
duplicate listing, not a benchmark defect. All 5 exclusions are
`identity_class = DISTINCT`.

### Population alignment defect

The harness selects postings **by index** into `collected.json`, not by
benchmark membership:

```text
in the default --to 26 window but NOT in benchmark : VJ-B22, VJ-B24, VJ-B25, VJ-B26
in the benchmark but NOT in the default window      : VJ-01, VJ-02, VJ-03, VJ-B28
```

Consequences: the default window would spend 12 calls extracting 4 postings that
are not benchmark cases, and would never extract `VJ-B28`, which is a benchmark
case sitting at index 27. `VJ-01..VJ-03` have no source text in
`collected.json` at all — their descriptions exist only in the dev DB, and no
artifact records a description hash for them, so their provenance against the
frozen benchmark build cannot be proven offline.

The completed work is unaffected: all 4 complete triplets (`VJ-B01..B04`) are
inside the benchmark. No quota has been spent outside it under V3.3.

The analysis layer was already correctly scoped — the 26-row stability table
enumerates the benchmark population exactly and marks `VJ-01..03` and `VJ-B28`
`NOT_RUN` / `NOT_MEASURABLE`.

Population selection was **not** changed, because choosing it is the
governance decision itself, not an instrumentation fix.

## Regression gate

```text
previous baseline : 405/405 PASS, 0 skipped, ruff clean
new total         : 413/413 PASS, 0 failures, 0 errors, 0 skipped
ruff check apps packages tests : All checks passed
```

The 8 added tests are the telemetry contract tests.

## Gate status

```text
BLOCKED -- BENCHMARK RECONCILIATION
```

Telemetry instrumentation is complete and verified. Extraction may not resume
until benchmark governance rules on two points:

1. whether the experiment population is the benchmark's 26 cases or the first 26
   collected postings — the 4-job difference decides whether 12 calls are spent
   on non-benchmark data and whether `VJ-B28` is ever run;
2. whether `VJ-01..VJ-03` may be sourced from the dev DB, given that no
   artifact records the description hash used at benchmark build time.

Against the benchmark population the remaining requirement is **66 calls over 22
jobs** (19 jobs with available source text = 57 calls; 3 unrunnable = 9 calls).