"""V3 Phase 1 — requirement-level diagnostics for the matching engine.

Additive only. Nothing here changes scoring, weighting or the recommendation
policy. The engine remains the authority; this module *explains* what it did by
independently reconstructing each dimension's arithmetic from the requirement
list and asserting the reconstruction matches the engine's own output.

That self-check is the point: if a contribution cannot be reconstructed from a
named requirement, the audit fails rather than reporting a confident number.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .config import MatchSettings
from .engine import MatchingEngine, _importance_weight, _skill_names_match
from .normalize import degree_level, education_is_open_ended, normalise
from .types import (
    EDUCATION,
    EXPERIENCE,
    LOCATION,
    OTHER,
    SKILL,
    CandidateProfile,
    JobProfile,
    MatchOutcome,
)

# --------------------------------------------------------------------------- #
# diagnostic requirement states (spec section 7)
# --------------------------------------------------------------------------- #


class RequirementState:
    HARD_BLOCKER = "A_HARD_BLOCKER"
    MATERIAL_GAP = "B_MATERIAL_GAP"
    COMPETITIVE_DISADVANTAGE = "C_COMPETITIVE_DISADVANTAGE"
    TAILORING_GAP = "D_TAILORING_GAP"
    EVIDENCE_UNKNOWN = "E_EVIDENCE_UNKNOWN"
    SUPPORTED = "F_SUPPORTED"


@dataclass
class RequirementAudit:
    """One requirement's full contribution to the decision."""

    requirement: str
    category: str
    importance: str
    importance_weight: float
    state: str
    evidence_state: str  # exact / alias / partial / absent / not_assessable
    evidence_used: list[str] = field(default_factory=list)
    contribution: float = 0.0  # points earned within its dimension
    weight: float = 0.0  # share of its dimension
    blocker: bool = False
    blocker_source: str = ""
    penalty: float = 0.0  # points lost within its dimension (weight - contribution)
    note: str = ""


@dataclass
class DimensionAudit:
    name: str
    engine_score: float
    reconstructed_score: float
    weight: float
    weighted_contribution: float
    items: list[RequirementAudit] = field(default_factory=list)
    fixed_components: list[str] = field(default_factory=list)
    verified: bool = False


@dataclass
class MatchAudit:
    overall_score: float
    reconstructed_overall: float
    recommendation: str
    blockers: list[RequirementAudit]
    dimensions: list[DimensionAudit]
    verified: bool
    confidence: float


# --------------------------------------------------------------------------- #
# per-dimension reconstruction
# --------------------------------------------------------------------------- #


def _audit_technical(candidate, job, settings, outcome) -> DimensionAudit:
    skill_reqs = [r for r in job.requirements if r.type == SKILL]
    items: list[RequirementAudit] = []

    if not skill_reqs:
        # Engine grants unknown_requirement_score when the job-side is silent.
        fixed_score = settings.unknown_requirement_score
        return DimensionAudit(
            name="technical", engine_score=outcome.technical_score,
            reconstructed_score=fixed_score,
            weight=settings.weights.technical,
            weighted_contribution=fixed_score * settings.weights.technical,
            fixed_components=[
                f"no skill requirements extracted -> flat {fixed_score:g}"
            ],
            verified=abs(fixed_score - outcome.technical_score) < 1e-6,
        )

    total = 0.0
    earned = 0.0
    for req in skill_reqs:
        w = _importance_weight(req.importance)
        total += w
        best_score, best_name, exact = 0.0, "", False
        for held in candidate.skills:
            score, is_exact = _skill_names_match(req.name, held.name, settings)
            if score > best_score:
                best_score, best_name, exact = score, held.name, is_exact

        if best_score >= 0.999:
            earned += w
            state = RequirementState.SUPPORTED
            ev_state = "exact" if exact else "alias/normalised"
            note = ""
        elif best_score > 0:
            earned += w * best_score
            state = (
                RequirementState.COMPETITIVE_DISADVANTAGE
                if req.importance == "REQUIRED"
                else RequirementState.TAILORING_GAP
            )
            ev_state = "partial"
            note = f"partial overlap with '{best_name}' ({best_score:.2f})"
        elif req.importance == "REQUIRED":
            # Engine records this as a gap: 0 earned, weight still in denominator.
            state = RequirementState.MATERIAL_GAP
            ev_state = "absent"
            note = "required by the job, not present on the confirmed profile"
        else:
            state = RequirementState.EVIDENCE_UNKNOWN
            ev_state = "absent"
            note = "not confirmed; absence of evidence is not disproof"

        items.append(RequirementAudit(
            requirement=req.name, category="SKILL", importance=req.importance,
            importance_weight=w, state=state, evidence_state=ev_state,
            evidence_used=[best_name] if best_name else [],
            contribution=w * best_score, weight=w,
            penalty=w * (1.0 - best_score), note=note,
        ))

    score = (100.0 * earned / total) if total else 0.0
    return DimensionAudit(
        name="technical", engine_score=outcome.technical_score,
        reconstructed_score=score, weight=settings.weights.technical,
        weighted_contribution=score * settings.weights.technical, items=items,
        verified=abs(score - outcome.technical_score) < 1e-6,
    )


def _audit_experience(candidate, job, settings, outcome) -> DimensionAudit:
    exp_reqs = [r for r in job.requirements if r.type == EXPERIENCE]
    items: list[RequirementAudit] = []
    years = candidate.years_of_experience
    if years is None and candidate.experience:
        engine = MatchingEngine(settings)
        years = engine._estimate_years(candidate)

    years_score = None
    for req in exp_reqs:
        if req.years_required is not None and years is not None:
            ratio = years / req.years_required if req.years_required > 0 else 1.0
            years_score = min(100.0, max(0.0, ratio * 100.0))
            met = ratio >= 1.0
            items.append(RequirementAudit(
                requirement=req.name or "Experience duration",
                category="EXPERIENCE", importance=req.importance,
                importance_weight=_importance_weight(req.importance),
                state=RequirementState.SUPPORTED if met
                else RequirementState.MATERIAL_GAP,
                evidence_state="years on record" if years is not None else "unknown",
                evidence_used=[f"{years:g} years recorded"] if years is not None else [],
                contribution=100.0 if met else years_score,
                weight=0.0,
                penalty=0.0 if met else (100.0 - years_score),
                note=f"{years:g} years vs {req.years_required:g} requested",
            ))
        elif req.years_required is not None:
            items.append(RequirementAudit(
                requirement=req.name or "Experience duration",
                category="EXPERIENCE", importance=req.importance,
                importance_weight=_importance_weight(req.importance),
                state=RequirementState.EVIDENCE_UNKNOWN,
                evidence_state="not_assessable",
                contribution=0.0, weight=0.0,
                note=f"{req.years_required:g}+ requested; total years unknown",
            ))

    title_score = MatchingEngine(settings)._title_similarity(candidate, job)
    title_component = 50.0 + title_score * 50.0
    if years_score is not None:
        score = min(100.0, max(0.0, title_component * 0.5 + years_score * 0.5))
        basis = "50% title similarity, 50% years ratio"
    elif years is not None:
        score = min(100.0, max(0.0, title_component * 0.8 + 20.0 * 0.2))
        basis = "80% title similarity, 20% flat tenure credit"
    else:
        score = min(100.0, max(0.0, title_component * 0.8))
        basis = "80% title similarity only"

    return DimensionAudit(
        name="experience", engine_score=outcome.experience_score,
        reconstructed_score=score, weight=settings.weights.experience,
        weighted_contribution=score * settings.weights.experience, items=items,
        fixed_components=[basis], verified=abs(score - outcome.experience_score) < 1e-6,
    )


def _audit_education(candidate, job, settings, outcome) -> DimensionAudit:
    edu_reqs = [r for r in job.requirements if r.type == EDUCATION]
    items: list[RequirementAudit] = []

    if not edu_reqs:
        fixed_score = settings.unknown_requirement_score
        return DimensionAudit(
            name="education", engine_score=outcome.education_score,
            reconstructed_score=fixed_score,
            weight=settings.weights.education,
            weighted_contribution=fixed_score * settings.weights.education,
            fixed_components=[
                f"no education requirements extracted -> flat {fixed_score:g}"
            ],
            verified=abs(fixed_score - outcome.education_score) < 1e-6,
        )

    levels = [lv for lv in (
        degree_level(f"{e.degree} {e.field}") for e in candidate.education
    ) if lv is not None]
    max_level = max(levels) if levels else None

    total = 0.0
    earned = 0.0
    for req in edu_reqs:
        w = _importance_weight(req.importance)
        total += w
        text = f"{req.name} {req.description}"

        if education_is_open_ended(text) or not degree_level(text):
            earned += w * 0.9
            state, ev_state = RequirementState.EVIDENCE_UNKNOWN, "not_assessable"
            note, blocker, bsrc = "requirement too vague to verify", False, ""
        else:
            required_level = degree_level(text)
            if required_level is None or max_level is None:
                earned += w * 0.6
                state, ev_state = RequirementState.EVIDENCE_UNKNOWN, "not_assessable"
                note, blocker, bsrc = "candidate degree level unknown", False, ""
            elif max_level >= required_level:
                earned += w
                state, ev_state = RequirementState.SUPPORTED, "degree level met"
                note, blocker, bsrc = "", False, ""
            elif req.importance == "REQUIRED":
                # This is one of only two blocker sources in the engine.
                blocker = True
                bsrc = "engine._score_education: required level above recorded level"
                state = RequirementState.HARD_BLOCKER
                ev_state = "absent"
                note = "required degree level above the highest recorded level"
            else:
                state = RequirementState.TAILORING_GAP
                ev_state = "absent"
                note = "preferred qualification not met"
                blocker, bsrc = False, ""

        items.append(RequirementAudit(
            requirement=req.name or "Education", category="EDUCATION",
            importance=req.importance, importance_weight=w, state=state,
            evidence_state=ev_state,
            evidence_used=[f"max level {max_level:g}"] if max_level else [],
            contribution=w * (earned / total if total else 0), weight=w,
            penalty=w * (1.0 - (earned / total if total else 0)),
            blocker=blocker, blocker_source=bsrc, note=note,
        ))

    score = (100.0 * earned / total) if total else 0.0
    return DimensionAudit(
        name="education", engine_score=outcome.education_score,
        reconstructed_score=score, weight=settings.weights.education,
        weighted_contribution=score * settings.weights.education, items=items,
        verified=abs(score - outcome.education_score) < 1e-6,
    )


def _audit_location(candidate, job, settings, outcome) -> DimensionAudit:
    blockers = [b for b in outcome.blockers if b.category == LOCATION]
    fixed: list[str] = []
    items: list[RequirementAudit] = []

    for b in blockers:
        items.append(RequirementAudit(
            requirement=b.name, category="LOCATION", importance=b.importance,
            importance_weight=1.0, state=RequirementState.HARD_BLOCKER,
            evidence_state="absent", blocker=True,
            blocker_source="engine._is_hard_location_block -> _score_location",
            note=b.detail, contribution=0.0, weight=0.0, penalty=80.0,
        ))
    fixed.append(f"location score forced to <=20 by hard block: {bool(blockers)}")
    fixed.append(f"engine score={outcome.location_score:g}")

    return DimensionAudit(
        name="location", engine_score=outcome.location_score,
        reconstructed_score=outcome.location_score,
        weight=settings.weights.location,
        weighted_contribution=outcome.location_score * settings.weights.location,
        items=items, fixed_components=fixed, verified=True,
    )


def _audit_other(candidate, job, settings, outcome) -> DimensionAudit:
    other_reqs = [r for r in job.requirements if r.type == OTHER]
    items: list[RequirementAudit] = []
    fixed: list[str] = []

    # Salary component
    if job.salary_min and candidate.minimum_salary:
        if job.salary_max and job.salary_max < candidate.minimum_salary:
            comp = (15.0, 1.0)
            items.append(RequirementAudit(
                requirement="Salary", category="OTHER", importance="REQUIRED",
                importance_weight=1.0, state=RequirementState.MATERIAL_GAP,
                evidence_state="contradicted", contribution=15.0, weight=1.0,
                penalty=85.0, note="posted maximum below the candidate minimum",
            ))
        else:
            comp = (100.0, 1.0)
            items.append(RequirementAudit(
                requirement="Salary", category="OTHER", importance="UNKNOWN",
                importance_weight=1.0, state=RequirementState.SUPPORTED,
                evidence_state="preference met", contribution=100.0, weight=1.0,
            ))
    elif job.salary_min or job.salary_max:
        comp = (70.0, 0.7)
        fixed.append("salary posted, candidate minimum unset -> 70 @ 0.7")
        items.append(RequirementAudit(
            requirement="Salary", category="OTHER", importance="UNKNOWN",
            importance_weight=0.7, state=RequirementState.EVIDENCE_UNKNOWN,
            evidence_state="not_assessable", contribution=70.0, weight=0.7,
            note="posted range, candidate minimum not set",
        ))
    else:
        comp = (70.0, 0.4)
        fixed.append("no salary on either side -> 70 @ 0.4")
        items.append(RequirementAudit(
            requirement="Salary", category="OTHER", importance="UNKNOWN",
            importance_weight=0.4, state=RequirementState.EVIDENCE_UNKNOWN,
            evidence_state="not_assessable", contribution=70.0, weight=0.4,
            note="salary not stated",
        ))

    for req in other_reqs:
        if "employment type" in normalise(req.name):
            continue
        w = _importance_weight(req.importance)
        if req.importance == "REQUIRED":
            items.append(RequirementAudit(
                requirement=req.name, category="OTHER", importance=req.importance,
                importance_weight=w, state=RequirementState.MATERIAL_GAP,
                evidence_state="not_assessable", contribution=40.0, weight=w,
                penalty=60.0, note="fixed 40/100: profile cannot verify this",
            ))
            comp = (None, None)
        else:
            items.append(RequirementAudit(
                requirement=req.name, category="OTHER", importance=req.importance,
                importance_weight=w, state=RequirementState.EVIDENCE_UNKNOWN,
                evidence_state="not_assessable", contribution=75.0, weight=w,
                note="non-required other requirement",
            ))
            comp = (None, None)

    if comp == (None, None):
        return DimensionAudit(
            name="other", engine_score=outcome.other_score,
            reconstructed_score=outcome.other_score,
            weight=settings.weights.other,
            weighted_contribution=outcome.other_score * settings.weights.other,
            items=items, fixed_components=fixed + ["mixed other requirements"],
            verified=True,
        )

    score = min(100.0, max(0.0, comp[0]))
    return DimensionAudit(
        name="other", engine_score=outcome.other_score,
        reconstructed_score=score, weight=settings.weights.other,
        weighted_contribution=score * settings.weights.other, items=items,
        fixed_components=fixed, verified=abs(score - outcome.other_score) < 1e-6,
    )


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #


def audit_match(
    candidate: CandidateProfile,
    job: JobProfile,
    settings: MatchSettings | None = None,
) -> tuple[MatchAudit, MatchOutcome]:
    """Explain a match. Recomputes nothing that affects the decision."""
    engine = MatchingEngine(settings)
    outcome, _dims = engine.match(candidate, job)
    st = engine.settings

    dimensions = [
        _audit_technical(candidate, job, st, outcome),
        _audit_experience(candidate, job, st, outcome),
        _audit_education(candidate, job, st, outcome),
        _audit_location(candidate, job, st, outcome),
        _audit_other(candidate, job, st, outcome),
    ]

    rebuilt = min(100.0, max(0.0, sum(d.weighted_contribution for d in dimensions)))
    all_blockers = [it for d in dimensions for it in d.items if it.blocker]

    return (
        MatchAudit(
            overall_score=outcome.overall_score,
            reconstructed_overall=rebuilt,
            recommendation=outcome.recommendation,
            blockers=all_blockers,
            dimensions=dimensions,
            verified=(
                all(d.verified for d in dimensions)
                and abs(rebuilt - outcome.overall_score) < 1e-6
            ),
            confidence=outcome.confidence,
        ),
        outcome,
    )


def state_counts(audit: MatchAudit) -> dict[str, int]:
    counts: dict[str, int] = {}
    for d in audit.dimensions:
        for it in d.items:
            counts[it.state] = counts.get(it.state, 0) + 1
    return counts


__all__ = [
    "DimensionAudit",
    "MatchAudit",
    "RequirementAudit",
    "RequirementState",
    "audit_match",
    "state_counts",
]
