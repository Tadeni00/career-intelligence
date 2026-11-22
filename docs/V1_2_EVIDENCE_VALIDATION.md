# V1.2 — Evidence Validation Precision & Review Efficiency

**Status:** Implemented and validated. V1 and V1.1 remain frozen and unmodified.

**Governing principle:** Evidence over intuition. Engineering over prompting.
Reliability as a first-class feature.

---

## 1. Why V1.2 exists

V1.1 made employer-facing output *safe*: unsupported and suspicious content
could no longer silently reach `VALID`. The cost was precision. A generated
cover letter produced roughly 13–16 findings, only some of which were genuine
fabrication. The rest were wording differences, normalisation gaps, harmless
vocabulary, or claims whose relationship to the evidence was merely unclear.

V1.2 does not make the validator more permissive. It makes it **more accurate**:
it separates *decisions* from *volume*, and it explains every finding.

---

## 2. Claim classifications

| Classification | Meaning | Outcome |
|---|---|---|
| `SUPPORTED` | Every significant term appears in confirmed evidence | Accept |
| `SUPPORTED_BY_ALIAS` | Wording differs by an explicit controlled alias | Accept |
| `SUPPORTED_BY_NORMALIZATION` | Wording differs only by spelling, number form, possessive, paraphrase, or a decorative qualifier | Accept |
| `NON_FACTUAL` | Stylistic, aspirational, or commentary — asserts no candidate fact | Accept |
| `PLAUSIBLE_BUT_UNVERIFIED` | Candidate-specific but not confidently traceable | `REVIEW_REQUIRED` |
| `STRENGTHENED` | Materially increases the factual strength of the evidence | `VALIDATION_FAILED` |
| `UNSUPPORTED` | Explicit candidate fact absent from evidence | `VALIDATION_FAILED` |
| `CONTRADICTORY` | Conflicts with confirmed evidence (e.g. employment dates) | `VALIDATION_FAILED` |
| `SUSPICIOUS` | Injected payload or unexpected content | `VALIDATION_FAILED` |

`ACCEPTED_CLASSES` is the single set consulted when deciding whether a finding
is emitted at all. `HARD_FAILURE_CLASSES` documents the classifications that may
never be downgraded to review-only.

---

## 3. Hard failure versus review required

The validator explicitly separates two outcomes:

- **`VALIDATION_FAILED`** — sufficient evidence of a violation. Invented
  technology, invented metric, invented employer, eligibility fabrication,
  invented contact detail, contradictory dates, suspicious payload, material
  claim strengthening.
- **`REVIEW_REQUIRED`** — the claim is candidate-specific, cannot be confidently
  mapped to evidence, but there is no basis to call it fabricated. It is surfaced
  to a human with an explanation and a recommended action.

A fabricated fact must never be routed to review. A genuinely ambiguous
paraphrase must never be routed to failure. Both directions are covered by tests.

---

## 4. Evidence traceability

Each classified claim carries an internal trace:

```
Generated Claim → Claim Type → Evidence Match → Evidence ID(s)
                → Comparison Result → Severity → Final Decision
```

`Claim.to_trace()` returns the claim text, category, classification, severity,
matched evidence labels, unexplained terms, reason and action. This metadata is
attached to every validation finding but is never injected into the
employer-facing document itself.

Example of a resolved trace:

```
Claim      "I use Excel daily for analysis."
Evidence   skill "Microsoft Excel"
Result     SUPPORTED_BY_ALIAS  (decorative qualifier "daily")
Severity   INFORMATIONAL
Decision   ACCEPT
```

---

## 5. Normalisation and aliases

Normalisation (applied before any comparison):

- Unicode NFKC canonicalisation; dash, apostrophe and quote variants folded.
- Possessives stripped, so `Monzo's` and `Monzo` compare equal.
- Number words folded, so `six years` and `6 years` compare equal.
- A controlled spelling table folds `modelling/modeling`, `organised/organized`,
  `analyse/analyze` and similar.
- Existing technology aliases (`Microsoft Excel ↔ Excel`, `Postgres ↔ PostgreSQL`,
  `ML ↔ Machine Learning`) are preserved and extended.

Aliases are explicit and justified. There is no uncontrolled synonym expansion.

`PARAPHRASE_GROUPS` records deliberate equivalences (e.g. `conducted ≈ performed`,
`built ≈ developed`, `cleaned ≈ cleansed`). A token is treated as paraphrased only
when a member of its group is actually present in the evidence — this is
traceable, not a similarity guess.

---

## 6. Why a token is missing

V1.1 asked *how many* terms were missing. V1.2 asks **why**. An unexplained term
is explained away when it is:

1. a benign professional qualifier (`effective`, `strong`, `reliable`, `analytical`);
2. a frequency or degree adverb (`daily`, `regularly`, `thoroughly`);
3. an evidenced paraphrase (`developed` where evidence says `built`);
4. intent or commentary vocabulary about the employer or role (`interest`,
   `aligns`, `mission`) — these assert nothing about the candidate;
5. vocabulary already supplied by the job posting, including the target role and
   company name.

What remains is either a **specific entity** (a named technology, proper noun) or
**abstract content**. An unevidenced technology is always fabrication. Everything
else that cannot be resolved routes to review rather than to failure.

A coverage gate accepts a sentence as paraphrase when at least 70% of its
significant wording is evidenced and no unsafe signal is present. Explicit
fabrication checks run **before** the coverage gate, so a high-coverage sentence
can never smuggle an unevidenced technology past it.

---

## 7. Severity

| Severity | Meaning |
|---|---|
| `CRITICAL` | Fabricated identity, employment, education, eligibility, contact detail, or a suspicious payload |
| `HIGH` | Invented technology, invented metric, invented counterparty, material responsibility strengthening |
| `MEDIUM` | Unsupported candidate-specific factual statement |
| `LOW` | Weakly supported wording difference |
| `INFORMATIONAL` | Stylistic or non-factual observation |

Severity affects workflow, not only display. `CRITICAL` findings are always
`severity="error"` and always force `VALIDATION_FAILED`; they cannot be
downgraded to a review warning. Tests assert this invariant directly.

---

## 8. Actionable findings

Every finding answers four questions:

1. **What did the generated document say?** — `detail`
2. **What evidence was found?** — `matched_evidence`, named in the message
3. **Why is the relationship uncertain?** — `message` / reason
4. **What should the user do?** — `action`

```
Claim    "Reduced processing time by 30%."
Evidence No supporting metric found.
Reason   The generated claim contains a candidate-specific quantitative
         achievement that is absent from the career evidence.
Action   Remove or replace this claim.
```

---

## 9. Review workflow

```
Confirmed candidate evidence
        ↓
Job requirements
        ↓
Deterministic match
        ↓
Controlled LLM generation
        ↓
Structured output
        ↓
Claim validation          ← improved in V1.2
        ↓
Output sanitization
        ↓
Final safety gate
        ↓
Human review             ← REVIEW_REQUIRED lands here
        ↓
Employer-facing document
```

The master career profile remains authoritative. Tailored documents never write
back to it; new information enters only through an explicit profile-edit flow.
There is no generated-CV → validator → auto-update feedback loop.

---

## 10. Benchmark results

Three real jobs, unchanged candidate evidence, unchanged postings.

| Job | Human | V1.1 findings | V1.2 findings | Hard | Review | Critical |
|---|---|---|---|---|---|---|
| VJ-01 Monzo | MAYBE | 16 | 13 | 6 | 7 | 0 |
| VJ-02 Affirm | NO | 10 | 9 | 3 | 6 | 0 |
| VJ-03 SEAhub | YES | 13 | 11 | 5 | 6 | 2 |
| **Average** | | **13.0** | **11.0** | | | |

See §13 for the honest reading of this result.

---

## 11. Adversarial dataset

`docs/adversarial_dataset_v1.1.json`, version `1.2`. All 24 V1.1 cases
(`AD-001`–`AD-072`) are retained unchanged and a retention test enforces this.
V1.2 adds 16 cases covering paraphrase, alias, benign professional wording,
ambiguous strengthening and explicit fabrication. All 12 sanitization payload
cases are retained.

---

## 12. Safety preservation

Every V1.1 hard-failure class is still blocked: candidate-specific fabrication,
eligibility fabrication, contact fabrication, suspicious output, and claim
strengthening. Detection remains pattern- and class-based; no payload is
hard-coded.

A fresh provider generation reproduced the injected tracking payload
(`BRIGHTEST #RMTM…`, decoding to `137.255.177.157`). The validator classified it
`CRITICAL` / `SUSPICIOUS_OUTPUT` and the document did not reach `VALID`.

---

## 13. Known limitations

- **Review burden fell 15%, not to the level the milestone hoped for.** The
  residual findings are largely genuine: the model introduces descriptive content
  that is not in the evidence. Reducing them further requires changing generation
  behaviour, not the validator.
- **The profile summary was previously absent from the evidence index.** This
  was a real V1.1 defect that made legitimate summary-derived claims look
  unsupported. It is fixed in V1.2.
- **Paraphrase groups are hand-maintained.** They are deliberate and testable but
  they do not generalise; an unlisted equivalence becomes a review finding rather
  than a false acceptance, which is the safe direction.
- **Coverage threshold (70%) is a chosen constant**, justified empirically against
  the benchmark rather than derived. It should be revisited with more data.
- **Semantic similarity is not used as a safety decision.** Nothing authorises an
  employer-facing fact except an interpretable evidence relationship.
- **The candidate's own name tokenises inconsistently** (`adenyi`) and is
  occasionally reported as unexplained. Cosmetic, no safety impact, unresolved.

---

## 14. Gate status

| Gate | Requirement | Result |
|---|---|---|
| A | V1.1 critical safety cases still blocked | PASS |
| B | Suspicious-output payload classes still blocked | PASS |
| C | Eligibility fabrication still blocked | PASS |
| D | Material strengthening blocked or review-required | PASS |
| E | V1.1 false-positive cases resolved | PASS |
| F | Claims separated into the defined classifications | PASS |
| G | Review efficiency improved without safety regression | PASS WITH QUALIFICATION |
| H | Review-worthy claims traceable to evidence | PASS |
| I | V1.1 tests plus new V1.2 tests pass | PASS |
| J | Three benchmark jobs re-evaluated and documented | PASS |
| K | Human audit — no `VALID` document contains a critical violation | PASS |

Gate G is qualified: average findings per document fell from 13.0 to 11.0 (15%),
and the noise classes responsible for the V1.1 figure were removed. The reduction
is real but modest, because the remaining findings are genuine. The milestone
explicitly forbids buying a lower number by weakening validation, so no further
reduction was taken.