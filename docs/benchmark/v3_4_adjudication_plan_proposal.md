# §11 Semantic-Adjudication Plan — PROPOSED, APPROVAL-READY, NOT APPROVED

**Document type:** proposal. **Status: PROPOSED — APPROVAL-READY. NOT APPROVED.**
**Authority to execute:** none. Recording policy decisions does **not** authorize
adjudication, and does **not** constitute approval of this plan.

**Governing specification:** `docs/benchmark/v3_4_corrective_engineering_specification.md`
`v3.4-spec-r3.4`, 109,085 bytes, sha256
`ed299934216d7e5c3f22a513f9df374ef142cbe5fdf76073d7841b88a9c2cd38` — read only,
**unmodified** by this stage.

**Revision:** Stage 8 — corrections **C-1** (R1/R4 eligibility relationship) and
**B-1** (§6A terminal states, **OD-5**) applied; owner-directed. Gate 2 remains
**NOT APPROVED** pending a fresh independent readiness review. See
`docs/benchmark/v3_4_owner_decision_register.md`.

**This document does not modify the governing specification.** Any specification
change it identifies is assigned to a future task (§10). OD-1 is a
**campaign-specific protocol exception** for this adjudication campaign only; it
does **not** amend, override, or reinterpret the governing specification
generally (§0.1).

---

## 0. Governing gates

These gates are **separate and sequential**. Passing one never implies the next.

| # | gate | state |
| --- | --- | --- |
| 1 | Decision and plan documentation | **DONE** |
| 2 | Final plan review and explicit approval | **NOT MET** — **now approvable**; no approval-blocking question remains open (§11) |
| 3 | Separate explicit authorization for human adjudication | **NOT MET** — prerequisites in §11.1 |
| 4 | Audit of adjudication results | not reached |
| 5 | Separate owner decision on A4 | not reached |
| 6 | Separate specification amendment if A4 is adopted | not reached |
| 7 | Separate D7 authorization for engine-side consequences | not reached |

**Plan approval is NOT claimed and is NOT granted by this revision.** What has
changed is that gate 2 is now *reached*: OD-1, OD-2 and OD-3 are recorded, so no
approval-blocking question remains open. Approval remains a separate owner act.
**Being approval-ready does not authorize adjudication** — that is gate 3, and it
requires reviewer identities (OD-3) and separately authorized implementation
(B-7).

### 0.1 Campaign-specific exception (OD-1) — scope and limits

This plan adopts a **campaign-specific** interpretation of §11's review unit:
R1–R3 per occurrence, R4 per explicit pair.

| limit | statement |
| --- | --- |
| **Does not amend the specification** | The governing specification is unmodified. OD-1 is a documented protocol exception for **this campaign only**. |
| **Does not override generally** | It settles no question of §11.1's construction beyond this campaign's packet format. It creates no precedent binding on future work. |
| **Does not resolve §11.1** | The "pair" (L1306) versus "item" (L1320/L1334/L1339) conflict remains **an open specification inconsistency** (§10 item 3). |
| **Tracked as future work** | Formal specification reconciliation is added to the future work register (§10.3). |
| **Revocable** | If reconciliation resolves against the hybrid, this exception is withdrawn and the protocol reverts. |

## 0.2 Owner decisions recorded in this stage

| decision | records | effect |
| --- | --- | --- |
| **OD-1** | review unit — campaign-specific hybrid (R1–R3 occurrence, R4 pair) | §6.1, §6.2 |
| **OD-2** | quotation correspondence — C1/C2/C3; **C2 and C3 excluded from R1 submission**; R4 pairing is a separate determination | §4.2, §6.2, §6.4, §6.9 |
| **OD-4** | R4 pair-generation algorithm — single deterministic rule; corrected at Stage 8 that two C2 members sit in eligible groups | §6.2, register |
| **OD-5** | §6A terminal states — `INCOMPLETE`/`ESCALATED` terminal, no revival | §6A.1 T-1…T-6 |
| **OD-3** | reviewer identities deferred to gate 3; two reviewers + third adjudicator required | §9 |

**Reconciled denominators under OD-2** — fully reconciled, and M7 itself is not
redefined:

```text
415 corpus occurrences
 = 250 no quotation available (D-7, structurally non-adjudicable)
 + 165 candidates carrying a quotation
       = 8 C2 excluded (OD-2) + 1 C3 excluded (OD-2) + 156 C1 SUBMITTED
```

| quantity | value |
| --- | --- |
| corpus occurrences | **415** |
| no quotation available (D-7) | **250** |
| candidates carrying a quotation | **165** |
| excluded from R1 submission (OD-2) | **9** (8 C2 + 1 C3) |
| **submitted — M7 denominator** | **156** |
| adjudication coverage vs corpus | **156 / 415 = 37.6%** |
| adjudication coverage vs candidates | **156 / 165 = 94.5%** |

**Note on a coincidental equality.** M11-C1 (156/415) and adjudication coverage
(156/415) are both **37.6%** because the same 156 occurrences are byte-exact and
submittable. They are **different quantities** — one is evidence coverage, the
other adjudication coverage — and must be reported under their own names and
never merged.

## 1. Historical baseline limitation — binding on every finding

**Owner decision D-0, option (a) — historical V3.3 baseline first.** The review
corpus is the V3.3 experiment; the corrected-contract diagnostic is **not** part
of this stage.

> Every measurement in this plan was produced from the **V3.3 experiment**:
> `contract_version: v3.3`, `schema_version: ExtractedJobRequirements@2`,
> provider `openai/gpt-oss-120b`, temperature 0.1, no seed, system-prompt sha256
> `43d20b8be806e7ba` — the **frozen historical prompt and schema**.

**No finding in this plan validates the corrected extraction contract.** The
corrected-contract diagnostic defined by specification §10 **has not been run**
(§10.6). The corpus available to adjudicate is output from the contract the
specification exists to correct. Results are a **historical baseline only**.

Per §10.5, results from these eight postings *"cannot establish benchmark-wide
reproducibility or correctness."* No rate, proportion or "pass" claim may be
extrapolated to the 26-case benchmark.

**Corrected-contract diagnostic execution requires separate authorization**
(§10.6) and is **not** requested, planned, or implied by this document.

## 2. Corpus actually available (measured, read-only)

All figures were computed by reading existing artifacts. Nothing was
regenerated, reconstructed, or inferred. The correspondence measurement is a
**deterministic pre-check, not adjudication**.

| # | posting | frozen bytes source | `source_sha256` verified | run records | successful |
| --- | --- | --- | --- | --- | --- |
| 1 | `VJ-B04` | `validation_jobs/postings/collected.json` | **YES** `982d5a335f15d9ae…` | 3 | 3 |
| 2 | `VJ-B11` | `collected.json` | **YES** `6120e2e3d934406c…` | 3 | 3 |
| 3 | `VJ-B14` | `collected.json` | **YES** `277139ad608c92e5…` | 4 | 3 (+1 preserved `EXTRACTION_FAILED`) |
| 4 | `VJ-B20` | `collected.json` | **YES** `9f0554d857973cf8…` | 3 | 3 |
| 5 | `VJ-B23` | `collected.json` | **YES** `96eeed2bc4e7fe3a…` | 3 | 3 |
| 6 | `VJ-B28` | `collected.json` | **YES** `b2d58a93f3b8486e…` | 3 | 3 |
| 7 | `VJ-02` | `validation_jobs/VJ-02_job2.json` | **YES** `a88b8bb9254710b9…` | 3 | 3 |
| 8 | `VJ-03` | `validation_jobs/VJ-03_job3.json` | **YES** `45fb6961c84e22c6…` | 3 | 3 |

All eight hashes recomputed **byte-exactly** from existing artifacts and match the
ledger; character counts match `source_chars`. `VJ-02`/`VJ-03` provenance is
independently `VERIFIED` in `v3_3_frozen_provenance.json` (3/3 verified, 0
unresolved).

**Heterogeneous source, recorded.** Six postings resolve from `collected.json`;
`VJ-02` and `VJ-03` resolve **only** from archived captures — they are absent
from `collected.json` *and* from `blind_review_pack_v3.json`. The packet builder
must record which source file supplied each posting. This is a property of the
existing corpus, not a defect introduced here.

## 3. Requirement occurrence inventory (measured)

Ledger `v3_3c_extraction_reproducibility_runs.json`, 81 records, sha256 prefix
`6f8f6a1ee5f54acb`.

| posting | occurrences | `source_text` present | blank | carries a quote |
| --- | --- | --- | --- | --- |
| `VJ-B04` | 58 | 58 | 23 | 35 |
| `VJ-B11` | 64 | 64 | 43 | 21 |
| `VJ-B14` | 88 | 88 | 58 | 30 |
| `VJ-B20` | 23 | 23 | 19 | 4 |
| `VJ-B23` | 35 | 35 | 16 | 19 |
| `VJ-B28` | 54 | 54 | 38 | 16 |
| `VJ-02` | 60 | 60 | 38 | 22 |
| `VJ-03` | 33 | 33 | 15 | 18 |
| **total** | **415** | **415** | **250** | **165** |

## 4. The two decisive measurements

### 4.1 All 250 blank quotations are `SKILL` — 100%

| type | occurrences | blank `source_text` |
| --- | --- | --- |
| `SKILL` | 250 | **250 (100.0%)** |
| `EXPERIENCE` | 82 | 0 |
| `OTHER` | 67 | 0 |
| `LOCATION` | 9 | 0 |
| `EDUCATION` | 7 | 0 |
| **total** | **415** | **250 (60.2%)** |

This reproduces finding **V-1** on historical V3.3 output.

**Missing evidence is not evidence of absence.** 250 of 415 occurrences (60.2%)
are structurally non-adjudicable: §11.1's R1 question — *"does the quote entail
the requirement as stated?"* — cannot be asked of them, because no quote exists.
A blank quotation is **not** `NOT_SUPPORTED` and must never be recorded as a
reviewer judgment. Handled by decision **D-7** (§6.7).

**The candidate pool is 165 occurrences, not 415.** Of those, **156 are
submitted** to R1 under OD-2; 9 (C2 + C3) are excluded from submission but
**retained and reported** (§6.4).

### 4.2 Three correspondence classes, measured and kept separate

Specification §5.2 defines `EVIDENCE_VERIFIED` as *"a deterministic
substring/offset match against the posting bytes"* — a **byte-exact** test.

| class | definition | count | share of 165 | R1 submission (OD-2) |
| --- | --- | --- | --- | --- |
| **C1 byte-exact** | `source_text` occurs verbatim in the frozen posting bytes | **156** | 94.5% | **SUBMITTED** |
| **C2 dash-normalised** | occurs only after the explicit Unicode normalisation of §6.4 | **8** | 4.8% | **EXCLUDED** — retained, reported |
| **C3 truncated-prefix / unresolved** | no occurrence after normalisation | **1** | 0.6% | **EXCLUDED** — retained, reported |
| | | **165** | 100% | **156 submitted** |

* **C2 cause, precisely identified.** The model emitted **U+2011 NON-BREAKING
  HYPHEN** and **U+2010 HYPHEN** where the posting has **U+002D HYPHEN-MINUS**:
  `hands‑on`, `in‑person`, `ex‑founder`, `remote‑first`, `large‑scale`,
  `top‑level`. Pairwise similarity 0.963–0.993. **Encoding is not stable across
  runs** — `VJ-B23` run2 emits `remote‑first` (U+2011) and run3 emits
  `remote-first` (U+002D) for the same requirement text.
* **C3 case** (`VJ-B14` run2 ordinal 7) is a genuine **prefix** of a longer
  posting sentence, cut at a period that does not exist in the posting.
  Similarity 0.994.
* **Zero** quotations lack a plausible source passage.

**Nothing is fabricated to close a class.** C3 is not auto-accepted. C2 is not
promoted to `EVIDENCE_VERIFIED`. See §6.4.

## 5. Missing material — recorded, never reconstructed

| field | status |
| --- | --- |
| `evidence_state` | **ABSENT** — V3.3 predates the contract defining it |
| offsets (`start`/`end`) | **ABSENT** — never recorded by the V3.3 harness |
| per-requirement `Provenance` | **ABSENT** — run-level only |
| `raw_extraction`, `coerced_extraction` | present for 21 of 24 successful runs; **absent for all 3 `VJ-B04` runs** |

1. **No offsets exist.** §5.6 criterion 4 requires *"Offsets resolve for every
   `EVIDENCE_VERIFIED` quote"* — unsatisfiable on this corpus as it stands.
2. **`VJ-B04` raw/coerced payloads are permanently absent** (recorded D8
   limitation). `VJ-B04` canonical requirement lists with `source_text` survive
   in all three runs, so reviewers have material; but `VJ-B04` **cannot be traced
   to raw model output**, and any claim about its raw extraction is
   unreconstructable. This limitation must remain visible in every report.

**No quotation, offset, provenance value, or reviewer judgment is fabricated,
guessed, or back-filled anywhere in this plan.** Where material is absent it is
recorded as absent, and §5.6 criterion 4's *"ambiguity is flagged, never
guessed"* is treated as binding.

## 6. Protocol under the recorded decisions

### 6.1 Review unit — OD-1: campaign-specific documented hybrid

**OD-1 selection, restated.** **R1–R3:** occurrence-level assessment. **R4:**
explicit obligation-pair assessment carrying both occurrences' provenance. **No
self-pairs; no arbitrary pair construction.** Approved as a **campaign-specific,
revocable protocol exception** (§0.1) — it does not amend the governing
specification generally, and §11.1's wording conflict remains open (FW-1).

**R1, R2, R3 — assessed per individual requirement occurrence**, keyed
`(job_id, run_id, ordinal)`, verified unique across all 415.

**R4 — assessed per explicitly constructed requirement pair**, defined below.

**Reconciliation with §11.1 — partial, and the residue is flagged not resolved.**
§11 contains **inconsistent unit wording**:

| line | wording |
| --- | --- |
| L1306 (§11.1) | *"For each requirement **pair** presented for review…"* |
| L1314 (§11.1 R4) | *"do these **two items** impose materially different obligations"* |
| L1320 (§11.2) | *"Two reviewers independently review every **item**…"* |
| L1334 (§11.3 r4) | *"`UNRESOLVED` **items** are reported as `UNADJUDICATED`"* |
| L1339 (§11.4) | *"**Per item**: both initial judgments, the adjudication if any…"* |

Four of the five unit references say **item**, including §11.4's audit-trail
requirement. The hybrid is **consistent with §11.2, §11.3 and §11.4** and with
§11.1's own R4 wording. **§11.1's opening sentence is not reconciled**: it
describes a single uniform unit for all four dimensions, whereas the hybrid
splits the unit by dimension.

**This is recorded as an open specification-consistency item (§10, item 3),
assigned to a future specification task. It is not claimed resolved.** Under
**OD-1** it is handled as a documented **campaign-specific protocol exception**
(§0.1) — not as a resolution. If the owner judges §11.1 binding on the unit, the
hybrid is withdrawn and the workload, packet format and reporting all change.

### 6.2 R4 pair construction — single algorithm (Stage 6 correction)

Corrected at Stage 6 to remove four mutually inconsistent readings. **This is the
only pair-generation rule in this plan.** Any other statement anywhere in this
document or the register that appears to describe pair generation defers to this
section.

**Withdrawn language.** The earlier rules — "consecutive run pairs in ascending
run order", "enumerated lexicographically by ordinal", and the worked example
"a 3-run name-group yields 3 pairs" under a consecutive-run rule — are
**withdrawn as inconsistent** and must not be used. This section implements
**OD-4** in the owner decision register.

#### Inputs

| term | definition |
| --- | --- |
| **occurrence key** | `(job_id, run_id, ordinal)` — stable identity, §6.1 |
| **normalized name** | `identity[0]` of the occurrence as stored in the frozen ledger |
| **name group** | all quote-bearing occurrences sharing `(job_id, identity[0])` |
| **quote-bearing** | `source_text` present and non-blank (R4-A; the 250 blank occurrences are excluded) |
| **documented run order** | ascending `run_id` |

#### Algorithm

```text
for each name group G:                              # keyed (job_id, identity[0])
    members = sort G by (run_id, ordinal)          # 4: documented order
    if count(distinct run_id in members) < 2:      # 8
        emit no pair; record NO_ELIGIBLE_PARTNER with the reason
        continue
    for every unordered pair (a, b) of distinct members:   # 2
        if a.run_id == b.run_id: continue           # 3: no same-run pairs
        emit pair id = "R4|"+a.key+"|"+b.key       # 6: stable, deterministic
        record both members' complete provenance   # 5 (also R4-E)
```

Ordered lexicographically by the sorted member keys, so the emitted sequence is
byte-reproducible. Self-pairs are structurally impossible: members are distinct
and no member pairs with itself (R4-B). Same-run pairs are excluded at step 3,
which is stricter than R4-B and is retained.

#### Edge cases — all defined

| case | behaviour |
| --- | --- |
| **empty group** (no quote-bearing occurrence) | not a group; nothing emitted |
| **single-occurrence group** | no pair; `NO_ELIGIBLE_PARTNER` recorded |
| **group with one distinct run** (e.g. two occurrences in run 1) | no pair; `NO_ELIGIBLE_PARTNER` recorded |
| **duplicate occurrences within one run** | the within-run combination is **excluded** (step 3); cross-run combinations are all generated |
| **multi-run group with several occurrences per run** | **every** cross-run combination is generated (full cross-product across distinct runs) |
| **three runs, one occurrence each** | **3 pairs** — `(1,2)`, `(1,3)`, `(2,3)` |

#### Worked examples — algorithmic, verified by execution

These illustrate the algorithm. They are **not** corpus measurements.

```text
members = [(run 1, ord 0), (run 2, ord 0), (run 3, ord 0)]
  -> 3 pairs: (1,0)-(2,0), (1,0)-(3,0), (2,0)-(3,0)

members = [(run 1, ord 0), (run 1, ord 1), (run 2, ord 0)]
  -> 2 pairs: (1,0)-(2,0), (1,1)-(2,0)
     the same-run pair (1,0)-(1,1) is excluded by step 3

members = [(run 1, ord 0), (run 1, ord 1)]
  -> 0 pairs; NO_ELIGIBLE_PARTNER (only one distinct run)
```

#### Independence of pair verdicts

An R4 verdict attaches **only** to the pair that was reviewed. A verdict on one
pair is **never** inferred, copied, or propagated to another pair, even when the
pairs share a member. Every required pair is independently reviewable, and every
pair receives its own audit record. One occurrence may therefore hold several R4
verdicts, one per pair it belongs to; these are recorded separately and are **not**
merged.

#### No defensible partner

Where a group yields no pair, R4 is recorded
`UNSURE — NO_ELIGIBLE_PARTNER under the §6.2 algorithm`, which §11.1 permits
because *"`UNSURE` is a first-class verdict. It is never coerced into a binary."*
**No comparison partner is invented.** Such occurrences still receive full R1–R3
assessment, and §8.2's `merged_occurrences` principle is honoured: no occurrence
is consumed by pairing.

**This case is expected, not exceptional.** Measured read-only from the frozen
ledger, the algorithm yields **50 pairs across 72 occurrences** from **31 eligible
name groups** (VJ-B04 21 · VJ-B14 9 · VJ-02 7 · VJ-03 6 · VJ-B11 3 ·
VJ-B23 3 · VJ-B20 1). Of the **165 quote-bearing candidate occurrences**, **93
receive no R4 pair** and must each carry `UNSURE — NO_ELIGIBLE_PARTNER`. All 93
remain **reportable and counted** (AC-14d); none is dropped.

> **Population note — corrected at Stage 8.** These 50 pairs span the **165
> quote-bearing candidate** occurrences, **not** the **156 C1 submitted** set.
> The two populations differ, and **two C2 occurrences do sit in R4-eligible
> groups** (see the governing distinction below). An earlier revision of this note
> stated that no excluded C2/C3 occurrence fell in an eligible group; **that
> statement was false** and is withdrawn. The R1 submission population is
> unchanged at 156, but **not** for the reason previously given — see below.

#### Governing distinction — R1 submission eligibility vs R4 pairing eligibility (Stage 8)

**R1 submission eligibility and R4 pairing eligibility are independent tests.**
Conflating them is the error this section exists to prevent.

| | governed by | population | basis |
| --- | --- | --- | --- |
| **R1 submission** | **OD-2** | **156 C1 occurrences** | `evidence_state` correspondence class: only C1 is submitted |
| **R4 pairing** | the §6.2 algorithm + **R4-A** | **50 pairs across 72 occurrences** from 165 candidates | quote-bearing members (§6.2 definition) |

Consequences, all binding:

* **An occurrence excluded from R1 submission is not automatically excluded from
  R4 pairing.** R1 asks whether a *quotation* entails a claim; R4 asks whether two
  items impose *materially different obligations*. These are different questions
  with different evidence requirements.
* **Two C2 occurrences therefore receive R4 judgments** as members of eligible
  cross-run pairs:

  | occurrence | class | R1 submission | R4 pairs |
  | --- | --- | --- | --- |
  | `VJ-B04` run 1, ordinal 2 | **C2** | **not submitted** | member of eligible pairs |
  | `VJ-B23` run 2, ordinal 5 | **C2** | **not submitted** | member of an eligible pair |

* **R4 judgments do not convert a C2 occurrence into C1**, do **not** make it
  eligible for R1 submission, and do **not** alter its evidence status or its
  recorded exclusion reason. C2 remains C2.
* **R4 pairing does not add, remove, or re-derive any R1 submission.** The 156
  R1 submissions are determined solely by OD-2 and are unaffected by pairing.
* **Zero blank-quotation occurrences enter any R4 pair**, consistent with R4-A.
  Verified: 250 blank occurrences, 0 inside any pair.

**Why the 156 is unchanged — stated correctly.** Not because C2/C3 are absent
from R4 groups (they are not), but because **R1 submission eligibility and R4
pairing eligibility are separate determinations that never re-derive one
another.**

#### Population arithmetic (corrected, Stage 8)

| quantity | value |
| --- | --- |
| Total occurrences | **415** |
| No-quotation occurrences | **250** |
| Quote-bearing candidates | **165** |
| C2 occurrences excluded from R1 submission | **8** |
| C3 occurrences excluded from R1 submission | **1** |
| **C1 occurrences submitted for R1** | **156** |
| **R1 submission population** | **156** (unchanged) |
| R1 candidate coverage | **156 / 165 = 94.5%** |
| Corpus coverage by the R1 submission population | **156 / 415 = 37.6%** |

R4 counts are unchanged and were re-verified at Stage 8: **31 eligible groups ·
50 pairs · 72 covered occurrences · 165 candidates · 93 without an eligible R4
partner.**

#### Verifying the algorithm

A read-only reference implementation, executed against the frozen ledger:

```python
import itertools
def r4_pairs(members):
    """members: [(run_id, ordinal), ...] for one (job_id, identity[0]) group."""
    if len({run for run, _ in members}) < 2:      # step 8
        return []                                  # NO_ELIGIBLE_PARTNER
    out = []
    for a, b in itertools.combinations(sorted(members), 2):   # steps 2, 4
        if a[0] == b[0]:                           # step 3
            continue
        out.append((a, b))                         # steps 5, 6
    return out
```

`combinations` over sorted members yields each unordered pair once, so no
duplicate pair can be emitted; the sorted input fixes lexicographic order.

#### Campaign limits preserved

R4-A through R4-E remain in force; the algorithm implements rather than replaces
them. This remains a **campaign-specific protocol exception under OD-1** (§0.1) —
revocable, and **not** an amendment to the governing specification. §11.1's
"pair"/"item" inconsistency remains disclosed as **FW-1**.

### 6.3 Blinding — D-2

During the independent review pass, reviewers **must not** see:

* `score`, `overall_score`, or any component score;
* `recommendation` (APPLY / APPLY_WITH_TAILORING / STRETCH / SKIP);
* `blocker_count` or any blocker detail;
* run-to-run agreement or disagreement counts;
* the **candidate profile**;
* **each other's initial judgments** (§11.2 — unchanged).

The packet presents only: frozen posting bytes, the requirement as extracted
(`name`, `type`, `importance_model`, `category`), the quoted passage, offsets if
and only if authorised (§6.4), and the correspondence class (§4.2).

§11.4's audit trail is fully satisfiable without any score. §11.2's questions
concern the posting, not the candidate, so excluding the profile loses nothing
the rubric requires.

### 6.4 Correspondence and offsets — D-6

**Three classes recorded separately and never merged** (C1/C2/C3, §4.2).

**The normalisation rule, fixed before any packet is built:**

1. Unicode NFKC normalisation of the query string and of the posting.
2. Map **U+2010, U+2011, U+2012, U+2013, U+2014, U+2212** to **U+002D**.
3. Collapse runs of whitespace to a single space; strip leading/trailing space.
4. Case-fold.

**Labelling rule — binding:**

| class | may be labelled `EVIDENCE_VERIFIED`? | submitted to R1 (OD-2)? |
| --- | --- | --- |
| **C1 byte-exact** | **Yes**, under §5.2's existing exact-correspondence rule | **YES — 156 submitted** |
| **C2 dash-normalised** | **No.** §5.2's rule is exact correspondence; a normalised match does **not** satisfy it. C2 is recorded in its own class and **must not** be relabelled `EVIDENCE_VERIFIED` unless a **separately approved specification change** permits it | **NO — excluded**, reason `CORRESPONDENCE_NORMALISED_NOT_EXACT` |
| **C3 truncated-prefix / unresolved** | **No.** Not automatically accepted. C3 items are flagged for owner disposition, not auto-classified | **NO — excluded**, reason `CORRESPONDENCE_UNRESOLVED_TRUNCATED_PREFIX` |

**OD-2 — exclusion from R1 submission.** C2 and C3 are excluded from R1
quote-entailment review **under this campaign's protocol**, because neither is
`EVIDENCE_VERIFIED` under §5.2 and R1 asks whether *the quote* entails the
requirement. This exclusion is a **reporting and submission decision only**. It
does **not** reclassify either class, does **not** assert `NOT_SUPPORTED`, does
**not** alter §5.2, and does **not** assert that the underlying claims are false.
If the governing specification is separately amended, they may return to
submission; until then they are out.

**Every occurrence is retained.** All 9 excluded occurrences are retained with
their `source_text`, correspondence class, exclusion reason, and occurrence
provenance, remain queryable, and are reported in full. Exclusion is **never**
deletion, silent omission, or a downgrade (§5.2.2, §5.2.1 rule 4).

The original `source_text` is **preserved verbatim** in every record regardless of
class; normalisation is applied only to the comparison, never to the stored text.

**Offsets — deterministic mapping or flag.** Offsets are computed **only** where
deterministic:

* **C1** — byte/character offsets into the **original, unmodified** frozen
  posting bytes, recorded as `[start, end)` plus the posting sha256 they refer to.
* **C2** — a normalised match **has no unambiguous offset in the original bytes**,
  because the matched text differs by codepoint. **No offset is invented.** The
  item is flagged `OFFSET_UNRESOLVED_NORMALISED` with the normalisation rule
  named, per §5.6 criterion 4 (*"ambiguity is flagged, never guessed"*).
* **C3** — no offset; flagged `OFFSET_UNRESOLVED_PREFIX`.

Every computed offset must be **verified by round-trip**: slicing the original
frozen bytes at `[start, end)` must reproduce `source_text` byte-for-byte. Any
offset failing round-trip is discarded and the item flagged, never emitted.
Offsets are computed at packet-build time from frozen bytes and existing
`source_text`; this **reads** frozen artifacts and **writes only new files**.

### 6.5 Verdict mapping — D-3 (non-lossy)

| resolved R1 | stored `semantic_support` |
| --- | --- |
| `SUPPORTED` | `SUPPORTED` |
| `NOT_SUPPORTED` | `NOT_SUPPORTED` |
| `PARTIAL` | `PARTIAL` |
| `UNSURE` (resolved to `UNSURE`) | `UNSURE` |
| adjudication `UNRESOLVED`, or no settled judgment | `UNADJUDICATED` |
| never submitted (e.g. D-7) | `UNADJUDICATED`, with recorded reason |

**`UNSURE` versus `UNADJUDICATED` — the distinction this mapping preserves:**

* **`UNSURE` is a judgment.** §11.1: *"`UNSURE` is a first-class verdict. It is
  never coerced into a binary."* Reviewers looked and could not decide.
* **`UNADJUDICATED` is a state of the record.** §11.3 rule 4: `UNRESOLVED`
  *"never silently assigned the majority or the model's value."*

Collapsing them would destroy the ambiguity signal §11.4 requires be reported.
The mapping is **non-lossy**: every §11.1 verdict survives, and all four
reviewer dimensions plus the complete audit record are preserved unchanged.

### 6.6 Disagreement — D-4

Each dimension resolves **independently**, per §11.3.

* Both initial judgments are retained verbatim; neither is overwritten (§11.3 r1).
* Any dimension where the two differ — **including one `UNSURE` against one
  decided verdict** — goes to a third reviewer who sees both judgments and the
  source (§11.3 r2).
* The adjudicator records `AGREED` with the converged verdict, or `UNRESOLVED`
  (§11.3 r3).
* **R1 alone determines `semantic_support`.** R1 `UNRESOLVED` maps to
  `UNADJUDICATED` **regardless** of the resolution of R2, R3 or R4.
* **Agreement is never forced.** No tie-break by rank, seniority, or
  re-review-until-consistent.

This keeps the option (b) predicate single-valued and unambiguous.

### 6.7 Blank quotations — D-7

All **250** occurrences are **retained** as `semantic_support = UNADJUDICATED`
with machine-readable reason **`NO_QUOTATION_AVAILABLE`**.

* They are **not submitted** to quote-entailment review.
* They are **never** classified `NOT_SUPPORTED`.
* They never appear in any numerator, any "unsupported" count, or M7's
  denominator.
* They are **never deleted** — §5.2.2 and §5.2.1 rule 4 forbid deletion, silent
  omission, or downgrading importance.

### 6.8 Evidence linkage — per assessment

Each assessment references exactly the material actually shown:

`job_id` · `run_id` · occurrence ordinal · posting `source_sha256` (verified) ·
the source artifact file supplying the bytes · `name`, `type`,
`importance_model`, `category` **verbatim, never corrected** · `source_text`
verbatim (blank marked blank) · offsets or the applicable
`OFFSET_UNRESOLVED_*` flag · correspondence class (C1/C2/C3) · normalisation rule
named · rubric version · reviewer id · timestamp · confidence in {low, medium,
high} (§11.2).

§5.2.1 rule 2: `importance_model` and `category` are **never overwritten**.
§8.3's importance adjudication is a separate deterministic step and is **not**
part of this review.

### 6.9 Reporting — D-5, using the real §9.3 definitions

Per §9.3, verbatim:

| metric | numerator | denominator | missing data |
| --- | --- | --- | --- |
| **M7** | requirements **adjudicated supported** | requirements **submitted for adjudication** | unadjudicated reported `UNADJUDICATED` |
| **M11** | requirements in `EVIDENCE_VERIFIED` | **all canonical requirements** | reported always; D1 primary gate |

**Existing metric names are NOT redefined, renamed, or repurposed.** Coverage is
disclosed **alongside**, using counts and explicit denominators, as §11.5 already
requires (*"M7 and M8 report adjudication denominators explicitly"*).

**Mandatory disclosures:**

| disclosure | value |
| --- | --- |
| M7 | numerator / **156** submitted (**OD-2**; was 165 candidates, less 9 excluded) |
| **adjudication coverage** | **156 / 415 occurrences = 37.6%** — explicit count + denominator |
| candidates carrying a quotation | **165** |
| excluded from R1 submission (OD-2) | **9** — 8 `CORRESPONDENCE_NORMALISED_NOT_EXACT`, 1 `CORRESPONDENCE_UNRESOLVED_TRUNCATED_PREFIX`; each retained and individually listed |
| `NO_QUOTATION_AVAILABLE` (D-7) | **250**, reported separately; never in any numerator or M7 denominator |
| correspondence classes | C1 156 · C2 8 · C3 1, reported separately |
| disagreement rate | per §11.4, *"a measure of requirement ambiguity, not a defect"* |
| counts | by resolved verdict; `UNSURE`; `UNRESOLVED`; `OFFSET_UNRESOLVED_*` |

**Denominator reconciliation (OD-2) — all figures tie out.**

```text
415 corpus = 250 no-quotation (D-7) + 165 candidates
165 candidates = 9 excluded (OD-2) + 156 submitted
M7 denominator = 156
adjudication coverage = 156/415 = 37.6%  (and 156/165 = 94.5% of candidates)
```

**M7's coverage blind spot, disclosed not hidden.** M7's denominator is
self-selected (*"requirements submitted"*). With **156** of 415 submittable,
**M7 could read 100% while describing 37.6% of the corpus.** The coverage line
above is **mandatory in the same report block**; M7 is never published alone.
Widening M7's denominator would require a §9.3 amendment and is assigned to a
future task (§10 item 6), **not** done here.

**What M7 may and may not be used to claim.** M7 measures the semantic-support
rate **within the 156 adjudicated occurrences only**. It may support statements
about those 156 occurrences. It may **not** be used to state or imply
extraction quality, evidence coverage, requirement correctness, or any
benchmark-wide or corpus-wide rate — the 259 non-submitted occurrences (250
without quotation + 9 excluded) are outside its denominator by construction.

**M11's canonical population — settled explicitly.** §9.3 denominates M11 by
*"all canonical requirements"*. **Occurrences are not canonical identities and
are never silently equated with them.** Computing the true canonical population
on this corpus requires the §8.1/§8.2 identity rule — which is a **proposal,
not implemented** (§8.2 is marked *"PROPOSAL — not implemented"*) — and the V3.3
artifacts used the **old, defective** identity key that §8.1/V-3/V-4 exist to
correct (identity then included `type`). The specified denominator is therefore
**not computable on this corpus**.

Settlement: M11 is reported **deviation-flagged** over the **415 occurrences**,
with the flag stating explicitly that the denominator is the occurrence count and
**not** the specified canonical population; plus the computable sub-report
**M11-C1** = C1 / 415 = 156/415 = 37.6%, which needs no identity rule because it
counts correspondence classes on occurrences. Both are labelled; neither is
passed off as the specified metric.

**M10 remains unavailable.** §9.3: correctness is *"unavailable until labeling
occurs; no proxy may be substituted."* No correctness claim is made.

### 6.10 Aggregation — D-8

**Occurrence level is primary.** Secondary analyses: **posting level** (8 units,
the §10 unit) and **name-group level** (surfaces cross-run instability). Every
occurrence-level record is preserved with full provenance **even when canonical or
posting aggregation is reported**, honouring §8.2's requirement that merging
preserve one `Provenance` per occurrence.

## 6A. Incomplete, interrupted and conflicted reviews — operational procedure (Stage 6 correction)

Every state change below is an **append-only event**. Prior judgments are never
overwritten, corrected in place, or deleted. Corrections are new events that
reference prior ones.

### 6A.1 Case states

| state | meaning |
| --- | --- |
| `NOT_STARTED` | no judgment submitted |
| `IN_PROGRESS` | at least one judgment submitted, required judgments not all present |
| `COMPLETE_PENDING_RESOLUTION` | all required initial judgments present; disagreements (if any) awaiting adjudication |
| `ADJUDICATED` | resolved via §11.3 |
| `INCOMPLETE` | a required judgment is missing and could not be completed (§6A.3–6A.5) |
| `ESCALATED` | independence or blindness could not be guaranteed; escalated to the owner |

`INCOMPLETE` and `ESCALATED` are **terminal for the campaign** and always carry a
recorded reason. Neither is ever silently converted into a verdict.

#### Terminality (clarified at Stage 8)

| rule | statement |
| --- | --- |
| **T-1** | `INCOMPLETE` and `ESCALATED` are **terminal**. No transition leads out of either state — not to `IN_PROGRESS`, not to `COMPLETE_PENDING_RESOLUTION`, not to `ADJUDICATED`, not to any other state. |
| **T-2** | **No revival or reopening transition exists under this protocol.** A case already marked `INCOMPLETE` or `ESCALATED` **cannot be revived** merely because a reviewer later becomes available, or because the underlying obstacle is resolved. |
| **T-3** | A **replacement reviewer may be assigned only while the case is still active** — `NOT_STARTED`, `IN_PROGRESS`, or `COMPLETE_PENDING_RESOLUTION` — subject to the existing independence and blinding requirements (§6A.3). Assignment before terminality is a normal transition, not a revival. |
| **T-4** | If a case reaches terminality, it **stays terminal**. Any proposed exception requires a **separately recorded owner decision and a new protocol review**. It **must not** be implemented as an undocumented state transition, and **no `REOPENED` state is introduced**. |
| **T-5** | Terminality does **not** relax any preservation duty. All prior events and judgments remain **append-only** and readable: nothing is overwritten, deleted, or superseded by the act of sealing a case terminal. |
| **T-6** | A terminal case remains **fully reportable** in its terminal state with its recorded reason, and contributes to the unresolved counts required by §11.5. |

**Scope note.** This clarification resolves an ambiguity identified in the Stage 7
independent review, where §6A.2's phrase *"can never be obtained"* implied
recoverability while §6A.1 declared these states terminal. **T-1 through T-4
adopt terminality**; the phrase is read as *"no further judgment will be obtained
under this protocol."*

### 6A.2 Missing or incomplete judgments

1. A case with only **one** initial judgment is **not** complete independent
   review. It is `IN_PROGRESS`.
2. A missing judgment is **neither agreement nor disagreement**. §11.3 triggers on
   differing judgments; it must never be read as triggering on an absent one.
3. A case is **not advanced to adjudication** until both required initial
   judgments exist (§11.2).
4. The case is reported with an explicit reason (`MISSING_INITIAL_JUDGMENT`,
   naming which reviewer and which dimensions).
5. No occurrence or pair disappears: it remains in reporting with its state and
   reason.
6. A single judgment is **never** promoted to the case's verdict. If no further
   judgment will be obtained **under this protocol**, the case ends `INCOMPLETE`,
   and any dimension without a settled judgment stays `UNADJUDICATED`.
   `INCOMPLETE` is terminal — see §6A.1 T-1…T-4; the case is **not** reopened if
   a reviewer later becomes available.

### 6A.3 Reviewer withdrawal or non-response

| event | required action |
| --- | --- |
| `WITHDRAWAL_DECLARED` | record the withdrawal, timestamp, reason, and case; **all previously submitted judgments are preserved** |
| `NON_RESPONSE_AT_DEADLINE` | record the deadline, the non-responding reviewer, and the case |
| `REPLACEMENT_ASSIGNED` | record the replacement's identity, the independence declaration, and the timestamp |

* A replacement reviewer must satisfy the **same** independence requirements as
  the original (§11.2, §11.3 r2) and must complete the missing review **without
  seeing the other reviewer's judgment**.
* Blinding obligations apply to the replacement exactly as to the original.
* If an independent replacement cannot be obtained, or if blindness or independence
  **cannot be guaranteed**, the case is held `ESCALATED` — **completion is never
  fabricated**.

### 6A.4 Conflict of interest and recusal

1. Reviewers **disclose relevant conflicts before starting**; the disclosure is
   an audit event referenced by every judgment that reviewer submits.
2. **Recusal before assessment:** record `RECUSAL_DECLARED` (reviewer,
   dimension, reason, timestamp). The affected case is reassigned per §6A.3.
3. **Conflict discovered after submission:** the original judgment is
   **preserved verbatim** and flagged `JUDGMENT_CONTESTED` for an explicit
   validity decision. It is **never silently deleted or overwritten**. The
   validity decision is a separate append-only event; the superseded judgment
   remains readable and is marked superseded, not removed.
4. If no independent replacement can be obtained, the affected **dimension or
   case stays `UNADJUDICATED`** with the reason recorded. The dimension is not
   decided by the remaining reviewer alone.

### 6A.5 Interruption and resumption

| event | required action |
| --- | --- |
| `REVIEW_INTERRUPTED` | record interruption time, actor, case, and the last committed event id |
| `REVIEW_RESUMED` | record resumption time, actor, and the event id resumed from |

* The **last committed audit event** and all completed judgments are preserved.
* Resumption continues **from the last recorded state**, without overwriting or
  duplicating prior judgments.
* Partial and resumed reviews are **distinguishable in the audit trail**: every
  judgment carries the resumption event id under which it was produced.
* An interrupted review is **never treated as complete** because earlier steps
  were recorded. A case interrupted with only one judgment present is
  `IN_PROGRESS`, not `COMPLETE_PENDING_RESOLUTION`.
* Any reassignment during interruption is recorded as its own event (§6A.3).

### 6A.6 Append-only integrity

| requirement | statement |
| --- | --- |
| **Event log** | all state changes are append-only events; no in-place mutation |
| **Correction** | a new event referencing the corrected event id; the original remains readable |
| **Replacement reviewer** | new `REPLACEMENT_ASSIGNED` event; prior judgments untouched |
| **Recusal** | new `RECUSAL_DECLARED` event; prior judgments preserved |
| **Resumption** | new `REVIEW_RESUMED` event referencing the interruption |
| **Contested judgment** | preserved and flagged, superseded by an explicit decision, never removed |
| **Vocabulary** | `UNSURE` and `UNADJUDICATED` remain distinct (§6.5); **no new evidence state is invented** |
| **Visibility** | any case not completable under this procedure remains visibly unresolved with an explicit reason |

## 7. Audit trail — binding (D-3, D-4, OD-1, OD-2, OD-3, Stage 6)

Append-only, per §11.4, retaining for **every** occurrence and **every** pair:

both independent initial assessments · reviewer identifiers · timestamps · all
four rubric dimensions per assessment · free-text rationale quoting the posting ·
confidence in {low, medium, high} (§11.2) · third-reviewer adjudication and its
rationale · `AGREED` / `UNRESOLVED` status · stored `semantic_support` and the
mapping applied · correspondence class and normalisation rule · offsets or the
`OFFSET_UNRESOLVED_*` flag · frozen posting sha256 and source artifact file ·
rubric version · occurrence key and, for pairs, both member keys.

Nothing is ever overwritten or deleted (§11.3 r1, §5.2.2).

## 8. Scope

Exactly the eight §10 postings. **No expansion.** 24 successful runs
(§10.3's "3 runs per posting, 24 calls"), **415** corpus occurrences,
**250** without quotation (D-7), **165** candidates carrying a quotation,
**9** excluded from R1 submission (OD-2), **156** submitted, plus deterministic
R4 pairs derived from those **156**.

## 9. Reviewer identities — OD-3 (deferred to gate 3)

**Selected:** two independent reviewers and a third adjudicator, with identities
and **written independence declarations documented before any assessment begins**
(§11.2, §11.3 r2).

**OD-3 — identities are deferred to the execution gate.** The written protocol
may be approved at gate 2 without reviewer identities being supplied. This rests
on §11's own preamble (L1301): §11 *"does not authorize conducting reviews,
**recruiting reviewers**, assigning cases, or labeling data."* Reviewer supply is
outside §11's authority and therefore cannot be a precondition for approving a
protocol §11 defines as design-only.

**No recruitment is authorized by OD-3.** No reviewer or adjudicator has been
identified, contacted, engaged, or appointed; **no human reviewer has been
approached**; no reviewer identity exists. Independence cannot be declared for a
person who has not been named, so this remains an unmet **gate-3 prerequisite**
(§11.1).

**Requirements that bind when gate 3 is reached:** two reviewers must assess each
submitted occurrence **independently** with no visibility of each other's
judgments (§11.2); a third reviewer adjudicates disagreements (§11.3 r2); every
independence declaration is written, dated, and filed before the first assessment.

## 10. Known specification inconsistencies — recorded, NOT fixed here

The governing specification is **not modified** in this stage. Each item is
assigned to an explicit future task.

| # | inconsistency | evidence | assigned to |
| --- | --- | --- | --- |
| **1** | **`ExtractedRequirementV3` cannot express the A4 rule.** The §5.4 proposed schema has **no `semantic_support`, no `decision_eligible`, no `importance_adjudicated`** field — yet proposed option (b) reads `semantic_support` directly. The rule the specification recommends has nowhere to live. | §5.4 L736–758 vs §5.1.3 L420 | **Future specification amendment** (schema shape) — required before any implementation of option (b) |
| **2** | **`SEMANTIC_UNADJUDICATED` survives as a live name** despite r3.1 superseding it in the evidence-state table. | §5.6 c.5 L793; §17.1 c.9 L1512; vs supersession L634, L1794 | **Future specification amendment** — vocabulary alignment |
| **3** | **§11.1's "requirement pair" unit conflicts with §11.2/§11.3/§11.4's "item" unit.** The OD-1 hybrid is consistent with four references and unreconciled with one. **Not resolved** — handled as a campaign-specific exception (§0.1). | L1306 vs L1320, L1334, L1339 | **Future specification amendment** — formal reconciliation of §11.1 with §11.2–§11.4 (§10.3) |
| **4** | **M11's denominator is not computable** on this corpus (§8.1/§8.2 identity rule unimplemented; V3.3 used the defective key). Occurrence-based reporting proceeds with an explicit deviation flag (§6.9); the two populations are never equated. | §9.3 L1223 vs §8.2 L1104 | **Future specification or engineering task** — implement identity, then recompute |
| **5** | **§5.2's exact-correspondence rule excludes C2 matches** (8 occurrences) that are substantively verbatim. Under **OD-2** they are excluded from R1 submission, retained and reported; **§5.2 is unmodified**. | §5.2 L607–610 vs measurement §4.2 | **Future specification decision** — only if the owner later pursues a normalisation-aware state |
| **6** | **M7's self-selected denominator permits a coverage-blind 100%.** Under **OD-2** the denominator is fixed at 156 with mandatory coverage disclosure (§6.9); **M7 itself is not redefined**. | §9.3 L1219 vs §6.9 | **Future specification amendment** — denominator and coverage rule |

### 10.3 Future work register (OD-1 residual)

| id | task | gate | note |
| --- | --- | --- | --- |
| FW-1 | **Formally reconcile §11.1's review-unit wording with §11.2–§11.4.** Decide whether §11 adopts "item" as the unit (making the hybrid normative), or retains "pair" (requiring the hybrid to be withdrawn). | 6 | Raised by **OD-1**; the campaign exception (§0.1) expires when this is resolved |
| FW-2 | Amend §5.4 schema to carry `semantic_support`, `decision_eligible`, `importance_adjudicated` | 6 | Required only if option (b) is adopted (B-3) |
| FW-3 | Align `SEMANTIC_UNADJUDICATED` → `UNADJUDICATED` at §5.6 c.5 and §17.1 c.9 | 6 | B-8 |
| FW-4 | Amend §9.3 M7 denominator and coverage rule | 6 | B-9 |
| FW-5 | Implement §8.1/§8.2 identity rule, then recompute M11 | 6 + engineering | B-4 |

**FW-1 through FW-5 are not blockers to gate 2 or gate 3.** None requires the
campaign to stop. FW-1 becomes load-bearing only if reconciliation resolves
against the OD-1 exception.

## 11. Blockers and prerequisites

### 11.1 Blocker classification (reconciled at Stage 3/Stage 4)

The previous revision placed all nine items under "blockers to gate 2". A
Stage 3 audit against the governing specification found that heading
overstated: several items' own status text placed them at later gates. Corrected
classification:

| # | item | class | blocks | closure needs |
| --- | --- | --- | --- | --- |
| **B-1** | Reviewer/adjudicator identities, independence declarations | **execution (gate 3)** | gate 3 only | external people + owner |
| **B-2** | §11.1 "pair" vs §11.2–§11.4 "item" | **OD-1 recorded** | **nothing — RESOLVED for this campaign** by campaign exception (§0.1); inconsistency retained, reconciliation at FW-1 | spec task (gate 6) |
| **B-3** | §5.4 `ExtractedRequirementV3` lacks fields option (b) requires | **option (b) activation (gate 6)** | gate 6 — **not adjudication** | spec amendment |
| **B-4** | M11 canonical population not computable | **reporting limitation** | nothing — deviation-flagged (§6.9) | spec/engineering task |
| **B-5** | 8 C2 occurrences cannot be `EVIDENCE_VERIFIED` | **OD-2 recorded** | **nothing — RESOLVED**: excluded from submission, retained, reported | spec change only if later pursued |
| **B-6** | 1 C3 occurrence not auto-accepted | **OD-2 recorded** | **nothing — RESOLVED**: excluded from submission, retained, reported | spec change only if later pursued |
| **B-7** | Normalisation + offset round-trip not implemented/tested | **technical prerequisite** | **packet release (gate 3)** | separately authorized implementation |
| **B-8** | `SEMANTIC_UNADJUDICATED` vocabulary conflict | **technical prerequisite** | **gate 6** | spec amendment |
| **B-9** | M7 self-selected denominator | **reporting limitation** | nothing — §11.5 disclosure implemented (§6.9) | spec amendment (future) |

**No item remains that blocks plan approval.** OD-1, OD-2 and OD-3 are recorded
(§0.2). **Gate 2 is reachable and is not claimed met.**

### 11.2 Prerequisites for adjudication execution (gate 3) — NOT MET

Distinct from plan approval. All must hold **before** any assessment begins:

| # | prerequisite | status |
| --- | --- | --- |
| E-1 | Owner approval of this plan (gate 2) | **NOT MET** |
| E-2 | Separate explicit authorization for human adjudication (gate 3) | **NOT MET** |
| E-3 | Two independent reviewers and a third adjudicator named | **NOT MET** — none identified or engaged |
| E-4 | Written, dated independence declarations filed | **NOT MET** |
| E-5 | Normalisation + offset round-trip implemented **and tested** (B-7) | **NOT MET** |
| E-6 | Packet builder implemented; reads frozen artifacts, writes only new files | **NOT MET** |
| E-7 | Reporting template implements §9.3 as written, plus mandatory coverage and M11 deviation disclosure | **NOT MET** |
| E-8 | Blinding confirmed at packet level (no score, recommendation, blocker, component, run-to-run count, candidate profile) | **NOT MET** |
| E-9 | All eight posting hashes re-verified; confirmed no frozen artifact is written to | **NOT MET** |
| E-10 | R4 algorithm (§6.2) implemented; verified to emit only cross-run, distinct-member pairs, both members' provenance preserved, stable pair ids | **NOT MET** |
| E-11 | §6A procedure implemented as append-only events; every AC-14a–AC-14d transition demonstrably enforced | **NOT MET** |

### 11.3 Items scoped to later gates — deliberately not blockers here

| item | class | gate it belongs to |
| --- | --- | --- |
| **B-3** missing schema fields for option (b) | T | **6** — specification amendment |
| **B-8** `SEMANTIC_UNADJUDICATED` vocabulary | T | **6** — specification amendment |
| **B-9** M7 denominator rule | T | **6** — specification amendment (reporting disclosure suffices meanwhile) |
| **B-4** M11 canonical population | T/R | **6** / engineering — deviation flag suffices meanwhile |
| **§11.1 reconciliation** (OD-1 residual) | T | **6** — specification reconciliation |
| **U-1** output-token maximum | T | **1** — extraction stage, unrelated to adjudication |
| **U-2b** endpoint parameter semantics | T | **1** — extraction stage, unrelated to adjudication |
| **U-4** capability-vs-experience identity | T | **3** — canonicalisation stage; **`PROVISIONAL — NOT VALIDATED`, not promoted** |

**U-1, U-2b and U-4 do not block plan approval, execution, or results
acceptance.** None bears on reviewing frozen artifacts. U-4 remains provisional
and is **not** promoted to a validated finding: the frozen eight-posting set
contains 0/10 SKILL↔EXPERIENCE transition cases and cannot settle it.

## 12. Acceptance criteria

### 12.1 Before adjudication may begin (gate 3)

| # | criterion |
| --- | --- |
| AC-1 | Owner approval of this plan, recorded (gate 2) — **NOT YET GRANTED** |
| AC-2 | Separate explicit authorization to execute, distinct from approval (gate 3) |
| AC-3 | Two independent reviewers and one third adjudicator identified; independence declared **in writing** and dated before the first assessment (OD-3, E-3/E-4) |
| AC-4 | Packet builder implemented; **reads** frozen artifacts, **writes only new files** |
| AC-5 | Normalisation rule implemented **and tested**; offset round-trip verified (D-6, B-7, E-5) |
| AC-6 | OD-2 applied as recorded: 156 C1 submitted; 9 excluded with recorded reasons; all 415 retained |
| AC-7 | Verdict→`semantic_support` mapping fixed in writing before first assessment (D-3) |
| AC-8 | **Exactly one R4 pair-generation algorithm is specified** (§6.2) and **all R4 examples agree with it**; no self-pairs, no same-run pairs; every pair preserves both members' provenance. **Specified and internally consistent — verified at Stage 6. Not yet *implemented* (E-10).** |
| AC-8b | **Pair verdict independence:** no pair's verdict inferred or propagated to another pair; every required pair independently reviewable (§6.2) — specified, not yet implemented |
| AC-14a | **A missing initial judgment cannot trigger agreement, disagreement, or advancement to adjudication**; such a case is `IN_PROGRESS` or `INCOMPLETE` with a recorded reason (§6A.2) — specified, not yet implemented |
| AC-14b | **Withdrawal, non-response, conflict, recusal, interruption and resumption each have defined transitions and named audit events** (§6A.3–6A.5) — specified, not yet implemented |
| AC-14c | **No prior judgment is silently overwritten or deleted**; corrections, replacements, recusal and resumption are append-only events (§6A.6) — specified, not yet implemented |
| AC-14d | **Unresolved cases remain reportable and retain an explicit reason**; `UNSURE`/`UNADJUDICATED` distinction preserved; no new evidence state introduced (§6A.6) — specified, not yet implemented |
| AC-14e | **`INCOMPLETE` and `ESCALATED` are terminal:** no transition leaves either state, no revival or reopening exists, replacement may be assigned only while a case is active, and any exception requires a separately recorded owner decision and protocol review (§6A.1 T-1…T-6, OD-5); no `REOPENED` state exists — specified, not yet implemented |
| AC-9 | Reporting template implements §9.3 M7/M11 as written, with **M7 denominator 156**, plus mandatory coverage and M11 deviation disclosure (D-5, OD-2) |
| AC-10 | Blinding confirmed at packet level: no score, recommendation, blocker, component, run-to-run count, or candidate profile (D-2) |
| AC-11 | All eight posting hashes re-verified; confirmed no frozen artifact is written to |
| AC-12 | §10.5 diagnostic boundary and the §1 historical-baseline limitation stated in the report |
| AC-13 | All eleven execution prerequisites E-1…E-11 (§11.2) satisfied and evidenced |

### 12.2 Before results may inform a policy decision (gate 5)

| # | criterion |
| --- | --- |
| AC-14 | Both initial assessments exist for every submitted occurrence, persisted before comparison (§11.2, §11.3 r1) |
| AC-15 | Every disagreement adjudicated or recorded `UNRESOLVED`; none forced (§11.3) |
| AC-16 | M7, M11 (+ deviation flag and M11-C1), coverage, correspondence classes, disagreement rate, `UNSURE` and `UNRESOLVED` counts all reported with denominators; **M7 denominator is 156** and the 165/415/250/9/156 reconciliation is shown |
| AC-17 | **Zero** `NO_QUOTATION_AVAILABLE` (250) and **zero** OD-2-excluded (9) occurrences appear in any numerator, any "unsupported" count, or M7's denominator |
| AC-18 | Occurrence-level provenance intact; no occurrence dropped by pairing, exclusion, or aggregation; both pair members recorded; all 9 excluded occurrences individually listed with reasons |
| AC-19 | `importance_model` and `category` unaltered everywhere (§5.2.1 rule 2) |
| AC-20 | `VJ-B04` raw/coerced payload limitation stated in the report |
| AC-21 | Every finding labelled as V3.3 / `ExtractedJobRequirements@2` historical output; **no validation claim** for the corrected contract |
| AC-22 | No correctness claim; M10 recorded unavailable (§9.3) |
| AC-23 | **Option (b) still NOT activated.** Results inform a later owner decision; they do not make one (§5.1.4, §5.1.5, gate 5) |

## 13. Proposed A4 policy — status unchanged

Proposed rule, **NOT IN FORCE**:

```text
decision_eligible = (evidence_state == EVIDENCE_VERIFIED AND semantic_support == SUPPORTED)
```

**R-E1 remains the operative rule:** `decision_eligible = (evidence_state == EVIDENCE_VERIFIED)`.

Adjudication results **inform** a later owner decision (gate 5). They do **not**
activate option (b). Activating it requires, in order: gate 5 owner decision →
gate 6 specification amendment reconciling all seven items in §5.1.5, including
the missing schema fields (§10 item 1) → gate 7 separate D7 authorization for any
engine-side consequence. **None of gates 5–7 is authorized.**
