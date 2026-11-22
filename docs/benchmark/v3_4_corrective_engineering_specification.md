# V3.4 Corrective Engineering Specification

**Status:** DESIGN AND SPECIFICATION ONLY — AMENDED. Not implemented.

```text
specification version : v3.4-spec-r3.4  (A4 decision preparation A6)
supersedes            : v3.4-spec-r3.3  (sha 6cbd08ca4735864a83ce434540d21076a37e9b09c2e2d609ddb2e2ef3b63dfef, 95704 bytes)
baseline experiment  : V3.3 deterministic job-requirement extraction reproducibility
V3.3 ledger          : 6f8f6a1ee5f54acb1bd9d9270f89edf8c244c72118381c21931feb20740557c0
V3.3 analysis        : a03bd0a12d167903311e0841eb5f9179b7cddf9ca4de8358759bc0a6932524ad
extraction contract  : ExtractedJobRequirements@2  (frozen; superseded only by future implementation)
```

### Evidence classes used throughout

| class | meaning |
| --- | --- |
| **Verified** | directly supported by inspected code or a reproducible demonstration |
| **Strongly supported** | multiple observations agree; causality not fully isolated |
| **Hypothesis** | plausible; requires testing |
| **Design decision (D1–D8)** | fixed by the user; not reopened here |
| **Implementation-time verification (V-pending)** | must be established during implementation; no value assumed now |

---

## 0. Authoritative decisions (D1–D8)

These are **fixed**. This amendment records and applies them; it does not
reopen or substitute them.

| id | decision |
| --- | --- |
| **D1** | **Evidence policy.** Mandatory source evidence for every candidate-specific requirement entering decision-bearing use. **No automatic skill exception.** |
| **D2** | **Architecture.** Approach A — one richer structured extraction call. |
| **D3** | **Deduplication.** Separate requirement identity from classification. Preserve genuinely distinct requirements **and all merged provenance**. |
| **D4** | **Output budget.** Explicitly pin a **verified, supported** output limit. Do not assume 3,072 tokens is the correct limit. |
| **D5** | **Diagnostic set.** Exactly eight postings: `VJ-B04`, `VJ-B11`, `VJ-B14`, `VJ-B20`, `VJ-B23`, `VJ-B28`, `VJ-02`, `VJ-03`. |
| **D6** | **Semantic review design.** Two independent reviewers, a documented rubric, and an explicit disagreement-resolution procedure. Designing the procedure does **not** authorize conducting reviews. |
| **D7** | **Engine-consumer review.** Requires separate explicit authorization. |
| **D8** | **Historical payload limitation.** Preserve that 12 early V3.3 runs lack raw/coerced payloads. Do not reconstruct or imply access to missing artifacts. |

---

## 1. Executive summary and scope

V3.3 established that extraction under the frozen contract is not repeatable:
0/26 canonical identity stability, 0/26 score stability, 164/759 distinct
requirement names recurring across runs, 7/26 jobs changing recommendation.

Repository inspection found **five defects that are deterministic, not sampling
noise**. Each was reproduced during CE-13.

| # | finding | class |
| --- | --- | --- |
| V-1 | Half of all requirements **cannot** carry evidence | **Verified** |
| V-2 | Skill importance is **never adjudicated** | **Verified** |
| V-3 | Deduplication keys on classification | **Verified** |
| V-4 | Frozen identity metric bundles selection and classification | **Verified** |
| V-5 | Scoring is a weighted **mean** | **Verified** |

The central claim: **the dominant reproducibility failure is not model sampling
variability. It is that the extraction contract expresses most requirements in
a form that structurally cannot carry the evidence the rest of the pipeline
assumes exists.** Skills carry no evidence (V-1) → importance cannot be
adjudicated (V-2) → classification depends on array placement → dedup splits
them (V-3) → count inflates → weighted-mean score moves (V-5).

This is favourable: V-1 to V-3 are addressable by contract and code changes that
are deterministic and unit-testable, with **no model change**. It is
unfavourable for any plan treating this as prompt tuning.

**Scope.** Evidence-bearing representation; single-call extraction contract;
identity/classification contract; output budget and failure handling;
diagnostic protocol; semantic-support review protocol; evaluation plan;
score/recommendation sensitivity; migration and versioning.

**Out of scope** (§13, D7). Implementation; extraction reruns; model, provider
or prompt experiments; benchmark changes; human-label execution; matching-engine
integration, scoring changes, threshold changes, blocker changes.

---

## 2. Verified V3.3 findings and supporting code paths

### Paths inspected

```text
apps/api/app/schemas/__init__.py                    ExtractedJobRequirements, ExtractedRequirement, Importance
apps/api/app/ai/openai_provider.py                  REQUIREMENT_CONTRACT_PROMPT, _json_completion, _coerce_job_requirements
apps/api/app/services/extraction.py                 coerce_requirements_payload, canonical_requirements, canonical_identity_set
apps/api/app/services/requirements.py               canonicalize, _dedupe_key, validate_importance, infer_category, normalize_requirement_name
apps/api/app/core/config.py                         Settings
apps/api/app/services/matching.py                   to_candidate_profile, build_settings
packages/matching/matching/types.py                 Requirement, JobProfile
packages/matching/matching/config.py                MatchWeights, RecommendationPolicy, MatchSettings
packages/matching/matching/engine.py                _importance_weight, dimension scorers, threshold mapping
validation_jobs/benchmark_selector.py                membership and source resolution
validation_jobs/harness_scheduling.py                conflict-aware scheduling
validation_jobs/scripts/v33_runs.py                  run harness and telemetry capture
docs/benchmark/v3_3_final_stability_analysis.{json,md}
tests/test_v33_*.py
```

### V-1 — Half of all requirements cannot carry evidence · **Verified**

Three independent enforcement points.

**(a) Schema.**

```python
required_skills:  list[str] = Field(default_factory=list)   # plain strings
preferred_skills: list[str] = Field(default_factory=list)
experience_requirements: list[ExtractedRequirement] = ...   # objects
education_requirements:   list[ExtractedRequirement] = ...
location_requirements:    list[ExtractedRequirement] = ...
other_requirements:       list[ExtractedRequirement] = ...
```

`ExtractedRequirement` *does* carry `source_text: str | None`. A `list[str]`
element cannot.

**(b) Prompt.** STEP 2 mandates evidence for "every requirement object", while
STEP 6 constrains the skill arrays:

```text
- required_skills and preferred_skills contain PLAIN STRINGS ONLY. Use them
  strictly for named technical capabilities. Never put objects in them.
```

The mandate and the prohibition are in direct tension; the prohibition wins
because it is the output contract.

**(c) Canonicalisation.** `canonical_requirements` synthesises skill objects:

```python
[{"name": v, "description": None, "importance": importance,
  "years_required": None, "source_text": "", "category": "TECHNICAL"}
 for v in values],
type_hint="SKILL",
require_evidence=False,
```

`source_text` is hardcoded empty; `require_evidence` explicitly disabled.

**Reproduced:** 633/633 `SKILL` instances have empty `source_text` (100%); all
other types 0%. Raw extraction shows 580 bare-string skill items and 492 dict
items carrying `source_text` — the model complied, so this is a **contract
defect, not model omission**.

### V-2 — Skill importance is never adjudicated · **Verified**

```python
if value == "REQUIRED":
    if evidence and not (has_strong or has_weak):
        value = "PREFERRED"   # downgrade, gated on evidence existing
```

For a skill, `source_text=""` and `description` coerces to `""` via
`(_field(item,"description") or "")`, so `evidence = normalize_text(" ") = ""` —
falsy. **The downgrade never fires.** Demonstrated:

```text
validate_importance("REQUIRED","python","", "")     -> REQUIRED   (no adjustment)
validate_importance("REQUIRED","python","", None)   -> PREFERRED  (accidental:
    f"{''} {None}" == " None", a truthy normalised string)
```

The second row is a **latent bug**: passing `None` instead of `""` changes the
result purely through string formatting. No production path passes `None` today,
so it is dormant — and no test covers it.

**Net effect:** a skill's importance is entirely determined by which array the
model placed it in. Reproduced on `VJ-02`:

```text
run1: airflow=REQUIRED catboost=REQUIRED claude code=REQUIRED cursor=REQUIRED
      kubeflow=REQUIRED lightgbm=REQUIRED mlflow=REQUIRED xgboost=REQUIRED
run2: airflow=REQUIRED catboost=PREFERRED claude code=REQUIRED cursor=REQUIRED
      kubeflow=REQUIRED lightgbm=PREFERRED mlflow=REQUIRED xgboost=PREFERRED
run3: airflow=PREFERRED catboost=PREFERRED claude code=PREFERRED cursor=PREFERRED
      kubeflow=PREFERRED lightgbm=PREFERRED mlflow=PREFERRED xgboost=PREFERRED
```

These are the eight "importance transitions" V3.3 reported for `VJ-02`. They are
not re-readings of the posting's mandatory language. They are one array-placement
decision made en masse with nothing to adjudicate it.

### V-3 — Deduplication keys on classification · **Verified**

```python
return (normalize_requirement_name(req.name), req.category, req.importance,
        req.type, req.years_required, eligibility_class, work_condition_class)
```

Demonstrated: two requirements named `python` at REQUIRED and PREFERRED →
**output count 2**. Classification variance *multiplies* the requirement set
rather than converging. Direct mechanism for count inflation, which feeds the
score denominator (V-5).

### V-4 — Identity metric bundles selection and classification · **Verified**

`identity()` includes `importance` and `category`. A requirement present in all
three runs whose importance flipped counts as *identity-unstable*, so V3.3's
0/26 overstates pure selection instability. However V3.3 also computed
**name-set** stability (field 0 only) and obtained **0/26**, mean pairwise
Jaccard 0.3509. Selection instability is real independently. Both views are
retained (§8, §9.3).

### V-5 — Scoring is a weighted mean · **Verified**

```python
def _importance_weight(importance):
    REQUIRED -> 1.0 ; PREFERRED -> 0.45 ; SOFT_SIGNAL -> 0.05
    INFORMATIONAL -> 0.05 ; otherwise -> 0.65
```

Dimension scores are weighted means (`sum(s*w)/sum(w)`; `engine.py:502`,
`engine.py:783`). Overall is a clamped weighted sum at 0.40/0.25/0.10/0.10/0.15
mapped by thresholds 80/65/50 plus blocker → SKIP.

1. **Count sensitivity.** `VJ-B20` moved 20 → 2 → 1 requirements and
   48.40 → 76.15 → 76.08.
2. **Importance-weight sensitivity.** Moving one tool between skill arrays
   multiplies its weight by **2.22×** with **no change in posting text**.
3. **Unevidenced requirements carry full weight** despite having no evidence
   that they are requirements at all.

### V-6 — Output-token observations · **Verified observations only**

Historical facts, preserved without causal upgrade:

* 21 of 66 measured successful calls ended at exactly **3,072 output tokens**.
* The harness sends no `max_tokens`; the provider default applies.
* Three `400 json_validate_failed` records exist, each with empty
  `failed_generation`.
* **The causal relationship between these observations has not been
  established.**

### H-1 — The 3,072 ceiling causes the validation failures · **Hypothesis**

A sibling attempt surfaced the provider message *"max completion tokens reached
before generating a valid document"*, but that attempt succeeded on retry and
was never persisted. 3,072 is therefore an **observed clustering value, not a
verified limit** — which is precisely why D4 requires implementation-time
verification before pinning.

### H-2 — D2-A versus D2-B · **Hypothesis / unresolved**

Model-sampling variability (D2-A) and contract/decomposition ambiguity (D2-B)
are not separable from V3.3's evidence. V-1 to V-3 are *sufficient* to produce
substantial instability unaided, weakening the case that D2-A dominates — but
they do not eliminate D2-A.

---

## 3. Root-cause evidence versus hypotheses

| claim | class | basis |
| --- | --- | --- |
| Skills structurally cannot carry evidence | **Verified** | schema, prompt, canonicalisation; 633/633 observed |
| Skill importance is unadjudicated | **Verified** | gate inspected; flip demonstrated |
| Dedup splits on classification | **Verified** | key inspected; 2-in-2-out |
| Identity conflates selection/classification | **Verified** | `identity()` inspected |
| Score is count- and weight-sensitive | **Verified** | weights and weighted means inspected |
| `VJ-B20`/`VJ-02` swings trace to V-2/V-3 | **Strongly supported** | arithmetic consistent; not isolated by controlled test |
| 3,072 ceiling causes validation failures | **Hypothesis (H-1)** | clustering observed; causal link unestablished |
| D2-A contributes materially | **Hypothesis (H-2)** | not separable |
| Paraphrase/decomposition explains residual name churn | **Hypothesis** | not measured |

---

## 4. Current data flow and requirement lifecycle

```text
1  frozen posting    benchmark member -> source (collected.json or verified archive)
2  prompt build      REQUIREMENT_CONTRACT_PROMPT (5123 chars, frozen)
3  provider call     openai/gpt-oss-120b, temperature 0.1, no seed, json_object
                     NO explicit max_tokens -- provider default (V-6, D4)
4  parse             _json_completion -> json.loads -> ExtractedJobRequirements
5  coerce            coerce_requirements_payload: symmetric repair, every array
6  canonicalise      canonicalize():
                       name      -> normalize_requirement_name (deterministic)
                       evidence  -> evidence_ok; quote must occur in source_document
                       duration  -> declared, else recovered; text wins on conflict
                       category  -> declared if valid, else infer_category
                       importance-> validate_importance against own evidence
                       dedupe    -> _dedupe_key (INCLUDES importance+category)
7  engine input      canonical -> matching.types.Requirement
8  scoring           dimension weighted means -> overall -> thresholds -> recommendation
9  telemetry         tokens, attempts, raw+coerced+canonical retained
```

**Enforced invariants.** Quote must occur in the source or evidence is stripped
and importance cannot lean on it; declared duration contradicted by text loses
to the text; invalid category falls back to deterministic inference; out-of-enum
importance becomes UNKNOWN; duration is never invented.

**Not enforced.** That skills carry evidence (impossible); that skill importance
is evidence-derived (impossible); that dedup is independent of classification
(the opposite); that requirement count reflects posting content rather than
model choice.

**Uncertainties.** Whether repeatability improves once V-1 to V-3 are fixed;
whether name-set churn is paraphrase or omission; the true supported output
limit (D4).

---

## 5. Evidence contract (D1)

### 5.1 Four distinct questions — never conflated (amendment A3)

| # | question | check | automatable | recorded in | effect on `decision_eligible` |
| --- | --- | --- | --- | --- | --- |
| 1 | **Quote correspondence** | does the quoted text occur in the frozen posting? | **yes, fully deterministic** | `evidence_state` | `VERIFIED` is a **precondition** for eligibility |
| 2 | **Semantic support** | does that text support the requirement *as stated*? | **no — not safely** | `semantic_support` (separate field) | **none** — orthogonal to eligibility |
| 3 | **Classification support** | does the text justify the assigned category and importance? | **partially** — the mandatory/preference lexicon is deterministic; genuine ambiguity is not | `importance_adjudicated`, `category`, plus adjudication record | gates *which* importance may be asserted, not eligibility itself |
| 4 | **Decision eligibility** | may this requirement influence a recommendation under D1? | **yes** — derived purely from `evidence_state` | `decision_eligible` | is the eligibility flag |

**Governing rules.**

1. **A matching quote does not, by itself, establish semantic or
   classification support.** `EVIDENCE_VERIFIED` answers only question 1.
   Presenting quote presence as proof of support is the specific error this
   contract exists to prevent.
2. **No code path may set `semantic_support` to `SUPPORTED`.** Only a §11
   adjudication record may do so.
3. **Semantic support is orthogonal to eligibility.** An `UNADJUDICATED`
   requirement does **not** become ineligible, and an adjudicated `SUPPORTED`
   requirement does **not** become eligible. Eligibility tracks evidence
   correspondence under D1 and nothing else.
4. **Missing evidence never affects a recommendation silently** — through
   `decision_eligible = false` (§5.3), never through a hidden skill exemption.
5. **There is no hidden skill exception.** D1 is unconditional.

**What happens while `semantic_support` is `UNADJUDICATED`.** The requirement is
fully retained with its evidence, provenance and `importance_model`;
`decision_eligible` follows `evidence_state` alone; the run reports an explicit
`semantic_support_unadjudicated` count; and **no semantic-support rate may be
quoted from that run**. Semantic-support metrics (M7) are reported only over
adjudicated items, with their denominator stated (§9.3).

### 5.1.1 Explicit decision-eligibility rule (amendment A4)

**The question.** May a requirement with `evidence_state = EVIDENCE_VERIFIED`
and `semantic_support = UNADJUDICATED` influence a recommendation?

**The answer, stated as one rule rather than inferred from separate tables.**

| | rule | status |
| --- | --- | --- |
| **R-E1** | `decision_eligible = (evidence_state == EVIDENCE_VERIFIED)`. This is the **only** determinant. There is no second condition, no category carve-out, and no skill exemption. | **OPERATIVE** (see §5.1.3 for a proposed alternative awaiting approval) |

Applied to each downstream surface, under r3.2 as written:

| surface | may a VERIFIED + UNADJUDICATED requirement influence it? | authority |
| --- | --- | --- |
| **Requirement matching** (candidate-vs-requirement evaluation) | **YES** | R-E1 |
| **Candidate score calculation** | **YES** | R-E1 |
| **Blocker evaluation** | **YES** — a VERIFIED requirement may raise a blocker | R-E1 |
| **Final recommendation** (APPLY / APPLY_WITH_TAILORING / STRETCH / SKIP) | **YES** | R-E1 |
| Semantic-support metric M7 | **NO** — may not be reported for this item until adjudicated | §5.1, §9.3 |

The obligation is uniform across every requirement category. A SKILL, an
EXPERIENCE, an EDUCATION, a LOCATION, a WORK_CONDITION, a DOMAIN, an
ELIGIBILITY and a behavioural requirement are treated identically. **No implicit
exception exists for skills or any other category** (D1, §5.1 rule 5).

**Audit retention is unconditional.** Whether or not a requirement is
decision-eligible, and whatever its `semantic_support` value, the requirement
itself, its `source_text` and offsets, its `importance_model`, its
`category_model` and its full `Provenance` chain are retained, remain queryable,
and are available for later §11 adjudication, diagnostics, and dispute. Ineligibility
is never deletion and is never a downgrading of importance.

### 5.1.2 Recorded tension — sufficiency of evidence (decision required, not resolved here)

R-E1 makes quote correspondence the **operative** gate for recommendations. The
consequence must be stated rather than left implicit:

* Because `EVIDENCE_VERIFIED` is only a string-correspondence test (§5.2, A4
  above), a model can quote a genuine sentence from the posting and attach an
  unsupported claim to it. Under R-E1 that requirement **will** reach scoring,
  blocker evaluation and the final recommendation, with its claim never having
  been checked.
* §5.1 rule 1 already names this failure mode for semantic support; R-E1 makes
  it *operative for decisions*, not merely for reporting.
* D1's own wording — *"mandatory source evidence for every candidate-specific
  requirement entering decision-bearing use"* — states a **necessary** condition.
  It does not state that evidence is **sufficient**. R-E1's sufficiency is an
  inference drawn in r3.1, not something D1 asserts.

**This specification does not resolve that inference, because resolving it
changes eligibility semantics and is a policy decision, not a clarification.**
Both readings are recorded:

| option | rule | consequence | cost |
| --- | --- | --- | --- |
| **(a) Retain R-E1** *(operative default, unchanged from r3.1)* | eligibility from evidence alone | unadjudicated-but-verified claims can influence a recommendation | precision risk; the quote-presence gate is doing more work than "evidence" suggests |
| **(b) Require adjudication before decision use** | `decision_eligible = EVIDENCE_VERIFIED AND semantic_support != UNADJUDICATED` — *formulation **SUPERSEDED** by §5.1.3 (amendment A6), which refines it to `semantic_support == SUPPORTED`; still **NOT IN FORCE*** | every decision-bearing requirement has been human-checked for support | far fewer decision-bearing requirements until §11 adjudication runs; **a stricter reading of D1**, and changes decision semantics |

**Until a decision is recorded, option (a) remains operative**, because it is
D1 applied literally and nothing in r3.1 authorised a stricter rule. The
tension is recorded, not silently resolved. **This item is listed as a decision
requiring user input (§22.2, item 4).**

### 5.1.3 A4 decision record — option (b) REFINED to `SUPPORTED` only, RECOMMENDED, NOT YET OPERATIVE (amendments A5, A6)

**Status: PROPOSED. Pending explicit owner approval. This section changes no
current behaviour.**

**R-E1 above remains the operative rule.** Option (b) is recorded here as the
**recommended decision** and is **not in force**. It must not be implemented,
referenced as policy, or relied upon by any consumer until the owner confirms
it. The operative and proposed rules are kept distinguishable on purpose.

| | rule | status |
| --- | --- | --- |
| **Operative now (r3.2–r3.3, D1 literal)** | `decision_eligible = (evidence_state == EVIDENCE_VERIFIED)` | **IN FORCE** |
| **Proposed (option b, refined by amendment A6, awaiting approval)** | `decision_eligible = (evidence_state == EVIDENCE_VERIFIED AND semantic_support == SUPPORTED)` | **NOT IN FORCE** |

**Refinement note (amendment A6).** The r3.3 formulation of option (b) admitted
`SUPPORTED` **or** `PARTIAL`. It is **refined here to `SUPPORTED` only.**
This narrows the proposal; it does not activate it. Option (b) remains
**NOT IN FORCE** and R-E1 remains **IN FORCE**, exactly as in r3.3.

#### Proposed per-verdict qualification under option (b)

Using only §11.1's already-approved `R1 Semantic support` verdicts. **No state
is added, renamed, or removed; the §11 rubric is unchanged.**

| `semantic_support` | qualifies for decision-bearing use? | effect |
| --- | --- | --- |
| `SUPPORTED` | **YES** — may qualify, **subject to every other applicable gate** (evidence state, importance, completeness, and any future authorized gate) | decision-bearing use permitted |
| `PARTIAL` | **NO — by default** | **retained for audit and adjudication**; does not qualify |
| `NOT_SUPPORTED` | **NO** | retained for audit; does not qualify |
| `UNSURE` | **NO** | retained for audit; does not qualify |
| `UNADJUDICATED` | **NO** | retained for audit; does not qualify; no §11 record exists |

Under this proposal, `SUPPORTED` is the **only** qualifying value. `PARTIAL`,
`NOT_SUPPORTED`, `UNSURE` and `UNADJUDICATED` all fail the same condition.
Because `SUPPORTED` is the sole qualifier, the outcome does **not** depend on
how `UNSURE` is mapped into the field — a mapping gap recorded in §5.1.4 is
therefore not blocking for the rule itself, though it must still be settled by
the adjudication plan.

#### Why `PARTIAL` is excluded by default

**Partial support does not establish support for the entire extracted
obligation.** An extracted requirement is asserted as a single obligation on
the candidate. A `PARTIAL` verdict means the quoted passage supports *some* of
that obligation and not all of it. The un-supported remainder is not a minor
detail: it is part of the obligation that would be scored, could raise a
blocker, or could drive a SKIP.

Therefore a compound or partially supported requirement **must not
automatically** influence requirement matching, candidate score calculation,
blocker evaluation, or the final APPLY / APPLY_WITH_TAILORING / STRETCH / SKIP
recommendation **merely because some part of it is supported.** Support for a
fraction of an obligation is not support for the obligation.

**Scope limit — no splitting, no identity redesign.** This refinement does
**not** split compound requirements into supported and unsupported parts, does
**not** redefine requirement identity, does **not** alter the dedup key, and
does **not** create a partial-weight concept. A `PARTIAL` requirement remains
**one requirement**, ineligible as a whole. Resolving compound obligations by
splitting would be a data-model and identity change, and is **out of scope here
and not proposed.**

**What `PARTIAL` items keep.** The complete extracted requirement, its
`source_text` and offsets, its `Provenance` chain, its `importance_model` and
`category_model`, and its adjudication record are all **fully preserved** and
remain queryable. Exclusion is never deletion, silent omission, or a downgrade.
`PARTIAL` is a **decision-use** exclusion only, never an assertion that the
requirement is unimportant, irrelevant, or fabricated (§5.2.2, §5.2.1 rules 2
and 4).
* **Who or what may establish it:** only a §11 adjudication record, under the
  existing two-reviewer design (§11.2 independent first pass, §11.3
  disagreement resolution, §11.4 append-only audit trail). **No code path may
  set it** — this is already fixed by §5.1 rule 2 and is unchanged. **No new
  adjudication process is proposed, invented, or implied.**
* **Retention:** unaffected. A requirement excluded from decision-bearing use
  under option (b) remains fully retained with its `source_text`, offsets,
  `importance_model`, `category_model` and `Provenance` chain, and remains
  available for later adjudication (§5.2.2).
* **Importance:** unaffected. Option (b) must not be implemented as a downgrade
  to `INFORMATIONAL`, and must not be read as evidence that the requirement is
  unimportant or irrelevant. §5.2.1 rules 2 and 4 continue to hold.

#### Operational trade-off, corrected and stated plainly

**Correction to r3.3 (amendment A6).** r3.3 said option (b) "will leave fewer
requirements eligible." That understated the effect. **No §11 adjudication has
ever been conducted.** Every requirement therefore currently carries
`semantic_support = UNADJUDICATED`, and under the `SUPPORTED`-only rule
`decision_eligible` would evaluate to **false for every single requirement**.

The accurate consequence is therefore:

* Option (b) as proposed is **not a standalone switch.** Applied before any
  adjudication exists, it would leave the decision-bearing requirement set
  **empty**, and the engine would have nothing eligible to match, score, or
  raise a blocker against. A job could not reach any of APPLY,
  APPLY_WITH_TAILORING, STRETCH or SKIP on a decision-bearing basis.
* Option (b) is only meaningful **after** the §11 prerequisite in §5.1.4 has
  been completed under an approved plan. The prerequisite is a **hard
  dependency**, not a parallel workstream.
* The `SUPPORTED`-only refinement makes this stricter than r3.3's
  `SUPPORTED`-or-`PARTIAL` form: `PARTIAL` items, which might have carried some
  decision weight, now also fail. Coverage after adjudication will be lower
  than under the r3.3 form.
* Coverage is reportable and already specified: evidence coverage **M11**
  (§9.3), plus the `semantic_support_unadjudicated` count required by §5.1,
  reported with denominators over adjudicated items only.
* A large proportion of requirements showing as not-yet-decision-bearing is the
  **expected** consequence of an incomplete adjudication prerequisite. It must
  **not** be reported as extraction failure, and must **not** be silently
  dropped from denominators.

**This specification does not choose how much adjudication to perform, who
performs it, or in what order.** Those are §5.1.4 plan items requiring separate
authorization.

#### Approval gate

Adopting option (b) requires, in order: **(0)** completion of the §5.1.4
adjudication prerequisite under a separately authorized plan; **(1)** explicit
owner approval of this decision; **(2)** a separately authorized amendment that
makes the rule operative and reconciles every item in §5.1.5; and **(3)**
separate D7 authorization for any engine-side consequence.

**Steps 0–3 are none of them authorized by this amendment.** Until all four are
complete, option (a) / R-E1 governs.

### 5.1.4 Adjudication prerequisite for option (b) (amendment A6)

**Option (b) cannot become operative until the semantic-adjudication
prerequisite has been completed under an approved plan.** This is a **hard
blocking dependency**, recorded here so it cannot be overlooked at approval
time.

**No adjudication has been performed.** No §11 review has been conducted, no
reviewer judgment exists, and no `semantic_support` value other than
`UNADJUDICATED` is present anywhere in the corpus. This amendment **does not
authorize** adjudication, does not schedule it, and does not begin it.

The plan itself is a **separate, authorization-gated step**. It must specify the
following **before** any review begins. **None of these details is decided by
inference here:**

| # | must be specified by the plan | status |
| --- | --- | --- |
| 1 | **Approved scope and unit of adjudication** — which postings, which requirements, and what exactly constitutes one adjudicable unit (per requirement, per requirement pair, or per run) | **UNDECIDED — requires separate plan** |
| 2 | **Application of §11.2–§11.3** — how the existing two-reviewer independent first pass and the third-reviewer disagreement resolution apply to the chosen unit, including how `UNRESOLVED` items remain `UNADJUDICATED` (§11.3 rule 4) | **UNDECIDED — inherits §11 as written; unit choice from item 1 governs** |
| 3 | **Linkage to frozen requirements and provenance** — how each adjudication record binds to a specific requirement, its `source_text` and offsets, its `Provenance` chain, and the `source_sha256` snapshot (§11.4) | **UNDECIDED — requires separate plan** |
| 4 | **Coverage and unresolved reporting** — how coverage denominators, `UNSURE`, `PARTIAL`, `NOT_SUPPORTED` and `UNADJUDICATED` counts, and reviewer disagreement rate are reported (§11.5, M7, M11) | **UNDECIDED — requires separate plan** |
| 5 | **Frozen eight-posting limits** — how the diagnostic set's limits are respected and **not** expanded, and how results generalize from eight postings are bounded | **UNDECIDED — requires separate plan; set itself is unchanged** |

**Additional gap identified for the plan, not resolved here.** The specification
uses `semantic_support` values `UNADJUDICATED`, `SUPPORTED`, `PARTIAL`,
`NOT_SUPPORTED` and `UNSURE`, and §11.1 defines `R1` verdicts
`SUPPORTED` / `NOT_SUPPORTED` / `PARTIAL` / `UNSURE`. The specification does
**not** state the mapping from an §11 `R1` verdict to the stored
`semantic_support` field value — in particular whether an `R1` verdict of
`UNSURE` is stored as `UNSURE` or collapses to `UNADJUDICATED`, and how a
§11.3 `UNRESOLVED` item is stored. **The plan must state this mapping.** It is
not blocking for the `SUPPORTED`-only rule, because every non-`SUPPORTED` value
fails identically; it **is** blocking for metric denominators and for any later
`PARTIAL`-or-`UNSURE`-qualifying variant. **This amendment does not invent the
mapping.**

**Nothing in §5.1 authorizes a review.** A plan under item 1 requires separate
explicit authorization, and execution of that plan requires a further
authorization.

### 5.1.5 Operative statements option (b) would overturn (amendment A6)

Recorded so a later making-operative amendment cannot silently leave
contradictions behind. **These statements are operative and remain in force
now. None is amended by this pass.**

| # | location | operative statement now | status under option (b) if adopted |
| --- | --- | --- | --- |
| 1 | §5.1 rule 3 | "**Semantic support is orthogonal to eligibility.** An `UNADJUDICATED` requirement does **not** become ineligible... Eligibility tracks evidence correspondence under D1 and nothing else." | **directly contradicted** — under option (b) an `UNADJUDICATED` requirement *does* become ineligible |
| 2 | §5.1 table, question 2 | effect on `decision_eligible`: "**none** — orthogonal to eligibility" | **directly contradicted** |
| 3 | §5.1 table, question 4 | `decision_eligible` "**derived purely from `evidence_state`**" | **directly contradicted** |
| 4 | §5.2.1 concept table | decision eligibility "**derived solely from `evidence_state`**" | **directly contradicted** |
| 5 | §5.2.2 stage table | "Stage 3 is not stage 4... Under R-E1 stage 4 does **not** currently require stage 3" | would become **stage 3 required for stage 4** |
| 6 | §5.2 | "A requirement entering decision-bearing use must be `EVIDENCE_VERIFIED`" | still true but **no longer sufficient** |
| 7 | §5.1.1 R-E1 | "This is the **only** determinant" | **replaced** by the two-part rule |

**This is the substantive finding of amendment A6:** r3.3 recorded option (b)
without enumerating what adopting it would overturn. Adopting it is a **broader
policy change than one eligibility expression** — it reverses the orthogonality
principle stated in §5.1 rule 3, which is load-bearing across §5.1, §5.2.1 and
§5.2.2. The owner should weigh that breadth, not only the rule text.

### 5.2 Evidence states and assignment rules (D1 — no automatic exception)

Four evidence states, describing **only** quote correspondence (question 1).
Semantic support is **not** an evidence state and is deliberately absent from
this table; it lives in its own field (§5.1, question 2). **No fifth evidence
state is introduced.**

**What `EVIDENCE_VERIFIED` establishes — and what it does not (amendment A4).**

`evidence_state = EVIDENCE_VERIFIED` establishes **exactly one thing**: that the
text supplied in `source_text` occurs in the frozen posting. It is a
**string-correspondence test** — a deterministic substring/offset match against
the posting bytes identified by `source_sha256`.

It does **not** establish any of the following, and no downstream consumer may
read it as doing so:

* that the quoted passage expresses the extracted requirement;
* that the requirement exists as an obligation on the candidate;
* that the assigned category is correct;
* that the assigned importance is justified;
* that the requirement is complete or non-duplicative.

**A verified quotation can be a true quotation attached to a false claim.** The
posting contains many sentences; any of them can be quoted accurately. Quote
correspondence is therefore evidence that the model *cited* the posting, not
evidence that the claim is *true*. This is stated explicitly because
`EVIDENCE_VERIFIED` is the most easily over-read value in the model.

| state | assignment rule | `decision_eligible` |
| --- | --- | --- |
| `EVIDENCE_VERIFIED` | quote supplied **and** located in the frozen posting | `true` |
| `EVIDENCE_REJECTED` | quote supplied **and** checked **and** not located | `false` |
| `EVIDENCE_UNVERIFIED` | quote supplied but correspondence not established (e.g. legacy record) | `false` |
| `EVIDENCE_ABSENT` | no quote supplied | `false` |

**Axis note (amendment A3).** r3 listed `SEMANTIC_UNADJUDICATED` as a fifth row
of this table. That was ambiguous: it is a **semantic-support** value, not an
evidence-correspondence value, and its presence in the evidence table invited
reading it as an evidence state that could affect eligibility. It is **removed
from this table** and specified instead as the `semantic_support` field in
§5.1. The four approved evidence states are unchanged.

**D1 is unconditional.** There is **no automatic skill exception** and no
class-wide waiver. A requirement entering decision-bearing use must be
`EVIDENCE_VERIFIED`. This supersedes the r1 draft's "narrow declared exception"
for eligibility and work-condition facts; **no such exception exists.**

### 5.2.1 Evidence state, importance and eligibility are orthogonal (amendment A2)

Three distinct concepts must not be conflated. They are recorded in **separate
fields**, and no one of them implies another:

| concept | field | meaning | may it be destroyed by missing evidence? |
| --- | --- | --- | --- |
| **Evidence status** | `evidence_state` | the four states of §5.2 | n/a — this *is* the evidence status |
| **Extracted importance** | `importance_model` | what the model actually asserted, preserved verbatim | **no** — always retained for audit |
| **Adjudicated importance** | `importance_adjudicated` | the evidence-derived bindingness | **no** — becomes `UNRESOLVED`, not a downgrade |
| **Decision eligibility** | `decision_eligible` (derived) | may this requirement influence a recommendation | derived solely from `evidence_state` |

### 5.2.2 The four retention stages are distinct (amendment A4)

A requirement passes through four independent conditions. **None implies the
next**, and no stage may be used as a proxy for another:

| # | stage | question answered | field | value is about |
| --- | --- | --- | --- | --- |
| 1 | **Retained for audit** | is the requirement preserved with full provenance? | whole record | **storage and traceability** |
| 2 | **Evidence-verified** | does the quotation occur in the posting? | `evidence_state = EVIDENCE_VERIFIED` | **string correspondence only** (§5.2) |
| 3 | **Semantically adjudicated** | does the passage support the claim as stated? | `semantic_support` | **entailment** |
| 4 | **Eligible for decision-bearing use** | may it influence score, blocker or recommendation? | `decision_eligible` | **permitted influence** |

Consequences, all mandatory:

* **Stage 1 is unconditional.** Every extracted requirement is retained with its
  provenance regardless of stages 2–4.
* **Stage 2 is not stage 3.** A verified quotation may still be an unsupported
  claim; stage 2 says nothing about entailment (§5.2).
* **Stage 3 is not stage 4, and stage 4 is not stage 3.** Under R-E1 (§5.1.1)
  stage 4 does **not** currently require stage 3; the sufficiency question is
  recorded as an open decision in §5.1.2.
* **Exclusion from stage 4 is not deletion, silent omission, or a downgrade.**
  A requirement excluded from decision-bearing use keeps its
  `importance_model` and `category_model` unchanged, keeps its provenance, and
  stays available for later adjudication. §5.2.1 rules 2 and 4 remain in force.

Governing rules:

1. **Missing or invalid evidence cannot silently influence a recommendation.**
   `decision_eligible` is false for every non-`EVIDENCE_VERIFIED` state, so such
   a requirement cannot reach scoring by any path.
2. **The model's original importance and category remain auditable.**
   `importance_model` and `category_model` are never overwritten.
3. **Evidence ineligibility does not imply the requirement is unimportant.** An
   unquotable requirement may well be genuinely `REQUIRED`. Absent evidence means
   the *claim* is unproven, not that the *obligation* is weak. The adjudicated
   field therefore becomes `UNRESOLVED`, **never** a silent demotion to
   `INFORMATIONAL`.
4. **Ineligibility is not deletion.** The requirement, its
   `importance_model`, its `category_model` and its full `Provenance` chain are
   all retained and remain queryable.
5. **The scoring-engine implementation is outside the current authorization.**
   `decision_eligible = false` currently surfaces as a **blocking diagnostic**
   (D7), not as an engine change.

**Correction to r2.** r2 §5.3 rule 2 and r2 §8.3 step 3 specified that an
evidence-ineligible requirement is *"forced to `INFORMATIONAL`"*. That
conflated evidence status with importance: it silently overwrote a defensible
model assertion with a weak value, and destroyed information about what the
model believed. It is **superseded**. `importance_adjudicated` becomes
`UNRESOLVED` with a recorded reason; `importance_model` is untouched; and
eligibility is carried by the separate derived flag.

`INFORMATIONAL` retains its original, distinct meaning: the model itself
asserted a non-binding qualifier. It is no longer used as a sink for
unadjudicable requirements.

### 5.3 Ineligible requirements must not affect outcomes silently

An evidence-ineligible requirement (§5.2.1):

1. is **retained** in the canonical set and in all audit output — never dropped;
2. has `importance_adjudicated` set to **`UNRESOLVED`** with a machine-readable
   reason, while `importance_model` is preserved unchanged;
3. has `decision_eligible = false`, so it **cannot** influence scoring or a
   recommendation under the contract approved at stage 4 (D7) — and until that
   authorization exists, is surfaced as a **blocking diagnostic** rather than
   silently scored;
4. appears in a mandatory per-run **evidence-coverage** metric (M11);
5. can never, under any path, silently influence a score or recommendation.

Rule 3 is a **blocking dependency on separate authorization (D7)**, not an
implementation task for this specification. Rule 3's mechanism is fully
specified here; the engine change is explicitly not authorized and is not made.

### 5.4 Proposed representation (proposal, not implemented)

```python
# PROPOSAL — ExtractedJobRequirements@3. Not implemented; not imported.
class Evidence(BaseModel):
    state: str                       # VERIFIED | REJECTED | UNVERIFIED | ABSENT
    quote: str | None                # verbatim
    start: int | None                # deterministic char offset
    end: int | None
    reason: str | None               # why REJECTED / ABSENT

class ExtractedRequirementV3(BaseModel):
    name: str                        # model wording, preserved
    normalized_name: str | None      # filled deterministically downstream
    type: str                        # TECHNICAL|EXPERIENCE|EDUCATION|LOCATION|
                                     # WORK_CONDITION|DOMAIN|ELIGIBILITY|BEHAVIORAL
    importance: Importance
    category: str | None             # classification-only (see 9.2)
    years_required: float | None
    evidences: list[Evidence]        # multiple passages supported
    provenance: Provenance           # mandatory (5.5)

class ExtractedJobRequirementsV3(BaseModel):
    requirements: list[ExtractedRequirementV3]
    responsibilities: list[str]
    issues: list[str]
```

`required_skills` / `preferred_skills` survive only as a **derived, read-only
projection** for backward compatibility — never as model input. Importance is a
requirement field, not a property of an array (fixes V-2's root).

### 5.5 Provenance — mandatory

Every requirement carries:

```python
class Provenance(BaseModel):
    source_sha256: str        # sha256 of the frozen posting bytes
    run_id: int
    raw_index: int            # index in the raw model output array
    coerced_index: int | None # index after coercion, when it moved
    canonical_index: int | None
```

Traceability from any canonical requirement to the exact raw element and exact
posting bytes is **mandatory**. Multi-passage support: a requirement may hold an
ordered list of `Evidence`; each records its own offsets. One passage may
support several requirements — no exclusivity constraint.

### 5.6 Evidence acceptance criteria

1. Every candidate-specific requirement carries a located quote, or an explicit
   recorded `EVIDENCE_ABSENT`/`EVIDENCE_REJECTED` with a machine-readable reason.
2. No requirement asserts `REQUIRED` or `PREFERRED` while its evidence state is
   not `EVIDENCE_VERIFIED`.
3. `evidence_ok` (boolean) is removed; it cannot distinguish absence from
   rejection.
4. Offsets resolve for every `EVIDENCE_VERIFIED` quote; ambiguity is flagged, never
   guessed.
5. Semantic support is `SEMANTIC_UNADJUDICATED` unless a §11 review record exists.
6. Evidence-ineligible requirements are retained, demoted, and surfaced — never
   dropped and never silently scored.

---

## 6. Single-call extraction contract (D2)

Approach A is fixed: **one** richer structured extraction call per run.

### 6.1 Response contract

Versioned, and validated against §5.4's schema. Every element must satisfy the
§5.2 assignment rules. Structural validation is performed on the parsed object;
coercion may repair shape drift (as today) but **must not manufacture evidence
or importance**.

### 6.2 Safe handling of malformed, incomplete or truncated output

| condition | required behaviour |
| --- | --- |
| non-JSON body | record `MALFORMED_BODY`, extract **nothing**, do not partially accept |
| JSON parses, fails schema validation | record `SCHEMA_INVALID` with per-field errors; extract nothing |
| structurally valid, **completeness not establishable** | record `COMPLETENESS_UNVERIFIED`; the run **must not** be treated as exhaustive |
| valid but ends suspiciously (see §7.3) | record `POSSIBLY_TRUNCATED` |
| provider 4xx/5xx | record `PROVIDER_ERROR` with status and error code |
| valid and complete | record `COMPLETE` |

**Governing rule: a partially valid response must never be accepted as
exhaustive when completeness cannot be established.** Completeness is
establishable only when the model emits an explicit declared total that matches
the parsed element count, or emits a completion marker. Absent such a signal,
completeness is `UNVERIFIED` and the run is flagged.

### 6.3 Retry policy and attempt-level provenance

Retained behaviour: the frozen two-attempt retry loop, with each attempt
recorded. Every attempt persists:

```text
attempt_index, timestamp, outcome class, http status, provider error code,
input_tokens, output_tokens, total_tokens, usage_available, model, temperature,
prompt_sha256, schema_version, harness_fingerprint
```

A failed attempt is **retained** and remains visible in execution history; it is
never overwritten by a later success and never counted as a successful run.

**Explicit non-claim: a single call does not guarantee reproducibility.** One
call per run is a design choice for auditability and to avoid compounding
sampling variance. It does not make output deterministic. Reproducibility remains
the object of measurement, not an assumption.

---

## 7. Output budget and failure handling (D4)

### 7.1 Output limit — U-1 disposition (amendment A2)

**U-1: UNRESOLVED — BLOCKING.** (Downgraded from r3's "RESOLVED WITH CONDITION";
the condition was load-bearing and is now stated as the disposition.)

*Observation, verified from the frozen ledger:* across all 66 measured
successful calls,

```text
measured output_tokens : n=66   min=1121   max=3072
calls exactly at 3072  : 21/66
calls ABOVE 3072       : 0/66
distribution at >=3060 : {3072: 21}   -- a single point, nothing near it
```

These three facts are **observations**. They are kept strictly separate from
the two claims below:

| claim | class |
| --- | --- |
| 21 of 66 calls ended at exactly 3,072 output tokens, and none exceeded it | **Verified observation** |
| A hard output ceiling at 3,072 *caused* that clustering | **Hypothesis (H-1)** — consistent with the distribution, not established by it |
| 3,072 is the provider's documented maximum for this model/tier | **Not established.** No repository artifact records it |

A pile-up at exactly one value with nothing above it is *consistent with* a hard
censoring boundary. It is **not** proof of one: a shared implicit default, a
model-side generation habit, or an unrelated constraint producing the same
signature cannot be excluded from repository evidence alone. r3's phrasing
("is the signature of") overstated this and is corrected here.

*What is missing:* the authoritative figure. The ledger contains no
`max_tokens`, `max_completion_tokens`, `context_length` or model-metadata
field, and the blind review pack contains no model metadata. Resolution
requires one of: provider documentation for the exact endpoint/model/tier; or a
non-inference capability/metadata endpoint; or one explicitly authorized live
call. Options 1 and 2 require no inference and are preferred.

**U-1 remains blocking.** No output limit may be pinned while this is open.

### 7.2 Configuration location and request semantics — U-2, U-5 (amendment A2)

**U-2a: RESOLVED — client request behaviour.** Verified by direct inspection of
`apps/api/app/ai/openai_provider.py::_json_completion` (the single provider call
site) and the installed SDK:

```text
verified source location : apps/api/app/ai/openai_provider.py::_json_completion
request sets max_tokens            : False
request sets max_completion_tokens : False
request sets max_output_tokens     : False
openai SDK version                : 3.24.0
SDK chat.completions.create accepts: max_completion_tokens, max_tokens
both parameters default to Omit (not sent) : True
parameters actually sent by _json_completion : model, temperature,
                                     response_format, messages
```

The current client sets **no** output-limit parameter. The effective limit is
therefore entirely provider-determined. This is a closed question.

**U-2b: UNRESOLVED — BLOCKING — provider parameter semantics.** Whether the
configured endpoint honours `max_completion_tokens`, the deprecated
`max_tokens`, or neither, and what each does when supplied, is a property of the
**endpoint's** API contract for the exact model and tier. It is not observable
from the repository: the client never supplies either parameter, so no
historical artifact records endpoint behaviour under either.

Resolution requires authoritative documentation for
`https://api.groq.com/openai/v1` chat-completions with model
`openai/gpt-oss-120b` on the account's tier, or one explicitly authorized live
call. **No provider call or live test was performed in this pass.**

**Dependency U-1 ↔ U-2b.** Both must close before a limit is pinned, and they
are independent:

* U-1 answers **"what is the maximum?"**
* U-2b answers **"how do we ask for it, and will the request be accepted?"**

Pinning a value without U-1 risks exceeding the true maximum and producing
rejected or truncated requests. Supplying that value without U-2b risks
requesting it through a parameter the endpoint ignores — silently reintroducing
the very provider-determined ceiling U-1 is trying to make explicit. Either gap
alone blocks pinning, and a stage-1 gate closes only when **both** are closed.

**U-5: RESOLVED.** The configuration architecture has a single established
precedent, and the output limit should follow it exactly rather than introduce a
second source of truth:

```text
.env  ->  app.core.config.Settings  (pydantic BaseSettings, env-driven)
            ->  matching/config.py frozen dataclasses (MatchWeights,
                RecommendationPolicy, MatchSettings)
                via  app.services.matching.build_settings()
            ->  recorded on every run / every outcome
```

`build_settings()` already demonstrates the pattern end to end: a
`threshold_*` field on `Settings` is injected into the frozen
`RecommendationPolicy`. The output limit belongs in the same flow — an
`ai_max_output_tokens`-style field on `Settings`, consumed by an extraction
settings object, recorded per run. `MatchWeights`,
`RecommendationPolicy` and `MatchSettings` are all `frozen=True`, so the limit
cannot be mutated after construction.

*Validation requirements.* The value must be a positive integer; it must be
recorded on every run record as `output_token_limit` alongside `model`,
`prompt_sha256`, `schema_version` and `harness_fingerprint`; and a run whose
recorded limit differs from the currently configured limit must be reported as
**non-comparable**, not silently pooled.

*Source of truth:* `.env` / `Settings`, exactly as thresholds are today. No
second configuration location is introduced.

### 7.3 Response classification and truncation — U-3 (amendment A2)

**U-3: RESOLVED.** Safe failure behaviour, by inspection class. The
implementation must distinguish exactly these five outcomes:

| class | what the implementation inspects | safe behaviour |
| --- | --- | --- |
| **complete, valid** | parses as JSON; validates against the v3 schema; and the model's declared total (when emitted) equals the parsed element count | usable as exhaustive |
| **malformed** | body is not parseable JSON, or parses but fails schema validation | extract **nothing**; record per-field errors; **never** partially accept |
| **explicitly length-limited** | provider response carries an explicit finish-reason/stop-indicator of `length`, or an equivalent provider field | record `EXPLICITLY_TRUNCATED`; **never** treat as exhaustive |
| **syntactically valid, exhaustiveness unestablished** | parses and validates, but no declared total is available to confirm completeness | record `COMPLETENESS_UNVERIFIED`; **must not** be treated as exhaustive (§6.2) |
| **provider error** | non-2xx HTTP status, or SDK exception | record `PROVIDER_ERROR` with status and provider error code |

Additional detection heuristic, clearly labelled as heuristic: if
`usage.output_tokens` equals the pinned limit **exactly**, raise
`POSSIBLY_TRUNCATED` for inspection. This is **not** proof of truncation and
must never be asserted as such.

**Governing non-claim: syntax validation does not prove exhaustiveness.** A
response can be perfectly well-formed JSON that silently omits requirements.
Only an explicit declared total (or an equivalent provider signal) can
establish completeness; absent one, completeness is `UNVERIFIED`.

**Recovery.** Any re-attempt is recorded as a **separate attempt** with its own
outcome class, usage telemetry and timestamp (§6.3). A truncated or incomplete
first attempt is never overwritten by a successful retry, and a successful
retry is never presented as evidence that the first attempt was exhaustive.

**No provider call or live test was used to settle this** — the rules are
derived from the recorded attempt history and the schema, and are testable
offline against the three preserved `400 json_validate_failed` records.

### 7.4 Historical facts preserved without causal upgrade

```text
21 of 66 measured successful calls ended at exactly 3,072 output tokens
3 historical HTTP 400 json_validate_failed records (empty failed_generation)
causal relationship between these: NOT ESTABLISHED
```

These remain observations. The specification does **not** claim the ceiling
caused the failures, and implementation must not treat that claim as settled.

---

## 8. Identity, canonicalisation and classification contract (D3)

### 8.1 Identity-defining vs classification-only attributes

| category | attributes | rationale |
| --- | --- | --- |
| **identity-defining** | normalized name, years_required, eligibility class, work-condition class | attributes that distinguish *what is being asked of the candidate* |
| **classification-only** | importance, category, **type** | how binding / which discovery bucket / which array the model used — **must not partition identity** |

**U-4: PROVISIONAL — NOT VALIDATED (amendment A3).** r3 recorded this as
"resolved" on the strength of one example. That overclaimed. The three layers
are separated below.

**(a) Observed historical behaviour — Verified.**

* `extraction.py::_TYPE_HINT` maps the **array key** to the type:
  `experience_requirements→EXPERIENCE`, `education_requirements→EDUCATION`,
  `location_requirements→LOCATION`, `other_requirements→OTHER`, skills
  `→SKILL`. `type` is therefore a function of **which array the model chose**.
* Across all 26 benchmark jobs, **16** requirement names change `type` between
  runs of the same posting. `VJ-B19 healthcare and/or claims adjudication
  experience` shows type `EXPERIENCE/EXPERIENCE/OTHER` with category
  `DOMAIN/DOMAIN/DOMAIN` — one obligation, three type values.

This establishes that **`type` is unstable across runs** and that its
instability tracks array placement. It does **not** establish that every
capability-versus-experience distinction is merely classification.

**(b) Proposed design rule — not yet validated.**

`type` is classification-only, excluded from the identity key (§8.1 table).
The rationale is narrow and defensible: an attribute that varies with which
prompt array the model filled is a classification artefact, and letting it
partition identity converts one obligation into several.

**(c) Evidence needed to validate the general rule — not available.**

The open question is narrow and specific: when a posting states a capability
("Python") and the model also emits an experience with it ("3+ years Python"),
is `SKILL` versus `EXPERIENCE` ever a *material* difference in obligation, or
only a difference in how the model filed it? The frozen diagnostic set was
measured for this and **cannot settle it**:

```text
type-transition pairs inside the frozen eight-posting set : 4
  ... of which SKILL<->EXPERIENCE (capability vs experience): 0
  the 4 are all OTHER<->EXPERIENCE behavioural/emotional text (VJ-B04)
all-26 type-transition pairs                              : 16
  of which SKILL<->EXPERIENCE                             : 10
coverage: the frozen eight set contains 4/16 = 25.0% of type
          transitions and 0/10 = 0.0% of capability-vs-experience cases
```

**r3's claim that the §11 rubric could settle this "inside the frozen
eight-posting set" was factually wrong** and is withdrawn: there are zero
`SKILL`↔`EXPERIENCE` pairs in that set.

**Resolution path, respecting the frozen set.** The eight-posting *diagnostic*
set is not expanded. Resolution requires §11 `R4 DISTINCT_OBLIGATION`
adjudication on `SKILL`↔`EXPERIENCE` pairs **as they arise** during the
diagnostic run, or a separately authorized review over cases outside the
diagnostic set. If no such pair arises within the eight postings, the question
**remains open after the diagnostic** and must be returned for decision — it
must not be closed by assumption.

**Risk if the provisional rule is wrong in the permissive direction.** Two
materially different obligations sharing a normalised name, no stated duration,
and differing only in capability-versus-experience framing would **merge**.
Mitigation without a threshold: `years_required` and the deterministic
`infer_category` output remain identity-defining or classification-determining
respectively, and §11 R4 exists precisely to catch such pairs. **Risk if wrong
in the restrictive direction** (keeping `type` in identity): re-inflates
requirement counts and re-creates V-3, which is Verified.

**Implementation readiness.** Stage 3 may proceed on the **narrow** basis that
array-derived `type` must not partition identity (Verified). Stage 3 may **not**
assert a universal capability-versus-experience rule until adjudicated. The
general rule is **PROVISIONAL — NOT VALIDATED**, which is a weaker status than
r3 recorded and does not block the narrow fix.

**Treatment of similar wording representing distinct obligations.** Two
requirements merge only when their **identity-defining** attributes coincide
**and** their quotes are not materially distinct obligations. Where wording is
similar but the quoted text imposes materially different obligations, they
**remain distinct** and are recorded as a `DISTINCT_OBLIGATION` pair with both
quotes retained. This is a **recorded human-reviewable signal**, not an
automatic semantic merge.

**No embeddings. No fuzzy-similarity thresholds. No unapproved semantic-merge
behaviour.** Canonicalisation remains deterministic string normalisation. A
similarity threshold would create an untestable boundary drifting with corpus
statistics — the class of defect this project exists to eliminate.

### 8.2 Deduplication (D3)

```python
# PROPOSAL — not implemented
def identity_key(req):
    return (normalize_requirement_name(req.name), req.type,
            req.years_required, eligibility_class(req), work_condition_class(req))
    # importance and category deliberately EXCLUDED (fixes V-3)
```

Merging must **preserve provenance for every occurrence**:

```python
class CanonicalRequirementV3:
    ...
    merged_occurrences: list[Provenance]   # one entry per raw element absorbed
```

Requirements: (a) identity consolidates first; (b) **all** merged provenance is
retained; (c) genuinely distinct requirements survive merging; (d) the merge
count is reported per run as a diagnostic.

### 8.3 Classification adjudication after consolidation

Importance and category are resolved **once, after** identity consolidation:

1. consolidate by identity key, retaining all provenance;
2. resolve category deterministically from the requirement's own text via
   `infer_category` (model-declared category is **advisory only** — this is the
   V-3/V-4 countermeasure, since V3.3's 12 category transitions tracked array
   choice rather than posting content);
3. adjudicate importance from consolidated evidence:
   - `EVIDENCE_VERIFIED` → evidence-derived classification permitted, recorded in
     `importance_adjudicated`;
   - any other state → `importance_adjudicated` = **`UNRESOLVED`** with a recorded
     reason, `importance_model` preserved unchanged, `decision_eligible = false`
     (§5.2.1). **Not** a silent demotion to `INFORMATIONAL`;
4. apply the V-2 fix: `validate_importance` must **refuse to assert**
   `REQUIRED`/`PREFERRED` when no verified evidence exists, and must normalise
   `None` and `""` identically before comparison (closes the latent bug).

### 8.4 Historical versus corrected identity reporting

Both definitions are reported for every job, always labelled:

```text
historical identity  : the frozen 7-field V3.3 definition (unchanged)
corrected identity   : identity-defining attributes only (selection identity)
classification view  : corrected identity + importance + category
```

V3.3 results are **never recomputed under the corrected identity and presented as
if they had been produced by the corrected contract.**

### 8.5 Decomposition contract (carried from r1, unchanged)

A requirement is **atomic** when it names exactly one capability, duration,
qualification, condition, or domain.

| construction | rule |
| --- | --- |
| "Python and SQL required" | one requirement per named capability, sharing the sentence quote |
| "Python, R, or Scala" | one requirement per item |
| "5+ years in X" | one requirement; duration in `years_required` |
| "LangChain for RAG" | one requirement unless the posting states each independently |
| "strong communicator who mentors" | two requirements — independently assessed |
| employer marketing, "about us" | not a requirement |
| responsibilities without expectation | not a requirement source |

`responsibilities` is retained for reporting but is **explicitly not** a
requirement source; converting responsibilities into requirements contributed to
V3.3 count inflation.

### 8.6 Acceptance criteria

1. Feeding one name at two importances yields **one** canonical requirement.
2. Every merged requirement lists one `Provenance` per absorbed raw element.
3. Materially distinct obligations with similar wording remain distinct and are
   flagged `DISTINCT_OBLIGATION`.
4. Category is never derived from importance or array membership.
5. Importance is never `REQUIRED`/`PREFERRED` without `EVIDENCE_VERIFIED`.
6. `description=None` and `description=""` produce identical importance outcomes.
7. Reports carry both identity definitions, labelled.

---

## 9. Evaluation plan

### 9.1 Two views, always both

**View 1 — exact identity agreement.** Strict set comparison under the labelled
identity definition. Automatable.

**View 2 — adjudicated semantic agreement.** Two differently-worded requirements
are judged to express the same underlying requirement **only** by the §11 review
protocol, recording pair, verdict, reviewer, date and confidence. Adjudicators
see both requirement texts, both quotes, and the source posting. **The model's
own output is never treated as ground truth.**

Paraphrase/decomposition differences are thereby *measured*, not inferred from a
low similarity score.

### 9.2 Metric separation

`category` (discovery bucket) and `importance` (bindingness) are reported as
separate dimensions and never combined into one "classification" score in
reporting, even where a metric aggregates them.

### 9.3 Metrics, with denominators and missing-data rules

| # | metric | definition | denominator | missing data |
| --- | --- | --- | --- | --- |
| M1 | count stability | runs with equal canonical counts | 26 jobs | job excluded **and reported** if any run missing |
| M2 | selection-identity stability | runs with equal identity-defining sets | 26 jobs | as M1 |
| M3 | classification-identity stability | runs with equal sets incl. importance/category | 26 jobs | as M1 |
| M4 | presence/absence | names in all 3 / exactly 2 / exactly 1 | unique names in union | reported with the union, never substituted |
| M5 | classification agreement | aligned requirements with identical importance and category | aligned requirements (present in >=2 runs) | unalignable names reported separately, **never** counted as agreement |
| M6 | quote correspondence | quotes located in the frozen posting | requirements **carrying a quote** | no-quote requirements reported as a **coverage** metric, **not** as correspondence failures |
| M7 | semantic support | requirements adjudicated supported | requirements submitted for adjudication | unadjudicated reported `UNADJUDICATED` |
| M8 | score stability | runs with equal scores; range distribution | 26 jobs | as M1 |
| M9 | recommendation stability | jobs whose three recommendations agree | 26 jobs | as M1 |
| M10 | correctness | agreement with independently adjudicated human labels | adjudicated labels | **unavailable until labeling occurs; no proxy may be substituted** |
| M11 | evidence coverage | requirements in `EVIDENCE_VERIFIED` | all canonical requirements | reported always; D1 makes this a primary gate |

The M6/M7 split is deliberate: V3.3's "633 without evidence" and "43 quotes not
found" answer different questions and must not share a denominator.

### 9.4 Change-control ledger

Every run record must carry: contract version, schema version, prompt sha256,
provider, model id, temperature, seed presence, engine sha256, config sha256,
source sha256, candidate profile sha256, **output token limit** (D4), and a
harness/environment fingerprint. Any change invalidates comparability and must
be recorded, so provider/model drift can never be mistaken for within-contract
repeatability.

### 9.5 Rationale for staged evaluation

The previous experiment was designed to detect a large effect and succeeded.
Re-running 26 × 3 (~66 calls, several quota windows) is only justified after the
deterministic gates pass, because the diagnostic set (§10) targets the observed
failure archetypes at a fraction of the cost.

---

## 10. Diagnostic protocol (D5)

**Exactly eight postings, fixed:**

```text
VJ-B04   VJ-B11   VJ-B14   VJ-B20   VJ-B23   VJ-B28   VJ-02   VJ-03
```

### 10.1 Why these eight

Selected because they span the observed failure archetypes: skill-heavy
decomposition (`VJ-B20`), count/recommendation inversion (`VJ-B11`), evidence and
decomposition variance (`VJ-B04`), recovery history (`VJ-B14`), count variance
with stable decision (`VJ-B23`, `VJ-B28`), tool-mass classification flip
(`VJ-02`), and count-stable identity-unstable (`VJ-03`).

### 10.2 Intended diagnostic questions

1. Does the corrected contract produce `EVIDENCE_VERIFIED` for previously
   unevidenced SKILL requirements?
2. Does dedup no longer split on classification?
3. Is selection-identity stability materially improved?
4. Do importance transitions persist once importance is evidence-derived?
5. Does the `VJ-B20`-class count collapse disappear?
6. Does the output budget permit the richer schema without truncation?

### 10.3 Comparisons and artifacts

3 runs per posting (24 calls). Artifacts per run: raw response, coerced payload,
canonical requirements with evidence states and offsets, provenance chain,
identity keys under both definitions, per-run telemetry, attempt history.
Report must include M1–M11 for the eight, and the completeness/
truncation classification of every response.

### 10.4 Reproducibility metadata

Per §9.4, plus explicit declaration that these are **diagnostic** results under a
**new** contract version, not benchmark measurements.

### 10.5 Mandatory reporting boundary

> **Results from eight selected postings cannot establish benchmark-wide
> reproducibility or correctness.** They are diagnostic. No rate, proportion or
> "pass" claim may be extrapolated to the 26-case benchmark, and no correctness
> claim may be made at all while M10 is unavailable.

### 10.6 Not authorized here

The diagnostic has **not** been run. D5 fixes the set and the protocol; execution
requires separate authorization.

---

## 11. Semantic-support review protocol (D6)

Design only. **This section does not authorize conducting reviews, recruiting
reviewers, assigning cases, or labeling data.**

### 11.1 Rubric

For each requirement pair presented for review, the reviewer records a verdict
against four questions:

| dimension | question | permitted verdicts |
| --- | --- | --- |
| **R1 Semantic support** | does the quote entail the requirement as stated? | `SUPPORTED` / `NOT_SUPPORTED` / `PARTIAL` / `UNSURE` |
| **R2 Explicit vs inferred** | is the requirement explicit in the posting, or inferred? | `EXPLICIT` / `INFERRED` / `UNSURE` |
| **R3 Classification support** | does the quote justify the assigned type and importance? | `JUSTIFIED` / `NOT_JUSTIFIED` / `UNSURE` |
| **R4 Distinct obligation** | do these two items impose materially different obligations on the candidate? | `SAME_OBLIGATION` / `DISTINCT_OBLIGATION` / `UNSURE` |

`UNSURE` is a first-class verdict. It is never coerced into a binary.

### 11.2 Independent initial judgments

Two reviewers independently review every item with **no visibility of each
other's judgments** during initial pass. Each judgment records: reviewer id,
timestamp, the four verdicts, a free-text justification quoting the posting, and
a confidence value in {low, medium, high}.

### 11.3 Disagreement resolution

On any dimension where the two initial judgments differ (including one
`UNSURE` against one decided verdict):

1. both judgments are **retained verbatim**; neither is overwritten;
2. a third reviewer adjudicates, seeing both judgments and the source;
3. the adjudicator records `AGREED` (with the converged verdict) or
   `UNRESOLVED`;
4. `UNRESOLVED` items are reported as `UNADJUDICATED` in all metrics and are
   **never** silently assigned the majority or the model's value.

### 11.4 Audit trail

Per item: both initial judgments, the adjudication if any, rubric version,
reviewer ids, timestamps, and the source snapshot sha256. The trail is
append-only. Reviewer disagreement rate is itself reported — it is a measure of
requirement ambiguity, not a defect to be smoothed away.

### 11.5 Reporting

M7 and M8 report adjudication denominators explicitly. `UNADJUDICATED` is
reported as a count, never excluded silently. Semantic-support rates are
reported **separately from** quote-correspondence rates (§5.1).

---

## 12. Score and recommendation sensitivity

### 12.1 Verified mechanism

Dimension scores are weighted means; weights are importance-derived
(REQUIRED 1.0, PREFERRED 0.45, SOFT_SIGNAL/INFORMATIONAL 0.05); overall is a
clamped weighted sum at 0.40/0.25/0.10/0.10/0.15 mapped at 80/65/50 with
blocker → SKIP.

### 12.2 Case readings

| case | observation | mechanism (class) |
| --- | --- | --- |
| `VJ-B20` | 20 → 2 → 1; 48.40 SKIP → 76.15/76.08 APPLY_WITH_TAILORING | weight-1.0 unmatched requirements leave a weighted mean; mean rises sharply. **Strongly supported** |
| `VJ-B11` | 23 → 32 → 9; 52.57 → 44.38 → 69.20 | same mechanism, non-monotone in count, so additions also depress. **Strongly supported** |
| `VJ-B12` | 17 → 9 → 19; 52.58 → 76.29 → 52.77 | score tracks count almost monotonically. **Strongly supported** |
| `VJ-02` | 16 → 19 → 25; 55.70 → 48.35; 8 tools flipped en masse | importance weight 0.45 → 1.0 is a 2.22× change with no posting change (V-2). **Verified mechanism**, attribution **strongly supported** |
| `VJ-B15` | 10 → 10 → 13; 61.45 → 61.45 → 49.58 | identical scores then a decision change; mean crossed 50. **Strongly supported** |
| `VJ-B23` | 8 → 11 → 16; SKIP throughout | count doubled, score stayed in one band. **Verified observation** |

`VJ-B20` and `VJ-B23` together: **count volatility and decision volatility are
related but not deterministically.** Any design assuming "fewer requirements is
safer" or normalising by count is unsupported by this evidence.

### 12.3 Assessment

The system is sensitive to requirement count (**Verified**), to classification
(**Verified**), and therefore to extraction instability (**Verified**). Missing
evidence does not reduce weight — unevidenced skills carry full weight, the
sharpest form of this defect (**V-1** + **V-5**).

### 12.4 Protective measures — diagnostics only

1. Expose per-run diagnostics: requirement count by type, evidence-coverage rate
   (M11), unevidenced weight share, dedup merge count, `DISTINCT_OBLIGATION`
   count, importance-change count relative to the posting's language.
2. Evidence-coverage below the D1 threshold is a **review trigger**, never a
   silent score rescale.
3. Decision-stability telemetry so instability is visible in production.

### 12.5 Explicitly forbidden here (D7)

Changing weights, thresholds, blocker policy or dimension aggregation; adding a
confidence multiplier; normalising by requirement count. Each is a separate
decision requiring its own evidence. **Score changes must not be used to
conceal unstable extraction** — doing so would hide the defect and destroy the
ability to detect it.

---

## 13. Engine-consumer scope exclusion (D7)

Matching-engine integration, scoring changes, recommendation-threshold changes
and blocker changes are **outside this specification and outside this
amendment**. The engine remains frozen.

### 13.1 Downstream questions for a future, separately authorized review

Recorded as questions, **not answered here**:

1. Should `EVIDENCE_REJECTED` / `EVIDENCE_ABSENT` requirements be excluded from
   scoring entirely, or admitted at `INFORMATIONAL` weight?
2. Should evidence coverage influence the overall score, or only gate
   recommendation?
3. Should a job whose evidence coverage falls below a threshold be withheld from
   recommendation and routed to review?
4. Should the blocker policy treat unevidenced location/work-condition
   requirements differently?
5. What is the correct aggregation when the requirement set is known to be
   incomplete (`COMPLETENESS_UNVERIFIED`)?
6. Should score normalisation by requirement count ever be introduced, given
   §12.2 shows count and score are not monotonic?
7. Do the thresholds 80/65/50 remain appropriate once extraction is stable?

Answering any of these requires modifying engine behaviour, which is
**unauthorized**. They are recorded for that future review only.

---

## 14. Historical limitations and comparability (D8)

**Preserved without reconstruction.** Twelve early V3.3 runs (the `VJ-B01`
through `VJ-B04` triplets) lack `raw_extraction` and `coerced_extraction`
because retention was introduced after those runs. Consequently:

1. Raw-to-canonical divergence **cannot** be analysed for those 12 runs.
2. The missing payloads are **not** reconstructed, inferred, approximated or
   implied to exist.
3. Every report must state this limitation wherever it compares raw and
   canonical layers.
4. Those 12 runs are marked `RAW_PAYLOAD_UNAVAILABLE` in any derived artifact.

**Comparability rule.** Reports must distinguish historical V3.3 results from
future corrected-contract results. V3.3 is reported under the frozen identity
and the frozen schema version; corrected-contract results under the corrected
identity and the new schema version. New extraction results are **never**
substituted into a V3.3 table, and missing historical data is never imputed.

---

## 15. Architecture and migration

| concern | effect | handling |
| --- | --- | --- |
| Schema | breaking: two-tier → single list | `ExtractedJobRequirements@3`; **both versions parseable** during transition |
| Stored artifacts | V3.3 lacks skill evidence and 12 raw payloads (D8) | v2 reader retained; no backfill |
| Raw retention | must be unconditional | retention is a pre-execution concern |
| Canonical persistence | evidence enum, offsets, provenance | additive fields; v2 readers ignore unknown fields |
| Evidence references | offsets primary; substring fallback for legacy | both retained |
| Historical comparison | V3.3 under frozen identity; V3.4 under corrected | **both reported, labelled** (§8.4) |
| Benchmark fixtures | unchanged, must remain so | referenced by sha |
| Matching inputs | evidence/offset/provenance optional | engine **must not** consume them before D7 authorization |
| API contracts | response shape changes | versioned; consumers updated in the same change or explicitly deferred |
| Observability | diagnostics + stability telemetry | structured, per-run, queryable; no secrets |
| Error handling | evidence mandatory | failure is a **recorded state**, never an exception; one bad element must not void a whole extraction |
| Backward compatibility | — | dual-read, single-write-new; v2 artefacts immutable |

### Versioning rule

`contract_version` and `schema_version` are mandatory on every run and every
canonical requirement. A V3.3 record is interpretable only under
`ExtractedJobRequirements@2` + frozen identity; a V3.4 record only under v3 +
corrected identity. **No V3.3 artifact is rewritten, migrated in place or
reinterpreted.**

---

## 16. Alternatives considered and trade-offs

| alternative | why rejected |
| --- | --- |
| Keep skills as strings; importance from array | preserves V-1 and V-2 exactly; the status quo |
| Prompt-only fix | cannot override a schema forbidding objects in those arrays; unenforceable |
| Two-stage extract-then-resolve | adds a second unstable call and a silent-drop failure mode |
| Embedding / fuzzy dedup | untestable threshold drifting with corpus statistics; unquantifiable failure cases |
| Aggressive deduplication | masks count inflation rather than removing its cause; `VJ-B20`'s 2 and 1 are near-collapses, not duplicates |
| Score normalisation by count | `VJ-B23` shows count and score are not monotonic; encodes a false model |
| Raise the output ceiling | may reduce `400` failures (H-1) but does not touch V-1 to V-3; and 3,072 is not a verified limit (D4) |
| Skill exception for eligibility/work-condition facts | **removed by D1** — no automatic exception |
| Ship without semantic adjudication | asserts support the pipeline cannot establish |
| Migrate V3.3 data to v3 | destroys the historical baseline |

---

## 17. Acceptance and rejection criteria

### 17.1 Acceptance criteria for a future implementation

1. Every candidate-specific requirement carries a located quote or an explicit
   recorded non-verified state with a reason. **No automatic exception (D1).**
2. Evidence state is a four-valued enum; `evidence_ok` is gone.
3. No requirement asserts `REQUIRED`/`PREFERRED` without `EVIDENCE_VERIFIED`.
4. Evidence-ineligible requirements are retained, demoted, surfaced, and never
   silently scored.
5. Dedup key is independent of importance and category; one name at two
   importances yields **one** output.
6. Every merged requirement retains one `Provenance` per absorbed raw element.
7. Materially distinct obligations with similar wording remain distinct and are
   flagged.
8. Offsets resolve for verified quotes; mismatches flagged, never guessed.
9. Semantic support is `SEMANTIC_UNADJUDICATED` unless a §11 record exists.
10. Selection and classification identity are reported separately, both
    definitions labelled.
11. Output token limit is **verified** before pinning, configured in one place,
    recorded per run.
12. Truncation is flagged, never asserted.
13. Every run records the §9.4 change-control set.
14. Raw, coerced and canonical payloads retained for **every** run.
15. A V3.3-era report re-run under new code reproduces the frozen V3.3 numbers
    **bit-for-bit**.
16. Deterministic unit suite green; no existing frozen test weakened.
17. Benchmark, labels, blind pack, ledger and prior analysis unchanged by sha.

### 17.2 Rejection criteria

1. Any matching-engine change bundled into an extraction-contract change (D7).
2. An automatic skill evidence exception (D1).
3. A second extraction call introduced without separate authorization (D2).
4. Semantic support asserted by code rather than adjudication.
5. Any threshold, weight or fuzzy rule without a stated failure mode and
   evaluation method.
6. Embeddings or fuzzy similarity introduced into identity.
7. Loss of V3.3 comparability (criterion 15).
8. Any existing frozen test weakened or deleted.
9. Backfilled, reconstructed or migrated historical records (D8).
10. Full benchmark re-run before deterministic unit gates pass.
11. An output limit pinned without verification (D4).
12. Diagnostic results extrapolated to the benchmark (§10.5).

---

## 18. Risks, unresolved questions, implementation-time verification

### 18.1 Risks

* **R-1** Mandatory evidence (D1) reduces recall for genuinely implicit
  expectations. Accepted deliberately: a false hard requirement is worse for a
  candidate decision than a missed soft one.
* **R-2** Removing skill arrays changes task difficulty; repeatability may
  improve while coverage falls. Must be measured **as a pair**.
* **R-3** Richer output against the same output limit may increase
  `POSSIBLY_TRUNCATED`. **Likely the main practical obstacle.** Mitigated by D4
  verification before any run.
* **R-4** Restructuring may destabilise downstream consumers more than the
  extractor.
* **R-5** Two-reviewer adjudication (§11) is slow and may accumulate
  `UNRESOLVED` items; that is a truthful outcome, not a failure.

### 18.2 Unresolved register — dispositions after review pass A2

| id | item | disposition | evidence / what remains |
| --- | --- | --- | --- |
| **U-1** | Supported max output tokens for this model/tier | **UNRESOLVED — BLOCKING** | Observations: 0/66 measured calls exceed 3,072; 21 sit exactly at 3,072; nothing between 3,060 and 3,072. That the clustering is *caused by* a ceiling is **Hypothesis (H-1)**. The documented maximum is **not established** by repository evidence. Needs provider documentation, a non-inference metadata endpoint, or one explicitly authorized live call. |
| **U-2a** | Does the client set an output limit, and where? | **RESOLVED** | `apps/api/app/ai/openai_provider.py::_json_completion` is the single provider call site and sends only `model`, `temperature`, `response_format`, `messages`. No `max_tokens` / `max_completion_tokens` / `max_output_tokens`. SDK 3.24.0 accepts both, both default `Omit`. |
| **U-2b** | Which parameter does the endpoint honour? | **UNRESOLVED — BLOCKING** | A property of the endpoint API contract for this exact model/tier. Not observable from the repository: the client never supplies either parameter, so no artifact records endpoint behaviour. Needs authoritative endpoint documentation or one explicitly authorized live call. |
| **U-3** | Truncation / completeness classification | **RESOLVED** | Five inspection classes and safe behaviours specified in §7.3, testable offline against the three preserved `400 json_validate_failed` records. No live test required. |
| **U-4** | Is `type` identity-defining? | **PROVISIONAL — NOT VALIDATED** | *Verified:* `type` is `_type_hint` from the **array key**; 16 names change type across the 26 jobs. *Not validated:* whether capability-vs-experience is ever a material obligation difference. The frozen eight-posting set contains **0 of 10** such cases, so it cannot settle it; r3's claim that it could is withdrawn. Narrow fix (array-derived type must not partition identity) is Verified and may proceed; the general rule awaits §11 R4 adjudication. |
| **U-5** | Configuration location for the output limit | **RESOLVED** | Follow the established `threshold_*` precedent: `.env` → `Settings` → frozen dataclass via `build_settings()` → recorded per run. No second configuration source. |
| **U-6** | Can `responsibilities` be a requirement source? | **RESOLVED** | It already cannot be one: `responsibilities` is in `STRING_ARRAYS` (coerced as strings) but **not** in `_TYPE_HINT`, so it never becomes a canonical requirement; `engine.py` contains zero references. The contract requirement it does **not** yet satisfy is the distinction below — a future prompt-contract item, not a code gap. |

**U-6 supporting contract (recorded, not implemented).** Three categories must
be distinguished so that a responsibility never silently becomes a hard
qualification:

| category | test | required treatment |
| --- | --- | --- |
| stated qualification / constraint | posting states it as a condition of being hired, with quotable mandatory or preference language | requirement, with evidence, adjudicated normally |
| responsibility implying a skill or experience | duty text contains a capability or duration that is separately assessable | emit as a requirement **only** with its own quote; the duty itself is not the requirement |
| descriptive duty | duty text only describes activities with no candidate-specific expectation | stays in `responsibilities`; never a requirement |

Anything not satisfiable by these tests must be **recorded as a future contract
requirement** rather than resolved by modifying code. The current prompt does
not ask the model to make this distinction explicitly, which is the actual gap.

### 18.3 Remaining blockers

| blocker | status | requires |
| --- | --- | --- |
| **U-1** — documented provider output maximum | **BLOCKING** | provider documentation, a non-inference metadata endpoint, or one explicitly authorized live call |
| **U-2b** — endpoint parameter semantics | **BLOCKING** | authoritative endpoint documentation, or one explicitly authorized live call |
| **U-4** — general capability-vs-experience identity rule | **PROVISIONAL, not blocking the narrow fix** | §11 `R4` adjudication on pairs arising in the diagnostic, or a separately authorized review outside the frozen set |
| **Evidence-exclusion engine behaviour** (§5.3 rule 3) | **BLOCKING for any engine work** | separate explicit authorization under D7 |

**Stage-1 gate.** The stage-1 output-budget gate closes only when **U-1 and
U-2b are both closed**. Neither alone is sufficient (§7.2). No output limit may
be pinned while either remains open.

### 18.4 Assumptions

Benchmark stays frozen and authoritative; matching weights/thresholds/blocker
policy stay frozen absent separate authorization; human labels remain 0/23 and
no correctness claim until they are not; the model id denotes a
stable-enough artifact — if not, §9.4 records it as a version change.

---

## 19. Recommended implementation sequence

```text
Stage 0  freeze this amended specification; no code
Stage 1  output-budget verification (U-1..U-3) — blocks all later stages
Stage 2  schema + evidence model
           ExtractedJobRequirements@3, evidence enum, offsets, mandatory provenance
           unit tests for every §17.1 criterion
Stage 3  canonicalisation
           V-2 fix (evidence-derived importance; INFORMATIONAL demotion)
           V-3 fix (dedup key excludes importance/category) + merged provenance
           V-1 consequence: skills gain evidence because the schema permits it
Stage 4  identity layering + evaluation harness (M1-M11, both definitions)
           reproduce V3.3 numbers bit-for-bit (criterion 15)
Stage 5  semantic-support review protocol operationalised (§11); no reviews run
Stage 6  diagnostic protocol execution (§10) — SEPARATE AUTHORIZATION
Stage 7  engine-consumer review — SEPARATE AUTHORIZATION (D7)
Stage 8  full controlled reproducibility experiment — SEPARATE AUTHORIZATION
```

Stages 2–4 require **no provider calls** for their acceptance criteria and **no**
engine change. Stage 1 blocks everything because an unpinned, unverified output
limit would make any diagnostic uninterpretable.

---

## 20. Required tests and validation gates

**Deterministic (no model calls).** Evidence mandatory with no exception;
non-verified states assigned correctly; `EVIDENCE_REJECTED` demotes;
`REQUIRED`/`PREFERRED` impossible without `EVIDENCE_VERIFIED`; one name at two
importances → one output; distinct durations stay distinct; distinct obligations
stay distinct and flagged; merged provenance complete; offsets resolve and
mismatches flag; category never derived from importance or array membership;
`None` vs `""` description identical; provenance chain resolves to a raw index;
semantic support never auto-set; evidence-ineligible requirements never silently
scored.

**Regression.** Full existing suite green with no weakened assertions; V3.3
ledger, benchmark, labels, blind pack unchanged by sha; V3.3 analysis artifact
re-reads identically under new code.

**Evaluation.** M1–M11 emitted with denominators; reports state which identity
definition underlies each number; unknowns reported as unknown.

---

## 21. Out of scope for this amendment

Implementation; extraction reruns; model/provider/temperature/prompt experiments;
matching-engine integration, scoring, threshold or blocker changes; benchmark,
ledger or frozen-artifact changes; human-label execution or adjudication;
diagnostic execution; any new experiment; any claim of extraction accuracy,
precision, recall or recommendation correctness.

---

## 22. Recorded decisions and remaining approvals

### 22.1 Recorded and closed

D1 evidence policy · D2 single-call architecture · D3 dedup/identity separation ·
D4 verified output budget · D5 eight-posting diagnostic set · D6 two-reviewer
review design · D7 separate engine authorization · D8 historical payload
limitation.

The r1 questions Q-1 (evidence exception), Q-2 (approach) and Q-3 (dedup) are
**closed by D1, D2 and D3 respectively.**

### 22.2 Still requiring user input before implementation

*Cross-reference correction (amendment A4):* r3.1 closed U-2 into U-2a/U-2b and
downgraded U-1 and U-4; this list previously still referenced the r3-era
dispositions and is now aligned with §18.2.

1. **U-1 (UNRESOLVED — BLOCKING) and U-2b (UNRESOLVED — BLOCKING)** — establish
   the documented output maximum and the endpoint parameter semantics, and
   confirm who obtains that evidence. The stage-1 gate closes only when both
   are closed (§18.3).
2. **U-4 (PROVISIONAL — NOT VALIDATED)** — decide whether to adopt the narrow
   array-derived-`type` fix now and defer the general
   capability-versus-experience rule to §11 adjudication, or to hold stage 3
   pending adjudication. §8.1.
3. **U-3, U-5, U-6 (RESOLVED)** — no input required; recorded for traceability.
4. **A4 — evidence sufficiency (§5.1.2).** Decide between option **(a)** and
   option **(b)**.
   * **Recommendation: option (b)**, refined by amendment A6 to
     `decision_eligible = (evidence_state == EVIDENCE_VERIFIED AND semantic_support == SUPPORTED)`.
     `SUPPORTED` qualifies (subject to all other gates); `PARTIAL`, `NOT_SUPPORTED`,
     `UNSURE` and `UNADJUDICATED` do not. Rationale: `EVIDENCE_VERIFIED` is a
     string-correspondence test only (§5.2), so option (a) permits a genuinely
     quoted sentence to carry an unchecked claim into a recommendation, and a
     `PARTIAL` verdict supports only part of an asserted obligation.
   * **Status: NOT YET APPROVED. Option (a)/R-E1 remains operative** (§5.1.1,
     §5.1.3). Adopting (b) requires: the §5.1.4 adjudication prerequisite
     completed under a separately authorized plan; owner approval; a separate
     amendment making it operative and reconciling all seven items in §5.1.5;
     and separate D7 authorization for any engine-side consequence.
   * **Blocking prerequisite (§5.1.4):** no §11 adjudication has ever been
     conducted. As proposed, option (b) applied today would make
     `decision_eligible` false for **every** requirement, leaving no
     decision-bearing set at all. It is not a standalone switch.
   * **Scope note:** adopting (b) reverses the orthogonality principle in
     §5.1 rule 3 and touches §5.1 (q2, q4), §5.2.1 and §5.2.2 as well — a
     broader policy change than one eligibility expression (§5.1.5).
   * **Prerequisite plan still UNDECIDED** (§5.1.4 items 1–5): unit of
     adjudication, §11.2–§11.3 application, provenance linkage, coverage and
     unresolved reporting, and frozen eight-posting limits — plus the
     `R1`-verdict-to-`semantic_support` field mapping.
5. Confirm **stage 6** (diagnostic) and **stage 8** (full experiment) each
   require separate authorization.
6. Approve **§17.1 criterion 15** (bit-for-bit V3.3 reproduction) as a
   non-negotiable gate.

---

## Appendix A — illustrative proposed shapes

```python
# PROPOSAL ONLY -- not implemented, not imported anywhere.

@dataclass(frozen=True)
class Evidence:
    state: str                 # VERIFIED | REJECTED | UNVERIFIED | ABSENT
    quote: str | None
    start: int | None
    end: int | None
    reason: str | None

@dataclass(frozen=True)
class Provenance:
    source_sha256: str
    run_id: int
    raw_index: int
    coerced_index: int | None
    canonical_index: int | None

@dataclass(frozen=True)
class CanonicalRequirementV3:
    name: str
    normalized_name: str
    type: str                  # identity-defining
    years_required: float | None
    importance: str            # classification-only; not part of identity
    category: str              # classification-only; not part of identity
    evidences: tuple[Evidence, ...]
    provenance: tuple[Provenance, ...]   # one per absorbed raw element
    merged_occurrences: int
```

## Appendix B — verified demonstrations (CE-13, read-only)

```text
D1  validate_importance("REQUIRED","python","", "")   -> REQUIRED   (no downgrade)
D2  validate_importance("REQUIRED","python","", None) -> PREFERRED  (accidental)
D3  canonicalize([python REQUIRED, python PREFERRED]) -> count 2 (dedup splits)
D4  633/633 SKILL instances have source_text == ""
D5  0/268 EXPERIENCE, 0/268 OTHER, 0/63 LOCATION, 0/16 EDUCATION lack evidence
D6  raw extraction: 580 bare-string skill items, 492 dict items with source_text
D7  prompt: skills "contain PLAIN STRINGS ONLY ... Never put objects in them"
D8  VJ-02: 8 tools flip REQUIRED<->PREFERRED en masse across runs 1-3
D9  engine dimension score = sum(s*w)/sum(w); _importance_weight 1.0 vs 0.45
```

No production code, test, frozen artifact or ledger was modified. No inference
call occurred.

## Appendix C — change log

| version | change |
| --- | --- |
| `v3.4-spec-r1` | Initial specification. sha `52a277c1859973fc8f994140fa93e5b2eabfa528c96fd084874ac3abcdb730c9`, 47,052 bytes. |
| `v3.4-spec-r2` | **Amendment A1.** Records decisions D1–D8 as fixed. Removes the r1 "narrow declared exception" for evidence eligibility (D1). Adds §6 single-call extraction contract, §7 output budget and failure handling (D4, with OB-1..OB-3 unresolved), §8 identity/dedup contract with mandatory merged provenance (D3), §10 eight-posting diagnostic protocol with an explicit no-extrapolation boundary (D5), §11 two-reviewer semantic-support review protocol (D6), §13 engine-consumer scope exclusion with deferred downstream questions (D7), §14 preserved historical payload limitation (D8). Adds §0 decision register, §18.2 unresolved register, Appendix C. Closes r1 questions Q-1/Q-2/Q-3. V3.3 verified findings V-1..V-6, hypotheses H-1/H-2, lifecycle description, and Appendix B demonstrations retained **unchanged**. |
| `v3.4-spec-r3` | **Review pass A2.** Verified r2 artifact hash before editing. **Corrects a demonstrated conflation:** r2 §5.3 rule 2 and §8.3 step 3 forced evidence-ineligible requirements to `INFORMATIONAL`, which merged evidence status with importance and destroyed the model's original assertion. New §5.2.1 separates four orthogonal fields (`evidence_state`, `importance_model`, `importance_adjudicated`, `decision_eligible`); ineligible requirements now take `importance_adjudicated = UNRESOLVED` with a recorded reason. **Resolves U-1..U-6** with dispositions and repository evidence (§7.1, §7.2, §7.3, §8.1, §18.2): U-1 RESOLVED WITH CONDITION (0/66 calls exceed 3,072; documented maximum still unverified), U-2/U-3/U-4/U-5/U-6 RESOLVED. **U-4 changes a design position:** `type` moves from identity-defining to classification-only, verified from `_TYPE_HINT` array-key derivation and the `VJ-B19` case. Adds §18.3 remaining blockers. Records the U-6 three-category responsibility contract. Decisions D1–D8, the eight-posting set, V3.3 findings, the missing-payload limitation, the two-reviewer design and the D7 gate are all **unchanged**. |
| `v3.4-spec-r3.1` | **Clarification pass A3.** Verified r3 artifact hash before editing. **Fixes an ambiguity:** r3 listed `SEMANTIC_UNADJUDICATED` as a fifth row of the §5.2 evidence-state table; it is a semantic-support value, not an evidence-correspondence value, and its presence invited reading it as an evidence state affecting eligibility. Removed from that table and specified as the separate `semantic_support` field. §5.1 rewritten from three to **four** distinct questions with explicit automatable/adjudication split and the behaviour while semantic support is `UNADJUDICATED`. **Splits U-2 into U-2a (RESOLVED — client sends no limit, source location recorded) and U-2b (UNRESOLVED — BLOCKING, endpoint parameter semantics),** with the U-1↔U-2b dependency stated and a two-part stage-1 gate. **Downgrades U-1** from "RESOLVED WITH CONDITION" to **UNRESOLVED — BLOCKING**, and separates the verified observation, the H-1 causal hypothesis, and the unestablished documented limit into an explicit table; corrects r3's "is the signature of" overclaim. **Downgrades U-4** from RESOLVED to **PROVISIONAL — NOT VALIDATED**: measured evidence shows the frozen eight-posting set contains 4 of 16 type-transition pairs and **0 of 10** `SKILL`↔`EXPERIENCE` cases, so it cannot validate the general rule; **r3's claim that the §11 rubric could settle it inside the frozen set is withdrawn as factually wrong.** Separates observation / proposed rule / validation status and records both merge and split risks plus implementation readiness. Adds §18.3 stage-1 two-part gate. Decisions D1–D8, the eight-posting set, V3.3 findings, the missing-payload limitation, the two-reviewer design and the D7 gate are all **unchanged**. |

**r3 supersession detail.** r2 §5.3 rule 2 ("is forced to `INFORMATIONAL`
importance") and r2 §8.3 step 3 ("forced to `INFORMATIONAL` with a recorded
reason") are **superseded** by §5.2.1 and §8.3 respectively. r2 §8.1's inclusion
of `type` among identity-defining attributes is **superseded** — `type` is now
classification-only. r2 §7.1–§7.3 `V-pending OB-1..OB-3` placeholders are
**superseded** by §7.1–§7.3. No other r2 content is withdrawn, and no r1 or V3.3
content is altered.

**r3.1 supersession detail.** r3 §5.1's three-question framing is **superseded**
by the four-question version. r3 §5.2's five-row table including
`SEMANTIC_UNADJUDICATED` is **superseded** by the four-state table; the four
approved evidence states are unchanged. r3 §7.1's "RESOLVED WITH CONDITION" and
its "is the signature of" phrasing are **superseded** by U-1 `UNRESOLVED —
BLOCKING` and the observation/hypothesis/unestablished table. r3 §7.2's single
`U-2: RESOLVED` entry is **superseded** by U-2a and U-2b. r3 §8.1's
"U-4 resolved" and "VJ-B19 is decisive" are **superseded** by
`PROVISIONAL — NOT VALIDATED`, and r3's statement that the frozen set contains
the needed transition pairs is **withdrawn as factually incorrect**. No other
r3 content is withdrawn.

| `v3.4-spec-r3.2` | **Semantic clarification A4.** Verified r3.1 artifact hash before editing. Answers the open semantic question directly rather than leaving it to inference between tables. **§5.2:** adds an explicit definition of what `EVIDENCE_VERIFIED` establishes — a string-correspondence test against the frozen posting bytes — and enumerates what it does **not** establish, including that a verified quotation may be attached to a false claim. **§5.1.1 (new):** states rule **R-E1**, `decision_eligible = (evidence_state == EVIDENCE_VERIFIED)` as the only determinant, and applies it explicitly to all four downstream surfaces (requirement matching, score calculation, blocker evaluation, final recommendation), stating that a VERIFIED + UNADJUDICATED requirement **may** influence each. Confirms uniform treatment across all requirement categories with no skill or category exception. **§5.1.2 (new):** records the resulting tension — that R-E1 makes quote correspondence the operative decision gate, and that D1's wording states only a *necessary* condition while R-E1's sufficiency was inferred in r3.1 — and presents options (a) retain R-E1 and (b) require adjudication before decision use, **without resolving it**; option (a) remains operative pending user decision. **§5.2.2 (new):** distinguishes the four independent stages (retained for audit / evidence-verified / semantically adjudicated / eligible for decision-bearing use), stating that none implies the next and that exclusion from decision use is not deletion, omission, or downgrading. **§22.2:** cross-reference correction aligning the decision list with r3.1 dispositions and adding the A4 sufficiency decision. No new state or field introduced; the four evidence states, `semantic_support`, `importance_model`, `importance_adjudicated` and `decision_eligible` are all unchanged. U-1, U-2b and U-4 wording untouched. Decisions D1–D8, the frozen eight-posting set, V3.3 findings, the missing-payload limitation, the two-reviewer design and the D7 gate all **unchanged**. |
| `v3.4-spec-r3.3` | **A4 decision record A5.** Verified r3.2 artifact hash before editing. **Records option (b) as the RECOMMENDED decision while leaving it NOT OPERATIVE.** **§5.1.3 (new):** side-by-side operative/proposed table — R-E1 marked **IN FORCE**, option (b) marked **NOT IN FORCE**; defines sufficient semantic support using only §11.1's already-approved R1 verdict vocabulary (`SUPPORTED` or `PARTIAL`; `UNSURE` and `NOT_SUPPORTED` would not qualify); confirms that only a §11 adjudication record may establish it and that §5.1 rule 2 already forbids any code path from doing so, with **no new adjudication process proposed**; confirms retention and importance preservation are unaffected and that option (b) must not be implemented as a downgrade to `INFORMATIONAL`; states the operational trade-off (fewer decision-bearing requirements until adjudication, and that this must not be reported as extraction failure); and sets a three-step approval gate. **§5.1.1:** R-E1 table row gains a `status` column reading **OPERATIVE** with a pointer to §5.1.3 — rule text unchanged. **§5.1.2:** fixes a broken cross-reference (`§22.3` → `§22.2`, item 4; no §22.3 exists). **§22.2 item 4:** records option (b) as recommended, explicitly **NOT YET APPROVED**, with R-E1 still operative and the three-step approval path. U-1, U-2a, U-2b and U-4 dispositions untouched. D1–D8, the frozen eight-posting diagnostic set, §11 two-reviewer design, §13 D7 gate, V3.3 findings and the missing-payload limitation all **unchanged**. **No behaviour change.** |

**r3.2 supersession detail.** No r3.1 rule is withdrawn. r3.1 §5.1 rule 3
("Eligibility tracks evidence correspondence under D1 and nothing else") is
**retained in substance** and is now written as rule R-E1 with its four
downstream consequences spelled out; the addition is precision and explicit
consequence, not a change of rule. r3.1 §5.2's `EVIDENCE_VERIFIED` row is
**unchanged in value** (`decision_eligible = true`) and is now accompanied by a
definition of what the state means. §5.2.2's stage table is additive and
consistent with r3.1 §5.2.1.

**r3.3 supersession detail.** No r3.2 content is withdrawn. The §5.1.2 reference
to "§22.3" is **corrected to §22.2** (no §22.3 exists). §5.1.1's R-E1 row gains
a status label only; its rule text is **unchanged**. §5.1.3 is **additive and
non-operative**.

| `v3.4-spec-r3.4` | **A4 decision preparation A6.** Verified r3.3 artifact hash before editing. **Refines the proposed option (b) to `SUPPORTED` only and records its prerequisites. No behaviour change; option (b) remains NOT IN FORCE and R-E1 remains IN FORCE.** **§5.1.3:** the proposed rule is refined from `semantic_support IN {SUPPORTED, PARTIAL}` to **`semantic_support == SUPPORTED`**; adds a per-verdict qualification table (`SUPPORTED` qualifies subject to all other gates; `PARTIAL`, `NOT_SUPPORTED`, `UNSURE`, `UNADJUDICATED` do not, each retained for audit and adjudication); adds the rationale that partial support does not establish support for an entire asserted obligation and must not drive matching, scoring, blockers or recommendations merely because part is supported; adds an explicit **no-splitting / no-identity-redesign / no-partial-weight** scope limit; corrects r3.3's understated cost to state that with **no adjudication performed, option (b) applied today would make `decision_eligible` false for every requirement**, leaving no decision-bearing set, and that it is **not a standalone switch**; extends the approval gate from three steps to four, with the prerequisite as step 0. **§5.1.4 (new):** states option (b) **cannot become operative until the semantic-adjudication prerequisite is completed under a separately authorized plan**, lists the five plan items as explicitly **UNDECIDED — requires separate plan**, and records an identified gap — the absent mapping from §11 `R1` verdict to stored `semantic_support` value — as **not resolved and not invented here**. **§5.1.5 (new):** enumerates the seven operative statements option (b) would overturn, including that §5.1 rule 3's orthogonality principle would be **directly contradicted**, so a later making-operative amendment cannot leave contradictions behind. **§5.1.2:** option (b) cell marked **formulation SUPERSEDED** by §5.1.3, still not in force. **§22.2 item 4:** updated with the refined rule, the four-step gate, the blocking prerequisite, the breadth note, and the five undecided plan items. **No state added, renamed, or removed. §11 rubric unchanged. No adjudication mechanism invented.** U-1, U-2a, U-2b and U-4 dispositions, D1–D8, the four evidence states, the separate `semantic_support` concept, the separation of evidence eligibility from importance, audit retention and provenance, the §11 two-reviewer design, the frozen eight-posting diagnostic set, the D7 gate, V3.3 findings and the historical missing-payload limitation all **unchanged**. |

**r3.4 supersession detail.** No r3.3 rule is withdrawn. The r3.3 option (b)
formulation `IN {SUPPORTED, PARTIAL}` is **refined**, not reversed in status, to
`== SUPPORTED`; the refinement narrows a **non-operative proposal** only, so no
operative content changes. §5.1.3's r3.3 statement that option (b) "will leave
fewer requirements eligible" is **corrected** as an understatement — the
accurate figure, given zero adjudications performed, is zero eligible
requirements. §5.1.4 and §5.1.5 are **additive and non-operative**. §5.2,
§5.2.1, §5.2.2, §11, §13 and D7 are **unchanged**.

**Amendment effect on r1 content.** r1 §E-3 ("mandatory evidence with a narrow,
declared exception") is **superseded and removed**; no exception exists. r1
§E-1's "MANDATORY except declared exception" comment is **superseded**. r1
§7 acceptance criterion "evidence or an explicit exception" and r1 §14 "exception
requires a reason" are **superseded**. r1 §16 decisions 1, 2 and 3 are
**closed**. No other r1 content is withdrawn.