"""Application Strategy (V2): the decision-interpretation layer.

Position in the pipeline (spec section 4)::

    Deterministic Match -> Application Decision -> Application Strategy
                                                 -> documents -> validation

Design contract (spec sections 2, 17, 18, 19, 20):

* The **recommendation is never recomputed here.** The existing matching engine
  owns the decision; this module consumes it.
* Every candidate-specific statement is assembled from requirement text (the
  job side) and evidence labels (the candidate side). Nothing is invented.
* "Not established in candidate evidence" is the only phrasing permitted for a
  gap. Absence of evidence is never converted into a factual absence.
* The LLM may only write ``decision_summary`` prose. Every list is computed
  deterministically and then checked by :func:`validate_strategy`.
* Nothing here writes to the candidate profile. Strategy never mutates evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from app.models import EvidenceRelationship, GapSeverity, Recommendation
from app.schemas import (
    ApplicationStrategy,
    ClaimRestrictionOut,
    EvidenceEmphasisOut,
    ProfileSummary,
    StrategyActionOut,
    StrategyBlockerOut,
    StrategyContext,
    StrategyGapOut,
    StrategyReviewNoteOut,
    StrengthOut,
    TransferableEvidenceOut,
    ValidationIssue,
)
from app.services.evidence import (
    GENERIC_TOKENS,
    EvidenceIndex,
    build_index,
    paraphrase_match,
)
from app.services.normalization import canonical_tech, normalize_text, tokens
from app.services.validation import classify_requirement, is_soft_signal

# --------------------------------------------------------------------------- #
# inputs
# --------------------------------------------------------------------------- #


@dataclass
class RequirementRef:
    """A job requirement plus the deterministic match verdict for it."""

    id: int | None
    name: str
    description: str
    importance: str
    type: str
    years_required: float | None = None
    matched: bool = False
    is_gap: bool = False
    is_blocker: bool = False


def _index_requirements(job, outcome) -> list[RequirementRef]:
    """Fold job requirements and the match outcome into one lookup table."""
    matched_names = {normalize_text(m.name) for m in outcome.matched}
    gap_names = {normalize_text(g.name) for g in outcome.gaps}
    blocker_names = {normalize_text(b.name) for b in outcome.blockers}

    refs: list[RequirementRef] = []
    for req in job.requirements:
        key = normalize_text(req.name)
        refs.append(
            RequirementRef(
                id=req.id,
                name=req.name,
                description=req.description or "",
                importance=classify_requirement(
                    req.name, req.description or "", req.importance
                ),
                type=req.requirement_type,
                years_required=req.years_required,
                matched=key in matched_names,
                is_gap=key in gap_names,
                is_blocker=key in blocker_names,
            )
        )
    return refs


# --------------------------------------------------------------------------- #
# evidence relationships
# --------------------------------------------------------------------------- #


def _requirement_terms(name: str) -> set[str]:
    """Significant terms a requirement is actually asserting.

    Single-character tokens are discarded: they match by accident ("B" inside
    "B.Sc") and would manufacture evidence provenance that does not exist.
    """
    return {
        t for t in tokens(canonical_tech(name) or name) - GENERIC_TOKENS
        if len(t) > 1
    }


def relationship_for(
    ref: RequirementRef, idx: EvidenceIndex
) -> tuple[EvidenceRelationship, list[str], float]:
    """Classify how a requirement relates to confirmed evidence.

    Returns ``(relationship, evidence_labels, confidence)``. Conservative by
    construction: an unsupported requirement is never reported as transferable.
    """
    terms = _requirement_terms(ref.name)
    if not terms:
        # Nothing substantive to assess (e.g. "Data analysis experience", where
        # every term is generic vocabulary). Report no relationship rather than
        # manufacturing a spurious one.
        return EvidenceRelationship.UNCERTAIN, [], 0.0

    # A partial relationship needs at least two real terms; one matched term is
    # coincidence, not evidence.
    min_terms = 2

    alias_terms = tokens(canonical_tech(ref.name)) - GENERIC_TOKENS

    best: list[str] = []
    best_score = 0.0
    best_kind = EvidenceRelationship.UNCERTAIN

    for item in idx.items:
        support = item.support
        direct = terms & support
        alias = (alias_terms - terms) & support
        paraphrased = {
            t for t in terms if paraphrase_match(t, support)
        } - direct
        covered = direct | alias | paraphrased
        if not covered:
            continue
        score = len(covered) / len(terms)

        if direct >= terms:
            kind = EvidenceRelationship.DIRECT
        elif covered >= terms:
            kind = EvidenceRelationship.TRANSFERABLE
        elif score >= 0.5 and len(terms) >= min_terms:
            kind = EvidenceRelationship.PARTIAL
        else:
            kind = EvidenceRelationship.UNCERTAIN

        if score > best_score:
            best, best_score, best_kind = [item.label], score, kind
        elif score == best_score and best:
            best.append(item.label)

    if not best:
        return EvidenceRelationship.UNCERTAIN, [], 0.0
    return best_kind, best[:3], round(best_score, 2)


# --------------------------------------------------------------------------- #
# builder
# --------------------------------------------------------------------------- #


_SEVERITY_BY_IMPORTANCE = {
    "REQUIRED": GapSeverity.REQUIRED.value,
    "PREFERRED": GapSeverity.PREFERRED.value,
    "SOFT_SIGNAL": GapSeverity.SOFT_SIGNAL.value,
}


def _not_established(ref: RequirementRef) -> str:
    """The only permitted gap phrasing (spec section 10).

    Deliberately worded so it asserts nothing about the candidate: absence of
    evidence is reported, never converted into a factual absence.
    """
    return (
        f"{ref.name} is not established in the candidate's confirmed evidence. "
        "This is an evidence boundary, not a statement about the candidate's "
        "actual experience."
    )


def build_strategy(
    profile: ProfileSummary,
    job,
    outcome,
    *,
    idx: EvidenceIndex | None = None,
) -> ApplicationStrategy:
    """Assemble the strategy deterministically from match + evidence."""
    idx = idx or build_index(profile)
    refs = _index_requirements(job, outcome)

    strengths: list[StrengthOut] = []
    gaps: list[StrategyGapOut] = []
    blockers: list[StrategyBlockerOut] = []
    transferable: list[TransferableEvidenceOut] = []
    emphasis: list[EvidenceEmphasisOut] = []
    restrictions: list[ClaimRestrictionOut] = []
    notes: list[StrategyReviewNoteOut] = []
    unmapped: list[tuple[str, EvidenceRelationship]] = []
    _emphasis_scores: dict[str, float] = {}

    for ref in refs:
        rel, evidence, confidence = relationship_for(ref, idx)

        # --- strengths -------------------------------------------------
        if ref.matched and evidence:
            strengths.append(
                StrengthOut(
                    requirement_id=ref.id,
                    requirement_name=ref.name,
                    evidence_ids=evidence,
                    statement=(
                        f"{ref.name} is supported by confirmed evidence "
                        f"({', '.join(evidence)})."
                    ),
                    strength="STRONG" if rel is EvidenceRelationship.DIRECT
                    else "MODERATE",
                )
            )
            for label in evidence:
                _emphasis_scores[label] = _emphasis_scores.get(label, 0.0) + confidence

        # --- transferable evidence ------------------------------------
        if (
            not ref.is_gap
            and not ref.is_blocker
            and rel in (EvidenceRelationship.TRANSFERABLE, EvidenceRelationship.PARTIAL)
            and evidence
        ):
            transferable.append(
                TransferableEvidenceOut(
                    requirement_id=ref.id,
                    requirement_name=ref.name,
                    evidence_ids=evidence,
                    relationship=rel.value,
                    confidence=confidence,
                    statement=(
                        f"Confirmed experience at {', '.join(evidence)} is "
                        f"{rel.value.lower()} support for this requirement."
                    ),
                )
            )
            for label in evidence:
                _emphasis_scores[label] = _emphasis_scores.get(label, 0.0) + confidence

        # --- partial / uncertain relationships are review items --------
        # Suppressed where they add nothing: aspirational boilerplate, a
        # requirement the deterministic engine already confirmed, a gap that is
        # already reported as a gap, or a blocker already stated above.
        if rel in (EvidenceRelationship.PARTIAL, EvidenceRelationship.UNCERTAIN):
            already_reported = (
                is_soft_signal(ref.name, ref.description)
                or ref.matched
                or ref.is_gap
                or ref.is_blocker
            )
            if not already_reported:
                unmapped.append((ref.name, rel))

        # --- gaps ------------------------------------------------------
        if ref.is_gap:
            severity = _SEVERITY_BY_IMPORTANCE.get(ref.importance,
                                                    GapSeverity.PREFERRED.value)
            gaps.append(
                StrategyGapOut(
                    requirement_id=ref.id,
                    requirement_name=ref.name,
                    importance=ref.importance,
                    severity=severity,
                    statement=_not_established(ref),
                )
            )
            restrictions.append(
                ClaimRestrictionOut(
                    requirement_id=ref.id,
                    subject=ref.name,
                    statement=f"Do not claim {ref.name}.",
                    reason=(
                        "Not established in the candidate's confirmed evidence. "
                        "The requirement is present in the job description only."
                    ),
                )
            )

        # --- blockers --------------------------------------------------
        if ref.is_blocker:
            blockers.append(
                StrategyBlockerOut(
                    requirement_id=ref.id,
                    requirement_name=ref.name,
                    statement=(
                        f"{ref.name} is a stated requirement of this role and is "
                        "not established in the candidate's confirmed evidence."
                    ),
                    severity="CRITICAL",
                )
            )
            restrictions.append(
                ClaimRestrictionOut(
                    requirement_id=ref.id,
                    subject=ref.name,
                    statement=f"Do not claim or imply {ref.name}.",
                    reason="Unresolved blocker for this role.",
                )
            )

    # --- evidence emphasis (prioritisation, never new facts) ---------
    ranked = sorted(_emphasis_scores.items(), key=lambda kv: -kv[1])
    for priority, (label, _score) in enumerate(ranked[:6], start=1):
        emphasis.append(
            EvidenceEmphasisOut(
                evidence_ids=[label],
                statement=(
                    f"Emphasise confirmed evidence from {label}: it directly "
                    "supports the requirements this role prioritises."
                ),
                priority=priority,
            )
        )

    # --- unmapped requirements, aggregated ----------------------------
    # Reported as one note rather than one per requirement: the uncertainty is
    # preserved in full, but the candidate is not shown a wall of text.
    if unmapped:
        partial = [n for n, r in unmapped if r is EvidenceRelationship.PARTIAL]
        uncertain = [n for n, r in unmapped if r is not EvidenceRelationship.PARTIAL]
        detail: list[str] = []
        if partial:
            detail.append(f"{len(partial)} partially mapped: {', '.join(partial[:6])}")
        if uncertain:
            detail.append(
                f"{len(uncertain)} not mapped to confirmed evidence: "
                f"{', '.join(uncertain[:8])}"
            )
        notes.append(
            StrategyReviewNoteOut(
                severity="MEDIUM" if partial else "LOW",
                statement=(
                    f"{len(unmapped)} job requirement(s) could not be confidently "
                    f"mapped to the candidate's confirmed evidence "
                    f"({'; '.join(detail)}). This is an evidence boundary, not a "
                    "statement about the candidate's ability. Review before "
                    "relying on any of them."
                ),
            )
        )

    # --- eligibility / location uncertainty ---------------------------
    if any("authoris" in n.statement.lower() or "authoriz" in n.statement.lower()
           or "eligib" in n.statement.lower() for n in notes + gaps) or not idx.has_eligibility():
        if any(
            r.type == "LOCATION" or "authoris" in r.name.lower()
            or "authoriz" in r.name.lower() or "eligib" in r.name.lower()
            for r in refs
        ):
            notes.append(
                StrategyReviewNoteOut(
                    severity="HIGH",
                    statement=(
                        "This role references eligibility or location conditions. "
                        "No eligibility evidence is confirmed on the profile, so "
                        "viability cannot be determined either way. The candidate "
                        "must confirm their own status; the system must not infer it."
                    ),
                )
            )

    strategy = ApplicationStrategy(
        decision=outcome.recommendation,
        decision_summary=outcome.explanation or "",
        strengths=strengths,
        gaps=gaps,
        blockers=blockers,
        transferable_evidence=transferable,
        evidence_emphasis=emphasis,
        claim_restrictions=restrictions,
        actions=_actions_for(outcome.recommendation, strengths, gaps, blockers,
                             restrictions),
        review_notes=notes,
    )
    return strategy


# --------------------------------------------------------------------------- #
# actions
# --------------------------------------------------------------------------- #


def _actions_for(
    decision: str,
    strengths: list[StrengthOut],
    gaps: list[StrategyGapOut],
    blockers: list[StrategyBlockerOut],
    restrictions: list[ClaimRestrictionOut],
) -> list[StrategyActionOut]:
    """Deterministic next steps per decision (spec section 14)."""
    required_gaps = [g for g in gaps if g.severity == GapSeverity.REQUIRED.value]

    if decision == Recommendation.SKIP.value:
        if blockers:
            primary = blockers[0].statement
            follow_up = StrategyActionOut(
                priority=2,
                action="Review the stated blocker before reconsidering.",
                rationale=(
                    "If the blocker reflects missing evidence rather than a genuine "
                    "limitation, update the profile explicitly and re-run the match."
                ),
            )
        else:
            # Never reference a blocker that does not exist. A SKIP without a
            # blocker comes from the overall score and dimension breakdown.
            primary = (
                "The deterministic match scored this role below the application "
                "threshold. No single requirement was recorded as a hard blocker."
            )
            follow_up = StrategyActionOut(
                priority=2,
                action="Review the score breakdown before reconsidering.",
                rationale=(
                    "Compare the per-dimension scores against the role. If a "
                    "requirement is missing from the extraction, re-run requirement "
                    "extraction before trusting the result."
                ),
            )
        return [
            StrategyActionOut(
                priority=1,
                action="Do not spend application effort on this role.",
                rationale=primary,
            ),
            follow_up,
        ]

    if decision == Recommendation.STRETCH.value:
        return [
            StrategyActionOut(
                priority=1,
                action="Review the missing requirements.",
                rationale=(
                    "".join(f"{g.requirement_name}. " for g in gaps)
                    or "No gaps were recorded by the deterministic match."
                ),
            ),
            StrategyActionOut(
                priority=2,
                action="Determine whether the gaps are genuinely disqualifying.",
                rationale=(
                    "Absence of evidence is not evidence of absence; confirm before "
                    "concluding you are ineligible."
                ),
            ),
            StrategyActionOut(
                priority=3,
                action="Tailor the application toward transferable evidence.",
                rationale="Position confirmed experience against the closest requirements.",
            ),
            StrategyActionOut(
                priority=4,
                action="Apply only if you accept the stretch.",
                rationale="The decision remains with the candidate.",
            ),
        ]

    actions: list[StrategyActionOut] = []
    priority = 1

    if strengths:
        actions.append(
            StrategyActionOut(
                priority=priority,
                action="Lead with your strongest evidenced requirements: "
                + ", ".join(s.requirement_name for s in strengths[:4]),
                rationale="These are confirmed in your evidence for this specific role.",
            )
        )
        priority += 1

    if restrictions:
        actions.append(
            StrategyActionOut(
                priority=priority,
                action="Do not claim: " + ", ".join(
                    r.subject for r in restrictions[:6]
                ),
                rationale="These are not established in your confirmed evidence.",
            )
        )
        priority += 1

    if decision == Recommendation.APPLY_WITH_TAILORING.value and required_gaps:
        actions.append(
            StrategyActionOut(
                priority=priority,
                action="Address required gaps in your narrative without overstating "
                "them: " + ", ".join(g.requirement_name for g in required_gaps[:4]),
                rationale="Required gaps carry the most application risk.",
            )
        )
        priority += 1

    actions.extend(
        [
            StrategyActionOut(
                priority=priority,
                action="Generate the tailored CV, then review it.",
                rationale="Documents are validated automatically; review the findings.",
            ),
            StrategyActionOut(
                priority=priority + 1,
                action="Generate the cover letter, then review it.",
                rationale="Confirm the reasoning is evidence-backed before sending.",
            ),
            StrategyActionOut(
                priority=priority + 2,
                action="Confirm contact details and eligibility before submitting.",
                rationale="The system never infers contact or eligibility information.",
            ),
            StrategyActionOut(
                priority=priority + 3,
                action="Submit the application.",
                rationale="Decision and preparation are complete.",
            ),
        ]
    )
    return actions


# --------------------------------------------------------------------------- #
# strategy validation (spec section 20)
# --------------------------------------------------------------------------- #


def validate_strategy(
    strategy: ApplicationStrategy, profile: ProfileSummary
) -> list[ValidationIssue]:
    """Check the strategy itself introduces no candidate fact.

    A strategy is an interpretation of evidence, so it is validated the same way
    generated documents are. Returns findings; an empty list means the strategy
    is fully grounded.
    """
    issues: list[ValidationIssue] = []
    idx = build_index(profile)
    support = idx.all_support()

    def add(code: str, message: str, detail: str, severity: str = "error") -> None:
        issues.append(
            ValidationIssue(
                severity=severity,
                code=code,
                message=message,
                detail=detail,
                claim_severity=severity.upper(),
                action="Correct the strategy; it must remain evidence-grounded.",
            )
        )

    valid_decisions = {r.value for r in Recommendation}
    if strategy.decision not in valid_decisions:
        add(
            "STRATEGY_INVALID_DECISION",
            f"Strategy decision '{strategy.decision}' is not a valid recommendation.",
            strategy.decision,
        )

    for strength in strategy.strengths:
        if not strength.evidence_ids:
            add(
                "STRATEGY_UNSUPPORTED_STRENGTH",
                f"Strength '{strength.requirement_name}' has no evidence provenance.",
                strength.statement,
            )
        elif not any(label in _labels(idx) for label in strength.evidence_ids):
            add(
                "STRATEGY_UNSUPPORTED_STRENGTH",
                f"Strength '{strength.requirement_name}' cites evidence that is not "
                "on the confirmed profile.",
                strength.statement,
            )

    forbidden = (
        "does not have", "has no experience", "lacks ", "never used",
        "cannot do", "is not authorized", "has no ",
    )
    for gap in strategy.gaps:
        low = gap.statement.lower()
        if any(f in low for f in forbidden):
            add(
                "STRATEGY_GAP_INTEGRITY",
                f"Gap for '{gap.requirement_name}' asserts factual absence. "
                "Absence of evidence must be reported as 'not established'.",
                gap.statement,
            )
        if gap.severity not in {s.value for s in GapSeverity}:
            add(
                "STRATEGY_INVALID_GAP_SEVERITY",
                f"Gap '{gap.requirement_name}' has unknown severity {gap.severity}.",
                gap.statement,
            )

    for blocker in strategy.blockers:
        if not blocker.requirement_name:
            add(
                "STRATEGY_UNSUPPORTED_BLOCKER",
                "A blocker was declared without naming a requirement.",
                blocker.statement,
            )

    for item in strategy.transferable_evidence:
        if not item.evidence_ids:
            add(
                "STRATEGY_UNSUPPORTED_TRANSFER",
                f"Transferable claim for '{item.requirement_name}' has no evidence.",
                item.statement,
            )
        elif not any(label in _labels(idx) for label in item.evidence_ids):
            add(
                "STRATEGY_UNSUPPORTED_TRANSFER",
                f"Transferable claim for '{item.requirement_name}' cites evidence "
                "that is not on the confirmed profile.",
                item.statement,
            )
        if item.relationship == EvidenceRelationship.UNCERTAIN.value:
            add(
                "STRATEGY_UNCERTAIN_TRANSFER_ASSERTED",
                f"'{item.requirement_name}' is marked UNCERTAIN and must not be "
                "presented as transferable support.",
                item.statement,
            )

    for restriction in strategy.claim_restrictions:
        if not restriction.reason:
            add(
                "STRATEGY_UNGROUNDED_RESTRICTION",
                f"Restriction on '{restriction.subject}' has no stated reason.",
                restriction.statement,
            )

    # A decision summary must not assert a candidate capability that is absent
    # from the evidence.
    for word in ("authorized", "authorised", "eligible", "visa", "sponsorship",
                 "security clearance", "citizen", "residency"):
        if word in strategy.decision_summary.lower() and word not in support:
            add(
                "STRATEGY_UNSUPPORTED_ELIGIBILITY",
                f"Decision summary asserts eligibility language ('{word}') that is "
                "not established in the candidate evidence.",
                strategy.decision_summary[:300],
            )

    return issues


def _labels(idx: EvidenceIndex) -> set[str]:
    return {item.label for item in idx.items}


# --------------------------------------------------------------------------- #
# narrative context + staleness
# --------------------------------------------------------------------------- #


def strategy_context(strategy: ApplicationStrategy, overall_score: float) -> StrategyContext:
    """Structured input for the narrative model (spec section 18)."""
    return StrategyContext(
        decision=strategy.decision,
        overall_score=overall_score,
        strengths=strategy.strengths,
        gaps=strategy.gaps,
        blockers=strategy.blockers,
        transferable_evidence=strategy.transferable_evidence,
        claim_restrictions=strategy.claim_restrictions,
    )


def evidence_fingerprint(profile: ProfileSummary, job) -> str:
    """Fingerprint of the evidence + requirement state a strategy was built from.

    Used to mark a strategy STALE when the candidate profile or the job
    requirements change (spec section 26). Not event sourcing - a plain digest.
    """
    payload = {
        "name": profile.name,
        "summary": profile.summary,
        "years": profile.years_of_experience,
        "skills": sorted({normalize_text(s.name) for s in profile.skills}),
        "experience": sorted(
            f"{normalize_text(e.company)}|{normalize_text(e.title)}|"
            f"{normalize_text(e.description)}"
            for e in profile.experience
        ),
        "education": sorted(
            f"{normalize_text(x.institution)}|{normalize_text(x.degree)}|"
            f"{normalize_text(x.field)}"
            for x in profile.education
        ),
        "requirements": sorted(
            f"{normalize_text(r.name)}|{normalize_text(r.description)}|{r.importance}"
            for r in job.requirements
        ),
    }
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


__all__ = [
    "RequirementRef",
    "build_strategy",
    "evidence_fingerprint",
    "relationship_for",
    "strategy_context",
    "validate_strategy",
]
