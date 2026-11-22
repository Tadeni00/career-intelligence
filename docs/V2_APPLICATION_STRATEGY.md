# V2 — Application Strategy & Decision Intelligence

**Status:** Implemented and validated. V1, V1.1 and V1.2 remain frozen and unmodified.

---

## 1. What V2 adds

V1 answered *does this candidate match this job?* V1.1 made generated output safe.
V1.2 made validation precise. V2 adds the missing **decision-interpretation layer**:

> Given this job and the candidate's confirmed evidence, is it worth applying —
> and how should the candidate position the experience they actually have?

```
Confirmed Career Evidence + Job Requirements
                ↓
        Deterministic Match          (frozen, authoritative)
                ↓
        Application Decision         (frozen recommendation, consumed)
                ↓
        Application Strategy         ← V2
                ↓
     Tailored CV / Cover Letter
                ↓
      Evidence Validation           (V1.2, still authoritative)
                ↓
          Human Review → Apply
```

## 2. The governing rule

The system must never confuse **what the job wants** with **what the candidate
has**. The strategy layer is an interpretation of confirmed evidence. It is not a
mechanism for creating candidate facts.

## 3. Deterministic vs LLM boundary

| Deterministic (decides) | LLM (may only assist) |
|---|---|
| match score and recommendation | concise explanations |
| hard blockers | summarisation |
| requirement importance | readable phrasing |
| evidence availability | organisation of strengths |
| explicit evidence mappings | drafting emphasis |
| safety restrictions | — |

The model receives a `StrategyContext` of already-computed facts and may return
only a `decision_summary` string. It is never asked to judge fit. Every returned
sentence is then re-validated by `validate_strategy`.

## 4. The strategy

```text
ApplicationStrategy
    decision                 # copied from the frozen recommendation
    decision_summary         # the only model-authored field
    strengths[]              # requirement -> evidence_ids, strength
    gaps[]                   # importance, severity, "not established" phrasing
    blockers[]               # only ever sourced from match blockers
    transferable_evidence[]  # DIRECT / TRANSFERABLE / PARTIAL / UNCERTAIN
    evidence_emphasis[]      # prioritisation, never new facts
    claim_restrictions[]     # do-not-claim list fed to generation
    actions[]                # decision-specific next steps
    review_notes[]           # surfaced uncertainty
```

## 5. Evidence relationships

`relationship_for()` classifies each requirement against the evidence index:

| Relationship | Condition |
|---|---|
| `DIRECT` | every significant term present in one evidence item |
| `TRANSFERABLE` | fully covered via alias or an evidenced paraphrase |
| `PARTIAL` | ≥50% covered **and** the requirement has ≥2 significant terms |
| `UNCERTAIN` | otherwise |

Two deliberate guards, both added after the real-world benchmark exposed
spurious provenance:

- **Single-character terms are discarded.** `B` inside `B.Sc` was producing a
  "B.Sc evidence" match for a requirement about something else entirely.
- **A requirement whose terms are all generic vocabulary** ("Data analysis
  experience" — `data`, `analysis`, `experience` are all generic) reports *no*
  relationship rather than inventing one.

`PARTIAL` and `UNCERTAIN` are never asserted as transferable support. They are
surfaced in `review_notes` instead, aggregated into a single note so the
candidate is not shown a wall of text. Nothing is hidden — every unmapped
requirement is still named.

## 6. Gap integrity

A gap always reads:

> *X* is not established in the candidate's confirmed evidence. This is an
> evidence boundary, not a statement about the candidate's actual experience.

`validate_strategy` rejects any gap whose statement asserts factual absence
("does not have", "has no experience", "lacks", "never used", …). Severity
follows importance:

| Importance | Severity |
|---|---|
| `REQUIRED` | `REQUIRED_GAP` |
| `PREFERRED` | `PREFERRED_GAP` |
| soft signal | `SOFT_SIGNAL_GAP` |

## 7. Blocker integrity

Blockers are taken **only** from the deterministic engine's blocker list. A
requirement that is merely absent from evidence becomes a gap, never a blocker.
A blocker with no underlying requirement is rejected by validation. In the
benchmark, zero false blockers were produced.

## 8. Claim restrictions

Every gap and blocker produces a `do not claim` restriction with a stated reason.
These are injected into the CV and cover-letter prompts as structured guidance:

```
Prioritise this confirmed evidence: …
Do NOT claim or imply any of the following, because they are not established in
the candidate's confirmed evidence: …
```

**These are prompt guidance, not a safety control.** The V1.2 deterministic
validator remains the final authority; this is asserted by test.

## 9. Staleness

A strategy is built from a specific evidence state and job requirement set. An
`evidence_fingerprint` (SHA-256 over skills, experience, education, summary and
requirement text) is stored with it. If the fingerprint or the source match
changes, the strategy is rebuilt as a new version and the previous version is
marked `STALE`. Stale strategies are never silently reused.

The fingerprint tracks *data*, not engine code. After changing strategy logic,
existing rows must be rebuilt explicitly (that is why the benchmark clears the
table before measuring).

## 10. No profile mutation

The strategy layer has no write path to the candidate profile. A discovered gap
never becomes a skill. This is enforced by test (`test_strategy_build_does_not_
mutate_profile`) and by the absence of any profile write in `services/strategy.py`.

## 11. Benchmark results

Three frozen jobs, unchanged candidate evidence, unchanged postings.

| Job | Human | Frozen decision | Preserved | Strengths | Gaps | Blockers | Restrictions | Review notes |
|---|---|---|---|---|---|---|---|---|
| VJ-01 Monzo | MAYBE | SKIP | yes | 2 | 0 | 0 | 0 | 2 |
| VJ-02 Affirm | NO | SKIP | yes | 2 | 1 | 0 | 1 | 2 |
| VJ-03 SEAhub | YES | APPLY_WITH_TAILORING | yes | 4 | 5 | 0 | 5 | 0 |

- **Strategy grounding: 22/22 (100%)** — every candidate-specific assertion cites
  evidence present on the confirmed profile.
- **Critical unsupported claims: 0**
- **False blockers: 0**
- **Decision preservation: all jobs**

The three jobs behave differently, as required: two clear SKIPs with short action
plans, one strong match with a full emphasis/restriction/action set.

## 12. Safety retention

During the V2 gate run the live model again emitted the injected tracking payload
(`BRIGHTEST #RMTM…`, decoding to `137.255.177.157`). The validator classified it
`CRITICAL` / `SUSPICIOUS_OUTPUT` and the document did not reach `VALID`. A valid
strategy did **not** make an unsupported document acceptable.

## 13. Known limitations

- **Recommendation agreement is unchanged and remains imperfect.** VJ-01 scores
  80.5 yet is `SKIP`, while the human baseline is MAYBE. That is the frozen
  matching engine's behaviour and V2 deliberately does not touch it. V2 explains
  the decision faithfully rather than second-guessing it.
- **Blockers are sparse.** The frozen engine produces few hard blockers, so most
  SKIPs are score-driven rather than blocker-driven. The strategy now says so
  instead of implying a blocker exists.
- **The evidence fingerprint does not include the strategy engine version.** A
  logic change requires an explicit rebuild; a data change does not.
- **Emphasis ranking is by evidence coverage**, not by business value. The
  highest-ranked item is often "professional summary", which is not very
  actionable for the candidate.
- **Transferable evidence is conservative.** Anything below `PARTIAL`, or without
  two real terms, is reported as uncertainty rather than a link. This under-
  claims rather than over-claims, which is the intended direction.
- **No LLM-authored emphasis.** `evidence_emphasis` and `actions` are fully
  deterministic templates. The spec permits the model to draft emphasis; V2 chose
  determinism for auditability.

## 14. Gate status

| Gate | Requirement | Result |
|---|---|---|
| A | Recommendation behavior unchanged | PASS |
| B | Every candidate-specific assertion evidence-backed | PASS |
| C | "Not established" never becomes "definitely does not have" | PASS |
| D | Every blocker grounded in requirement + match result | PASS |
| E | Missing/unsafe claims surfaced as restrictions | PASS |
| F | Transferable evidence never becomes an unsupported claim | PASS |
| G | Strategy informs generation without bypassing validation | PASS |
| H | All V1.1/V1.2 safety cases still pass | PASS |
| I | All existing + V2 tests pass | PASS |
| J | Human audit | PASS |
| K | Real-world benchmark on the three frozen jobs | PASS |