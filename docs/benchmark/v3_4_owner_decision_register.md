# Owner Decision Register — A4 / §11 Adjudication

**Document type:** decision register. **Revision:** owner decisions **OD-6,
OD-7, OD-8, OD-9** recorded (post-Gate-3-readiness). Gate 2 approval remains as
recorded in §13a. All earlier decisions — OD-1…OD-5 and D-0…D-9 — are retained in
full and unaltered.

**Governing specification:** `docs/benchmark/v3_4_corrective_engineering_specification.md`
`v3.4-spec-r3.4`, 109,085 bytes, sha256
`ed299934216d7e5c3f22a513f9df374ef142cbe5fdf76073d7841b88a9c2cd38` — read only,
**unmodified**.

**Companion:** `docs/benchmark/v3_4_adjudication_plan_proposal.md`
sha256 `2d1fb031c1eae12025fb5a81fdacd3cc30113de75925503b2983b05a37a077ef`.

**Gate 2 (plan approval) is APPROVED — §13a.** **This register still does not
authorize adjudication, Gate 3 execution, or policy activation.**

**Recording convention:**

| status | meaning |
| --- | --- |
| **OWNER-DIRECTED** | decision recorded by the owner; binding on this plan, **subject to** consistency with the governing specification |
| **OWNER-DIRECTED (OUTSTANDING)** | policy requirement recorded; an execution prerequisite remains unsatisfied |
| **CAMPAIGN EXCEPTION** | campaign-specific protocol exception; does **not** amend or override the specification generally |
| **OPEN** | not decided; blocks something |

---

## Stage 4 decisions — OD-1, OD-2, OD-3

| id | decision | selection | status | gate |
| --- | --- | --- | --- | --- |
| **OD-1** | review unit | campaign-specific hybrid: R1–R3 occurrence, R4 explicit obligation pair | **OWNER-DIRECTED / CAMPAIGN EXCEPTION** | 2 reached |
| **OD-2** | quotation correspondence | C1 submitted; C2 and C3 excluded from R1, retained and reported | **OWNER-DIRECTED** | 2 reached |
| **OD-3** | reviewer identities | deferred to execution gate; two reviewers + third adjudicator required before any assessment | **OWNER-DIRECTED** | 3 prerequisite |
| **OD-4** | R4 pair-generation algorithm | single deterministic algorithm; all cross-run distinct-member pairs; stable pair ids; verdict independence | **OWNER-DIRECTED / CAMPAIGN EXCEPTION** | 2 reached (specified); implementation E-10 |

**No decision in this stage authorizes adjudication.** Gate 2 is now *reachable*;
gate 3 remains **NOT MET**.

---

## OD-4 — R4 pair-generation algorithm · **OWNER-DIRECTED / CAMPAIGN EXCEPTION**

**Question.** Before this decision, §6.2 admitted four mutually inconsistent
readings of pair construction, producing 39, 41, 47 and 50 pairs respectively and
leaving 2 occurrences with an R4 verdict under only some readings. Stage 5
recorded this as an approval-blocking defect. **The withdrawn readings are quoted
here only as the historical defect; the strings "consecutive run pairs" and
"a 3-run name-group yields 3 pairs" appear in this document nowhere as a live
rule** — see the two explicit withdrawal notices below.

**Selection — one deterministic algorithm (campaign-specific).** For each name
group keyed `(job_id, identity[0])`:

1. use occurrence identity `(job_id, run_id, ordinal)`;
2. enumerate **every unordered pair of distinct occurrences whose `run_id`
   values differ**;
3. generate **no same-run pairs and no self-pairs**;
4. sort members by `(run_id, ordinal)` — the documented run order — and emit
   pairs lexicographically by sorted member keys;
5. store **both members' complete occurrence provenance** with each pair;
6. derive a **stable pair identifier** deterministically from the two member keys;
7. **never infer an R4 verdict from another pair's verdict** — every required
   pair is independently reviewable, `UNSURE` outcomes included;
8. if a group has **fewer than two distinct runs**, generate no pair and record
   the reason; **never invent a comparison partner**.

**Rationale.** The rule removes reading-dependence entirely: one algorithm, one
pair sequence, reproducible. It satisfies R4-D's demand for a "stated,
deterministic rule" and strengthens R4-E by mandating stable pair identity and
dual provenance.

**Compatibility confirmed against existing constraints before adoption:**

| constraint | disposition |
| --- | --- |
| **R4-A** quote-bearing only | **preserved** — groups built from non-blank `source_text`; the 250 blank occurrences stay excluded |
| **R4-B** distinct members | **preserved** — self-pairs structurally impossible |
| **R4-C** same posting | **preserved** — group key is `(job_id, identity[0])` |
| **R4-D** deterministic | **satisfied** |
| **R4-E** both members' provenance | **preserved and strengthened** (steps 5–6) |
| **OD-1** campaign exception | **unchanged** — still campaign-specific, revocable, does not amend the specification |
| **OD-2** C1/C2/C3 | **unchanged** — the 156-occurrence R1 submission population is untouched, because **R1 submission eligibility and R4 pairing eligibility are independent determinations that never re-derive one another** (not because C2/C3 are absent from R4 groups — two C2 occurrences *are* present there; corrected at Stage 8) |

**Scope and consequences.**

* **Campaign-specific.** Like OD-1, a protocol exception for this campaign only.
  **Revocable**, and it does **not** amend the governing specification. §11.1's
  "pair"/"item" inconsistency remains disclosed as **FW-1**.
* **Review workload.** Computed read-only from the frozen ledger, the algorithm
  yields **50 R4 pairs across 72 occurrences** from **31 eligible name groups**
  (VJ-B04 21 · VJ-B14 9 · VJ-02 7 · VJ-03 6 · VJ-B11 3 · VJ-B23 3 · VJ-B20 1).
  **This is a corpus measurement of the algorithm's output, not an invented
  figure.** It is *specified*, **not implemented and not executed** (E-10).
* **Population note (corrected at Stage 8).** These pairs span the **165
  quote-bearing candidate** occurrences, **not** the **156 C1 submitted** set.
  **Two C2 occurrences do sit in R4-eligible groups** and will hold R4 verdicts:
  `VJ-B04` run 1 ordinal 2, and `VJ-B23` run 2 ordinal 5. **An earlier revision of
  this note claimed no excluded C2/C3 occurrence fell in an eligible group; that
  claim was false and is withdrawn.** Neither population is affected in substance,
  and the reason is now stated correctly below.

### R1 submission eligibility vs R4 pairing eligibility (Stage 8, owner-directed)

**R4 participation is independent of R1 submission eligibility**, subject to the
existing R4-A requirement that an occurrence be quote-bearing. Both identified C2
occurrences are **retained** in R4-eligible groups. Neither the R4 pairing
algorithm nor OD-2's R1 submission population was changed.

| | governed by | population |
| --- | --- | --- |
| **R1 submission** | **OD-2** — only C1 is submitted | **156 C1 occurrences** |
| **R4 pairing** | the §6.2 algorithm + **R4-A** | **50 pairs across 72 occurrences** |

Binding consequences:

* An occurrence excluded from R1 submission is **not automatically excluded from
  R4 pairing**. R1 asks whether a *quotation* entails a claim; R4 asks whether two
  items impose *materially different obligations*.
* `VJ-B04` run 1 ordinal 2 (**C2**) and `VJ-B23` run 2 ordinal 5 (**C2**) may
  receive R4 judgments as members of eligible cross-run pairs.
* R4 judgments **do not** convert C2 to C1, **do not** make either occurrence
  eligible for R1 submission, and **do not** change its evidence status or its
  recorded exclusion reason.
* R4 pairing **does not add, remove, or re-derive** any R1 submission.
* **Zero** blank-quotation occurrences enter any R4 pair (R4-A), verified.

**Corrected population arithmetic:**

| quantity | value |
| --- | --- |
| Total occurrences | **415** |
| No-quotation occurrences | **250** |
| Quote-bearing candidates | **165** |
| C2 excluded from R1 submission | **8** |
| C3 excluded from R1 submission | **1** |
| **C1 submitted for R1** | **156** |
| **R1 submission population** | **156** — unchanged |
| R1 candidate coverage | **156 / 165 = 94.5%** |
| Corpus coverage | **156 / 415 = 37.6%** |

R4 counts unchanged and re-verified at Stage 8: **31 eligible groups · 50 pairs ·
72 covered occurrences · 165 candidates · 93 without an eligible R4 partner.**

**Nothing is executed by this decision.** No packet built, no pair assessed, no
reviewer contacted. Gate 3 prerequisites E-10 and E-11 remain **NOT MET**.

---

## OD-5 — Terminal states in §6A · **OWNER-DIRECTED**

**Question.** §6A.2 ended a case as `INCOMPLETE` only if the second judgment
*"can never be obtained"*, implying recoverability, while §6A.1 declared
`INCOMPLETE` and `ESCALATED` *"terminal for the campaign"*. `REPLACEMENT_ASSIGNED`
existed but **no revival path was defined**. Stage 7 recorded this as an
ambiguous transition condition.

**Selection — terminality adopted; no revival under this protocol.**

* `INCOMPLETE` and `ESCALATED` are **terminal**. No transition leads out of either
  state.
* **No revival or reopening transition is permitted.** A case already marked
  terminal **cannot be revived** merely because a reviewer later becomes available.
* A replacement reviewer may be assigned **only while the case is still active**
  (`NOT_STARTED`, `IN_PROGRESS`, `COMPLETE_PENDING_RESOLUTION`), subject to the
  existing independence and blinding requirements. This is a normal transition,
  **not** a revival.
* Any proposed exception requires a **separately recorded owner decision and a new
  protocol review**. It must **not** be implemented as an undocumented state
  transition.
* **No `REOPENED` state is introduced.** §6A.2's phrase *"can never be obtained"*
  is read as *"no further judgment will be obtained under this protocol."*
* Append-only requirements are unchanged: no prior event or judgment may be
  overwritten or deleted, and sealing a case terminal does not relax any
  preservation duty. Terminal cases remain fully reportable with their reason.

Recorded as **T-1 … T-6** in plan §6A.1. Acceptance criterion **AC-14e** verifies
the written terminality rules; implementation remains **E-11**, **NOT MET**.

**Affects:** gate 2 (clarifies, does not change, the §6A procedure). Not a Gate 3
authorization.

---

## Owner decisions recorded — OD-6, OD-7, OD-8, OD-9

Recorded following the Gate 3 readiness assessment. **None of these decisions
authorizes Gate 3, engineering, reviewer outreach, or adjudication.** Each
*restricts* activity; none enables it.

| id | decision | selection | status |
| --- | --- | --- | --- |
| **OD-6** | E-1 status reconciliation | register authoritative for Gate 2 status; plan preserved byte-for-byte | **OWNER-DIRECTED** |
| **OD-7** | E-5…E-11 engineering | **implementation and testing NOT AUTHORIZED** | **OWNER-DIRECTED** |
| **OD-8** | reviewer selection and outreach | **NOT AUTHORIZED** | **OWNER-DIRECTED** |
| **OD-9** | FW-4 reporting treatment | §6.9 disclosure accepted for this campaign; §9.3 amendment deferred | **OWNER-DIRECTED** |

---

## OD-6 — E-1 status reconciliation · **OWNER-DIRECTED**

**Issue.** The Gate 2-approved plan (§11.2) records **E-1 "Owner approval of this
plan (gate 2)" — NOT MET**, because it was written before approval. Register §13a
records that approval as `APPROVED 2026-10-10`. The requirement text agrees in both
documents; only the plan's status snapshot is stale.

**Selection.** The **owner decision register is authoritative** for the recorded
Gate 2 approval status.

| consequence | statement |
| --- | --- |
| **Plan preserved** | `docs/benchmark/v3_4_adjudication_plan_proposal.md` remains **byte-for-byte unchanged** at 57,465 bytes, sha256 `2d1fb031c1eae12025fb5a81fdacd3cc30113de75925503b2983b05a37a077ef`. |
| **No plan edit** | The plan's `E-1 — NOT MET` entry is **not** edited to appear current. It stands as a **stale pre-approval status snapshot**, superseded by §13a. |
| **No amendment implied** | This decision **does not amend the plan** and **does not change its approved hash**. The Gate 2 approval basis in §13a remains intact and historically accurate. |
| **E-1 assessment** | On the register's authority, **E-1 is satisfied as of 2026-10-10**. The plan's stale text is a documentation artefact, not a substantive gap. |
| **Not satisfied by decision** | E-1's satisfaction derives solely from the Gate 2 approval in §13a, **not** from this decision. Recording OD-6 changes no prerequisite status. |

---

## OD-7 — E-5 … E-11 engineering · **OWNER-DIRECTED · NOT AUTHORIZED**

**Selection. Implementation and testing are NOT AUTHORIZED.** Gate 2 approval does
not authorize these activities.

**Expressly not authorized:**

| area | scope withheld |
| --- | --- |
| **E-5** | normalization and evidence-offset implementation or testing |
| **E-6** | production adjudication packet construction |
| **E-10** | production R4 pair-generation implementation |
| **E-11** | review-state and append-only event implementation |
| **E-8** | packet-level blinding or reviewer-capture mechanisms |
| **E-7** | reporting-template implementation |
| **E-9** | pre-review source-hash automation |
| **conformance** | conformance tests or implementation changes intended to satisfy E-5 … E-11 |

**Prerequisite status is unchanged by this decision.** E-5 … E-11 remain
**NOT IMPLEMENTED** and **NOT MET**, exactly as assessed. Recording OD-7 marks no
E-item complete; it withholds the authority that would be needed to begin any of
them. The reference R4 implementation printed in plan §6.2 remains a **diagnostic
reference only** and confers no implementation status.

---

## OD-8 — Reviewer selection and outreach · **OWNER-DIRECTED · NOT AUTHORIZED**

**Selection. Reviewer selection and outreach are NOT AUTHORIZED.**

| withheld | statement |
| --- | --- |
| **Identification / recruitment** | Do not identify, recruit, or shortlist reviewers or an adjudicator |
| **Contact** | Do not contact, solicit, or correspond with any candidate reviewer or adjudicator |
| **Declarations** | Do not solicit, request, or collect independence or conflict-of-interest declarations |
| **Replacement** | Do not arrange or appoint replacement reviewers |
| **Campaign** | No review or adjudication may begin |

**E-3 and E-4 remain unsatisfied and NOT MET.** Their documentary prerequisites —
two independent initial reviewers, a third adjudicator, and dated written
independence declarations — are specified in plan §6A.3, §9 and OD-3, but **no
person has been identified, approached, or engaged**, and none is authorized to
be.

---

## OD-9 — FW-4 reporting treatment · **OWNER-DIRECTED**

**Selection.** The existing **§6.9 coverage disclosure is accepted for this
campaign**, and the formal **§9.3 amendment is deferred** to the later gate already
specified by the governing plan (**gate 6**), per plan §11.3 and §10.3.

| binding condition | statement |
| --- | --- |
| **Artifacts unchanged** | The governing specification and the Gate 2-approved plan are **unchanged**. No gate is invented and no existing gate definition is altered. |
| **Coverage distinction retained** | Adjudication-submission coverage (**156 / 415 = 37.6%**) remains distinct from the full occurrence population (**415**) and from candidate coverage (**156 / 165 = 94.5%**). M7's denominator remains **156**. |
| **No corpus-wide claims** | Subset-level results must **not** be represented as corpus-wide quality, correctness, or extraction-quality estimates. |
| **FW-4 stays open** | FW-4 is **not** silently resolved or removed from the open-item register. It remains an **open specification-amendment task at gate 6** (B-9); only its *treatment for this campaign* is fixed by this decision. |
| **Deferral recorded, not closed** | This is a **deferral notation**, not a closure of FW-4. |

---

## OD-1 — Review unit · **OWNER-DIRECTED / CAMPAIGN EXCEPTION**

**Question.** May the campaign use a split unit — R1–R3 per occurrence, R4 per
pair — given §11.1 says "pair" and §11.2/§11.3/§11.4 say "item"?

**Selection — approved as a campaign-specific hybrid:**

* **R1–R3:** occurrence-level assessment, keyed `(job_id, run_id, ordinal)`.
* **R4:** explicit obligation-pair assessment, carrying **both** occurrences'
  provenance, generated **solely** by the OD-4 / §6.2 algorithm.
* **No self-pairs** and **no arbitrary pair construction** — rules R4-A…R4-E
  apply (both members quote-bearing; members distinct; same posting;
  deterministic derivation; both members' provenance carried).
* **Pair generation follows the single algorithm in OD-4** (all cross-run,
  distinct-member pairs; sorted by `(run_id, ordinal)`; lexicographic emission;
  stable pair ids). **The earlier "consecutive run pairs" wording is withdrawn as
  inconsistent with OD-4 and must not be used.** Each pair is emitted **once**; an
  occurrence may appear in multiple pairs; every verdict is stored against **both**
  occurrence keys and is **never inferred from another pair's verdict**.
* Where no defensible partner exists — a group with fewer than two distinct runs —
  R4 is recorded `UNSURE — NO_ELIGIBLE_PARTNER under the §6.2 algorithm`.
  **A pairwise verdict is never forced onto a single occurrence, and no comparison
  partner is invented.**

**§11.1 wording conflict is preserved as an explicit open specification
inconsistency.** The "pair" (L1306) versus "item" (L1320, L1334, L1339) conflict
is **not resolved** and remains on the inconsistency register.

**This decision does not amend or override the governing specification
generally.** It is a documented protocol exception for **this campaign only**:
it settles no question of §11.1's construction beyond this campaign's packet
format, creates no precedent binding on future work, and is **revocable** —
if reconciliation resolves against the hybrid, the exception is withdrawn and the
protocol reverts.

**Formal specification reconciliation added to the future work register** as
**FW-1** (plan §10.3), gate 6. The campaign exception expires when it resolves.

**Affects:** gate 2 (now unblocked by this decision).

---

## OD-2 — Quotation correspondence · **OWNER-DIRECTED**

**Question.** How are C1 byte-exact, C2 dash-normalised, and C3 truncated-prefix
occurrences to be labelled and submitted, given §5.2's exact-correspondence rule
(L607–610)?

**Selection — existing conservative handling accepted:**

| class | treatment | submitted to R1 |
| --- | --- | --- |
| **C1 byte-exact** | correspondence only, with **verified offsets** | **YES — 156** |
| **C2 normalised** | remains a **separate diagnostic class**; **not** `EVIDENCE_VERIFIED` | **NO — 8 excluded** |
| **C3 truncated-prefix** | remains **separate**; **not automatically accepted** | **NO — 1 excluded** |

* **C2 and C3 are excluded from R1 submission under this campaign's protocol
  unless the governing specification is separately amended.**
* **Every occurrence is retained**, and **every exclusion and its reason is
  reported.** Exclusion codes: `CORRESPONDENCE_NORMALISED_NOT_EXACT` (8),
  `CORRESPONDENCE_UNRESOLVED_TRUNCATED_PREFIX` (1).
* **`EVIDENCE_VERIFIED` is not redefined.** §5.2 is unmodified. No normalised or
  truncated match is labelled `EVIDENCE_VERIFIED`.
* Exclusion is a **submission and reporting decision only** — it does not
  reclassify either class, does not assert `NOT_SUPPORTED`, and does not assert
  the underlying claims are false. Exclusion is never deletion, silent omission,
  or a downgrade (§5.2.2, §5.2.1 rule 4).

### Denominator reconciliation — all figures tie out

```text
415 corpus occurrences
 = 250 no quotation available   (D-7; structurally non-adjudicable)
 + 165 candidates carrying a quotation
       = 8 C2 excluded (OD-2) + 1 C3 excluded (OD-2) + 156 C1 SUBMITTED
```

| quantity | value |
| --- | --- |
| corpus occurrences | **415** |
| no quotation available (D-7) | **250** |
| candidates carrying a quotation | **165** |
| excluded from R1 submission (OD-2) | **9** |
| **submitted — M7 denominator** | **156** |
| coverage vs corpus | **156 / 415 = 37.6%** |
| coverage vs candidates | **156 / 165 = 94.5%** |

**M7 itself is not redefined.** Its §9.3 definition is unchanged
(L1219: numerator *"requirements adjudicated supported"*, denominator
*"requirements submitted for adjudication"*). What changes is **how many
occurrences are submitted** — a reporting input, not a metric change.

**M7 could read 100.0% while describing 37.6% of the corpus.** The coverage
disclosure is mandatory in the same report block (§11.5 requires explicit
denominators). **No subset of 156 may be presented as establishing
benchmark-wide extraction quality, correctness, or evidence coverage.**

**Note on a coincidental equality:** M11-C1 (156/415) and adjudication coverage
(156/415) are both 37.6% because the same 156 occurrences are byte-exact and
submittable. They are **different quantities** — evidence coverage versus
adjudication coverage — and are reported under their own names, never merged.

**Affects:** gate 2 (now unblocked); reporting content at gate 4.

---

## OD-3 — Reviewer identities · **OWNER-DIRECTED**

**Question.** Must reviewer and adjudicator identities exist before the written
protocol is approved, or only before review launches?

**Selection: approved with identities deferred to the execution gate.**

The written protocol may be approved at gate 2 without reviewer identities being
supplied. Basis: §11's own preamble (L1301) — §11 *"does not authorize conducting
reviews, **recruiting reviewers**, assigning cases, or labeling data."* Reviewer
supply is outside §11's authority and cannot be a precondition for approving a
protocol §11 defines as design-only.

**Required at gate 3, before any assessment begins:**

* two **independent initial reviewers** — no visibility of each other's judgments
  (§11.2);
* a **third adjudicator** for disagreements (§11.3 r2);
* **identities and written independence declarations documented before any
  assessment begins** — written, dated, filed.

**No recruitment or review is authorized by OD-3.** No reviewer or adjudicator
has been identified, contacted, engaged, or appointed; **no human reviewer has
been approached**; no reviewer identity exists. This remains unmet prerequisite
**E-3/E-4** (plan §11.2).

**Affects:** gate 3 — execution, not approval.

---

## Status summary

| id | decision | owner selection | status | blocks |
| --- | --- | --- | --- | --- |
| **D-0** | corpus | (a) historical V3.3 baseline first | **OWNER-DIRECTED** | POLICY |
| **D-1** | review unit | documented hybrid (R1–R3 occurrence / R4 pairs) | **OWNER-DIRECTED** | **§11.1 reconciliation OPEN** |
| **D-2** | blinding | full blinding incl. candidate profile | **OWNER-DIRECTED** | — |
| **D-3** | verdict mapping | non-lossy | **OWNER-DIRECTED** | POLICY |
| **D-4** | disagreement | per-dimension; R1 alone drives the field | **OWNER-DIRECTED** | — |
| **D-5** | reporting | preserve §9.3; explicit denominators + coverage; M11 population settled | **OWNER-DIRECTED** | residual §9.3 tasks OPEN |
| **D-6** | correspondence | dash-normalisation minimum; C2/C3 **not** `EVIDENCE_VERIFIED` | **OWNER-DIRECTED** | **CLOSED by OD-2** |
| **D-7** | blank quotations | retain 250 as `UNADJUDICATED` / `NO_QUOTATION_AVAILABLE` | **OWNER-DIRECTED** | — |
| **D-8** | aggregation | occurrence-primary; posting + name-group secondary | **OWNER-DIRECTED** | — |
| **D-9** | reviewer independence | two reviewers + third adjudicator; declarations before execution | **OWNER-DIRECTED** | **EXEC gate 3 — E-3/E-4, superseded operationally by OD-3** |

**No reviewer or adjudicator has been identified, contacted, engaged, or
appointed.** D-9's policy requirement is selected and carried into **OD-3**;
its execution prerequisite is unsatisfied and is **not** a plan-approval blocker.

**Stage 4 refinement of the D-series.** **OD-1** refines D-1 by scoping the
hybrid as a revocable campaign-specific exception (B-2 closed for this campaign;
§11.1 inconsistency retained, FW-1). **OD-2** closes D-6's open C2/C3
disposition by excluding both from R1 submission, which **fixes the M7
denominator at 156** and updates D-5's coverage disclosure from 165/415 = 39.8%
to **156/415 = 37.6%**. **OD-3** confirms D-9's policy requirement and defers
identity to gate 3. D-0, D-2, D-3, D-4, D-7, D-8 are unchanged.

---

## D-0 — Corpus · **OWNER-DIRECTED**

**Question.** Adjudicate the V3.3 corpus, or wait for the corrected-contract
diagnostic (§10, unrun per §10.6)?

**Selection: option (a) — historical V3.3 baseline first.**

**Binding qualification.** All findings from this review identify their data as
**V3.3 output produced under `ExtractedJobRequirements@2` and the frozen
historical prompt** (`43d20b8be806e7ba`). **No finding may be presented as
validation of the corrected extraction pipeline.** The corrected contract does
not exist in this corpus.

**Corrected-contract diagnostic execution requires separate authorization**
(§10.6). It is not requested or implied here.

**Consequence.** The review yields a historical baseline semantic-support rate on
the review yields a historical baseline semantic-support rate on
**156 submitted occurrences** (under OD-2; 165 candidates before C2/C3
exclusion), which is the empirical input to whether option (b)
is viable at all.

**Limitation.** It cannot validate the corrected pipeline, and it inherits V-1
(250 blank skill quotations) and the `VJ-B04` missing-payload limitation.

**Blocks:** nothing further. **Informs:** gate 5 (owner decision on A4).

---

## D-1 — Review unit · **OWNER-DIRECTED · superseded by OD-1 (campaign exception)**

> **Stage 4:** this selection is carried forward as **OD-1**, scoped as a
> **campaign-specific, revocable protocol exception**. B-2 is closed for this
> campaign; the §11.1 wording conflict **remains an open specification
> inconsistency** tracked as **FW-1** (gate 6). It is **not** resolved.

**Question.** §11.1 opens *"For each requirement pair presented for review…"*.
Occurrence, pair, or run as the unit?

**Selection: documented hybrid.**

* **R1, R2, R3** — assessed per **individual requirement occurrence**, keyed
  `(job_id, run_id, ordinal)` (verified unique across all 415).
* **R4** — assessed per **explicitly constructed requirement pair** under five
  deterministic rules, spelled out identically in the plan (§6.2):

  | rule | requirement |
  | --- | --- |
  | **R4-A** | both members quote-bearing |
  | **R4-B** | members are distinct occurrences — **self-pairing prohibited** |
  | **R4-C** | same posting |
  | **R4-D** | deterministic derivation, never chosen for convenience or agreement |
  | **R4-E** | both members' full occurrence provenance carried into the pair record |

* **Duplicate-pair handling — governed solely by OD-4 / plan §6.2.** Every
  cross-run, distinct-member pair; sorted by `(run_id, ordinal)`; emitted once;
  lexicographic emission; stable pair ids; both members' occurrence provenance
  preserved. **The "consecutive run pairs" wording is withdrawn.**
* **Pair-verdict independence.** Every pair is independently reviewable. A
  verdict is **never** inferred or propagated from another pair, even when pairs
  share a member; one occurrence may hold several R4 verdicts, recorded separately.
* **No defensible partner** → R4 recorded `UNSURE — NO_ELIGIBLE_PARTNER under the
  §6.2 algorithm` (a group with fewer than two distinct runs). **No comparison
  partner is invented and no verdict is forced onto a single occurrence**;
  R1–R3 still proceed in full.

**Reconciliation with §11.1 — partial; the residue is FLAGGED, not resolved.**

§11 contains **inconsistent unit wording**:

| line | wording |
| --- | --- |
| L1306 (§11.1) | *"For each requirement **pair** presented for review…"* |
| L1314 (§11.1 R4) | *"do these **two items** impose materially different obligations"* |
| L1320 (§11.2) | *"Two reviewers independently review every **item**…"* |
| L1334 (§11.3 r4) | *"`UNRESOLVED` **items**…"* |
| L1339 (§11.4) | *"**Per item**: both initial judgments…"* |

Four of five unit references say **item**, including §11.4's audit-trail
requirement, and §11.1's own R4 wording presupposes two items. **The hybrid is
consistent with §11.2, §11.3, §11.4 and §11.1's R4.**

**§11.1's opening sentence is NOT reconciled.** It describes one uniform unit for
all four dimensions; the hybrid splits the unit by dimension. This is **not
claimed resolved**. It is recorded as specification-inconsistency item **3** and
assigned to a **future specification amendment**.

**Owner action required (blocker B-2).** Confirm the hybrid is acceptable against
§11.1, **or** require a uniform pair unit — in which case workload, packet format
and reporting all change and this selection must be revisited.

**Blocks:** final plan review, pending owner confirmation.

---

## D-2 — Blinding · **OWNER-DIRECTED**

**Question.** May reviewers see scores, recommendations, blockers, component
values, run-to-run agreement counts, or the candidate profile?

**Selection: no. All are hidden during the independent review pass.**

Hidden: `score`, `overall_score`, all component scores, `recommendation`,
`blocker_count` and blocker detail, run-to-run agreement/disagreement counts, and
the **candidate profile**.

**Plus, unchanged from §11.2:** reviewers must not see **each other's initial
judgments** during the independent pass.

**Basis.** §11.2 requires only mutual invisibility of judgments; §11 is silent on
scores, so blinding fills a gap rather than conflicting with it. §11.4's audit
trail is fully satisfiable without any score, and R1–R4 concern the posting
rather than the candidate.

**Limitation.** Slightly less context for judging importance. Recorded, accepted.

---

## D-3 — Verdict mapping · **OWNER-DIRECTED**

**Question.** The specification defines R1 verdicts and separately uses
`semantic_support`, but **never states the mapping** (§5.1.4 records the gap and
declines to invent it).

**Selection: non-lossy mapping.**

| resolved R1 | stored `semantic_support` |
| --- | --- |
| `SUPPORTED` | `SUPPORTED` |
| `NOT_SUPPORTED` | `NOT_SUPPORTED` |
| `PARTIAL` | `PARTIAL` |
| resolved `UNSURE` | `UNSURE` |
| adjudication `UNRESOLVED` / no settled judgment | `UNADJUDICATED` |
| never submitted | `UNADJUDICATED` + recorded reason |

**`UNSURE` versus `UNADJUDICATED`:** **`UNSURE` is a judgment** — reviewers looked
and could not decide (§11.1: *"`UNSURE` is a first-class verdict. It is never
coerced into a binary"*). **`UNADJUDICATED` is a state of the record** — no
settled judgment exists (§11.3 r4). Collapsing them would destroy the ambiguity
signal §11.4 requires be reported.

**Binding:** the original **four reviewer dimensions** and the **full audit
record** are preserved unchanged. The mapping is non-lossy — every §11.1 verdict
survives.

**Audit trail — binding, applies to every decision in this register (§11.4).**
Records are **append-only**: both independent initial assessments, reviewer
identifiers, timestamps, all four rubric dimensions, rationales, confidence in
{low, medium, high} (§11.2), third-reviewer decisions, unresolved outcomes,
rubric version, and frozen source references are all retained. **Nothing is ever
overwritten or deleted** (§11.3 r1, §5.2.2) — neither initial judgment may be
replaced by the adjudicator's verdict, and an `UNRESOLVED` outcome is retained
alongside any later resolution.

**Blocks:** nothing further. Required reading for gate 5.

---

## D-4 — Disagreement resolution · **OWNER-DIRECTED**

**Question.** Per §11.3, may `semantic_support` be set when R1 itself is
unresolved?

**Selection: each dimension resolves independently; R1 alone determines
`semantic_support`.**

R1 `UNRESOLVED` maps to `UNADJUDICATED` **regardless** of the resolution of R2,
R3 or R4. Both original judgments and the full resolution record are preserved.
The adjudicator records `AGREED` (with converged verdict) or `UNRESOLVED`
(§11.3 r3). **Agreement is never forced** — no tie-break by rank, seniority, or
re-review-until-consistent.

**Basis.** §11.3 is deliberately per-dimension, and option (b)'s predicate reads
a single field, so that field needs a single unambiguous source.

**Limitation.** A resolved R2/R3/R4 cannot compensate for unresolved R1 —
intended and now recorded.

---

## D-5 — Reporting · **OWNER-DIRECTED · residual §9.3 tasks OPEN**

**Question.** M7's denominator is self-selected; M11's denominator is
uncomputable on this corpus.

**Selection: preserve the existing M7 and M11 definitions unchanged.**

* **No existing metric name is redefined, renamed, or repurposed.**
* **Exact denominators published**, plus **mandatory coverage disclosures**
  alongside M7 in the same report block — satisfying §11.5's existing requirement.
* **The 250 blank-quotation occurrences reported separately**, never inside any
  numerator or any "unsupported" count.
* M7 is **never published alone**; the coverage line is mandatory, because M7's
  self-selected denominator otherwise permits a coverage-blind 100%.
  **Refined by OD-2:** with C2 and C3 excluded from R1 submission, the M7
  denominator is **156** and the coverage line reads **156/415 = 37.6%** (it read
  165/415 = 39.8% under D-5 alone). Full reconciliation — 415 = 250 no-quotation
  + 165 candidates; 165 = 9 excluded + 156 submitted.
* **The 9 OD-2-excluded occurrences are also reported separately**, never inside
  any numerator, any "unsupported" count, or M7's denominator.

**M11 canonical population — settled explicitly.** §9.3 denominates M11 by
*"all canonical requirements"*. **Occurrences are not canonical identities and are
never silently equated with them.** Computing the specified denominator requires
the §8.1/§8.2 identity rule, which is **a proposal, not implemented** (§8.2 is
marked *"PROPOSAL — not implemented"*), and V3.3 used the **old, defective**
identity key that §8.1/V-3/V-4 exist to correct.

**Settlement:** M11 is reported **deviation-flagged** over the **415 occurrences**,
with the flag stating the denominator is the occurrence count and **not** the
specified canonical population. Alongside it, **M11-C1** = C1/415 = 156/415 =
37.6% is reported — it counts correspondence classes on occurrences and needs no
identity rule. Both are labelled; neither is passed off as the specified metric.

**Residual, assigned to future tasks (not done here):** widening M7's denominator,
and computing M11's true population once the identity rule exists — both require
§9.3 amendments.

---

## D-6 — Correspondence and offsets · **OWNER-DIRECTED · superseded by OD-2 (disposition CLOSED)**

> **Stage 4:** the previously-open C2/C3 disposition is **CLOSED by OD-2** — all 9
> occurrences are excluded from R1 submission, retained and reported with
> exclusion codes; 156 C1 occurrences are submitted. **`EVIDENCE_VERIFIED` is not
> redefined and §5.2 is unmodified.** B-5 and B-6 are closed for this campaign.

**Question.** §5.2 defines `EVIDENCE_VERIFIED` as a byte-exact substring match.
Measured across the **165 candidate occurrences** (those carrying a quotation):
**156 byte-exact (C1)**, **8 matching
only after Unicode dash normalisation (C2)**, **1 truncated prefix (C3)**. A naive
byte-exact test would falsely reject 9/165 (5.5%) and bias reviewers.
**OD-2 resolution:** all 9 are excluded from R1 submission, retained and
reported; 156 C1 occurrences are submitted.

**Selection: documented Unicode-dash normalisation as the minimum diagnostic
comparison, with byte-exact matches kept distinct.**

**Normalisation rule (fixed before packet creation):** NFKC → map U+2010, U+2011,
U+2012, U+2013, U+2014, U+2212 to U+002D → collapse whitespace runs → strip →
case-fold.

**Three classes recorded separately, never merged:**

| class | count | may be `EVIDENCE_VERIFIED`? |
| --- | --- | --- |
| **C1 byte-exact** | 156 | **Yes** — satisfies §5.2's exact-correspondence rule |
| **C2 dash-normalised** | 8 | **No.** §5.2's rule is exact correspondence. A normalised match does **not** satisfy it. **Must not** be relabelled `EVIDENCE_VERIFIED` unless a **separately approved specification change** permits it |
| **C3 truncated-prefix / unresolved** | 1 | **No. Not automatically accepted.** Flagged for owner disposition |

**Truncated-prefix handled separately, not auto-accepted.**

**Original `source_text` preserved verbatim** in every record; normalisation
applies to the comparison only, never to stored text. **The matching class is
recorded.**

**Offsets — deterministic or flagged:**

* **C1** — offsets into the **original, unmodified** frozen posting bytes,
  `[start, end)`, with the posting sha256 they refer to.
* **C2** — a normalised match has **no unambiguous offset in the original bytes**
  (the text differs by codepoint). **No offset is invented.** Flagged
  `OFFSET_UNRESOLVED_NORMALISED` per §5.6 c.4 (*"ambiguity is flagged, never
  guessed"*).
* **C3** — no offset; flagged `OFFSET_UNRESOLVED_PREFIX`.

Every offset must pass **round-trip verification** — slicing the original frozen
bytes at `[start, end)` must reproduce `source_text` byte-for-byte. Offsets
failing round-trip are discarded and the item flagged, never emitted.

**Normalisation and offset mapping must be defined and tested before packet
creation** (blocker B-7).

**Open:** owner disposition for C2 (B-5) and C3 (B-6).

---

## D-7 — Blank quotations · **OWNER-DIRECTED**

**Question.** 250 of 415 occurrences (60.2%) are `SKILL` type with **100% blank
`source_text`** — reproducing V-1. R1 cannot be asked of them.

**Selection: retain all 250 as unadjudicated, reason `NO_QUOTATION_AVAILABLE`.**

* **Not submitted** to quote-entailment review.
* **Never** classified `NOT_SUPPORTED`. **Missing evidence is not evidence of
  absence** — a blank quotation is absence of the material the question requires.
* Never in any numerator, any "unsupported" count, or M7's denominator.
* **Never deleted** — §5.2.2 and §5.2.1 rule 4 forbid deletion, silent omission,
  and downgrading importance. Retained as records with machine-readable reason.

---

## D-8 — Aggregation · **OWNER-DIRECTED**

**Selection: occurrence-level reporting is primary.** Posting-level (8 units) and
name-group-level views are **secondary analyses**.

**Binding:** all occurrence-level provenance is preserved **even when canonical
or posting aggregation is reported**, honouring §8.2's requirement that merging
preserve one `Provenance` per occurrence. No occurrence is consumed by pairing or
aggregation.

---

## D-9 — Reviewer independence · **OWNER-DIRECTED (OUTSTANDING)**

**Question.** Who are the two independent reviewers and the third adjudicator?

**Selection: two independent reviewers plus a third adjudicator, with identities
and written independence declarations established before execution.**

**OUTSTANDING EXECUTION PREREQUISITE — NOT SATISFIED.**

> **No reviewer or adjudicator has been identified, contacted, engaged, or
> appointed. No human reviewer has been approached. No reviewer identity exists,
> so no independence declaration can be made.**

Independence must be declared **before** any assessment (§11.2, §11.3 r2). This
blocks **gate 3** (separate authorization for human adjudication) and is carried
as open blocker **B-1**.

Note `human_labels_v3.json` remains status `PENDING_INDEPENDENT_HUMAN_REVIEW` with
23 of 23 labels outstanding, so no completed prior label pass exists to anchor to.

---

## 13. Known specification inconsistencies — recorded, not fixed

The governing specification is **not modified** in this stage. Each item is
assigned to an explicit future task.

| # | inconsistency | assigned to |
| --- | --- | --- |
| 1 | `ExtractedRequirementV3` (§5.4) has no `semantic_support`, `decision_eligible`, or `importance_adjudicated` field, yet option (b) reads `semantic_support` | **Future specification amendment** — required before implementing option (b) |
| 2 | `SEMANTIC_UNADJUDICATED` survives at §5.6 c.5 (L793) and §17.1 c.9 (L1512) despite r3.1 supersession | **Future specification amendment** — vocabulary alignment |
| 3 | §11.1's "requirement pair" unit conflicts with §11.2/§11.3/§11.4's "item" unit; the D-1 hybrid is consistent with four references, unreconciled with one | **Future specification amendment** — reconcile §11.1 with the hybrid |
| 4 | M11's canonical population is not computable (§8.1/§8.2 identity rule unimplemented; V3.3 used the defective key) | **Future specification or engineering task** |
| 5 | §5.2's exact-correspondence rule excludes C2 matches (8) that are substantively verbatim | **Future specification decision** |
| 6 | M7's self-selected denominator permits a coverage-blind 100% | **Future specification amendment** |

---

## 13a. Gate 2 owner approval decision — **APPROVED**

**Decision:** `APPROVED`
**Gate:** `Gate 2 — adjudication plan approval`
**Decision date:** `2026-10-10` *(ISO-8601 plain date, matching the repository's established convention — cf. `archive_retrieved: "2026-10-07"` in `docs/benchmark/v3_3_frozen_provenance.json`)*
**Basis:** successful **Stage 9 independent read-only readiness review**
**Stage 9 report conclusion:** `RECOMMEND GATE 2 APPROVAL`

**Decision scope — approval of the current adjudication plan only.** This approval accepts the adjudication protocol as sufficiently specified to proceed to the subsequent readiness and execution-preparation gates. **It does not authorize the adjudication campaign to begin.**

**Exact artifacts approved** (hashes against which this decision was made):

| artifact | path | SHA-256 |
| --- | --- | --- |
| governing specification | `docs/benchmark/v3_4_corrective_engineering_specification.md` | `ed299934216d7e5c3f22a513f9df374ef142cbe5fdf76073d7841b88a9c2cd38` |
| adjudication plan | `docs/benchmark/v3_4_adjudication_plan_proposal.md` | `2d1fb031c1eae12025fb5a81fdacd3cc30113de75925503b2983b05a37a077ef` |
| owner decision register (pre-approval) | `docs/benchmark/v3_4_owner_decision_register.md` | `fc2c8806b76dcd57c080e675a49c8746a62cdb1df99e647bd18d17a86cdc2ad1` |

The specification and the plan are **unchanged by this record**; only this register was edited. Any future change to the specification or plan voids the basis of this approval and requires a fresh independent readiness review.

**Approval metadata — deliberately not recorded.** This repository defines **no** owner-identifier, approver, signature, attestation, witness, or clock-time field for approvals, and none is invented here. The decision is attributed to **the project owner** as the decision-making authority, with the date above and the approved-artifact hashes as its complete identifying record. If an owner identifier or formal attestation is later required, it must be supplied by the owner and appended as a separate record; it is not inferred.

### Restrictions that remain in force after Gate 2 approval

Gate 2 approval changes **nothing** below. Each item retains its prior status.

| # | restriction | status after Gate 2 |
| --- | --- | --- |
| 1 | Gate 3 — adjudication execution | **NOT AUTHORIZED** |
| 2 | Human adjudication | **NOT AUTHORIZED** |
| 3 | Reviewer recruitment or contact | **not authorized** |
| 4 | Provider calls, extraction, experiments, benchmark runs | **not authorized** |
| 5 | Production packet builder; offset/normalization implementation; schema changes; engine changes; state-management implementation | **not authorized** |
| 6 | Prerequisites **E-1 … E-11** | **retain their recorded status — none is marked complete by this approval** |
| 7 | **FW-1 … FW-5**, **U-1**, **U-2b**, **U-4** | **existing statuses and required resolution gates retained** |
| 8 | Eligibility option (b) | **NOT IN FORCE** |
| 9 | **R-E1 operative** | `decision_eligible = (evidence_state == EVIDENCE_VERIFIED)` |
| 10 | Adjudication performed so far | **none** — no requirement adjudicated, no reviewer judgment recorded, no campaign execution implied |

**Explicitly unchanged by this approval:** the R4 pairing algorithm and its counts (31 groups · 50 pairs · 72 covered occurrences · 93 without an eligible R4 partner); the R1/R4 eligibility distinction and the two C2 occurrences in R4-eligible groups (`VJ-B04` run 1 ordinal 2, `VJ-B23` run 2 ordinal 5); the 156-occurrence R1 submission population and M7 denominator; §6A terminality rules T-1…T-6; OD-1…OD-5 and D-0…D-9 in full.

**Gate 2 is a protocol approval, not a campaign launch.** The eleven execution prerequisites — in particular reviewer identities and written independence declarations (OD-3, E-3/E-4) — remain unmet and must be satisfied under a separate Gate 3 authorization before any assessment begins.

---

## 14. Gates

| # | gate | state |
| --- | --- | --- |
| 1 | Decision and plan documentation | **DONE** |
| 2 | Final plan review and explicit approval | **APPROVED 2026-10-10** (§13a) — previously "NOT MET — now reachable"; that prior state is preserved in §13a and below |
| 3 | Separate explicit authorization for human adjudication | **NOT AUTHORIZED** — prerequisites E-1…E-11 unmet |
| 4 | Audit of adjudication results | not reached |
| 5 | Separate owner decision on A4 | not reached |
| 6 | Separate specification amendment if A4 is adopted | not reached |
| 7 | Separate D7 authorization for engine-side consequences | not reached |

**Gate 2 is met as of 2026-10-10 (§13a). Gate 2 approval does not authorize Gate 3.** Gate 3 remains a separate owner act and requires E-1…E-11 — in particular reviewer identities (OD-3, E-3/E-4) and separately authorized implementation of the normalisation and offset round-trip logic (B-7, E-5).

**Preserved history — §14 gate 2 and gate 3 before this decision.** Gate 2 was
recorded as *"NOT MET — now reachable; OD-1/2/3 recorded, no approval-blocking
question open"* and gate 3 as *"NOT MET — prerequisites E-1…E-10 unmet"*. Those
records are superseded in status only; neither is deleted or rewritten, and the
substantive content they carried — that gate 2 was reachable with no
approval-blocking question open, and that gate 3 depends on unmet prerequisites —
remains true.

## 15. Blocker status (reclassified at Stage 3/Stage 4)

The prior revision listed all nine items as blockers to gate 2. That overstated
the position: several items' own status text placed them at later gates.

| # | blocker | class | gate it blocks | status |
| --- | --- | --- | --- | --- |
| B-1 | Reviewer/adjudicator identities, independence declarations | execution prerequisite | 3 | **OPEN** — E-3/E-4; deferred by OD-3 |
| B-2 | §11.1 "pair" vs §11.2–§11.4 "item" | campaign exception (OD-1) + future spec task | **none now**; FW-1 at 6 | **RESOLVED for this campaign**; inconsistency retained |
| B-3 | §5.4 schema lacks option (b) fields | technical prerequisite | 6 | **OPEN** — future spec amendment; does not affect adjudication |
| B-4 | M11 canonical population not computable | reporting limitation | **none** — deviation-flagged | **OPEN as engineering task**; transparent for this run |
| B-5 | 8 C2 occurrences not `EVIDENCE_VERIFIED` | owner decision (OD-2) | **none** | **RESOLVED** — excluded, retained, reported |
| B-6 | 1 C3 occurrence not auto-accepted | owner decision (OD-2) | **none** | **RESOLVED** — excluded, retained, reported |
| B-7 | Normalisation + offset round-trip not implemented/tested | technical prerequisite | 3 (packet release) | **OPEN** — E-5 |
| B-8 | `SEMANTIC_UNADJUDICATED` vocabulary conflict | technical prerequisite | 6 | **OPEN** — FW-3 |
| B-9 | M7 self-selected denominator | reporting limitation | **none** — disclosure implemented | **OPEN as spec task** — FW-4 |

**Remaining plan-approval blockers: none.** Gate 2 is reachable.

**Execution prerequisites (gate 3). E-1 is satisfied; E-2 through E-11 remain
NOT MET.** **E-1 — Gate 2 plan approval — SATISFIED** as of `2026-10-10` per §13a; OD-6 makes this register authoritative for that status, and the approved plan is byte-identical while retaining its historical pre-approval `E-1 — NOT MET` status snapshot, which is deliberately not edited. **Still NOT MET:** E-2 execution authorization · E-3 reviewers named · E-4 independence declarations · E-5 normalisation/offset implemented and tested · E-6 packet builder · E-7 reporting template · E-8 blinding confirmed · E-9 posting hashes re-verified · E-10 R4 pair rule implemented · E-11 §6A append-only event protocol implemented. **Gate 3 remains NOT AUTHORIZED.**

*Correction note (documentation-only, appended under the register's append-only convention; no new decision identifier is created, since this applies OD-6 rather than adding an owner decision).* The prior wording of this paragraph read: *"**Execution prerequisites (gate 3), all NOT MET:** E-1 plan approval · E-2 execution authorization · E-3 reviewers named · E-4 independence declarations · E-5 normalisation/offset implemented and tested · E-6 packet builder · E-7 reporting template · E-8 blinding confirmed · E-9 posting hashes re-verified · E-10 R4 pair rule implemented."* That text is superseded on two points: it listed **E-1 as unmet**, which §13a and OD-6 make inaccurate; and it **omitted E-11**, which was added to the plan at Stage 6. Both defects are corrected above. No other §15 entry, blocker row, or historical record was altered.

**Later-gate items, deliberately not blockers:** FW-1 §11.1 reconciliation ·
FW-2 schema fields (B-3) · FW-3 vocabulary (B-8) · FW-4 M7 rule (B-9) · FW-5
M11 population (B-4) — all gate 6 or engineering. **U-1** and **U-2b**
(`UNRESOLVED — BLOCKING`) belong to extraction stage 1; **U-4**
(`PROVISIONAL — NOT VALIDATED`) belongs to stage 3. **None blocks adjudication,
and U-4 is not promoted to a validated finding.**

**Option (b) remains NOT IN FORCE. R-E1 remains the operative rule.** Adjudication
results would inform a later owner decision; they would not activate it.
