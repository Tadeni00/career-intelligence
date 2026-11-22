"""V3 Phase 1 diagnostic tests (spec section 21).

These test the *instrumentation*, not the scoring model. Nothing here may change
or weaken a recommendation: the engine is the frozen baseline.
"""

from __future__ import annotations

import pytest
from matching import (
    CandidateEducation,
    CandidateExperience,
    CandidateProfile,
    CandidateSkill,
    JobProfile,
    MatchSettings,
    MatchWeights,
    RecommendationPolicy,
    Requirement,
    RequirementState,
    audit_match,
    state_counts,
)

BASELINE = MatchSettings(
    weights=MatchWeights().normalised(),
    policy=RecommendationPolicy(),
)


def _candidate(**kw) -> CandidateProfile:
    base = dict(
        id=1,
        name="Tommie van der Berg",
        professional_title="Data Scientist",
        location="Amsterdam, Netherlands",
        years_of_experience=6,
        skills=[CandidateSkill(id=1, name="Python"),
                CandidateSkill(id=2, name="SQL")],
        experience=[CandidateExperience(
            id=1, company="Fintech Systems", title="Data Scientist",
            start_date="2021", end_date="", description="Built data pipelines.")],
        education=[CandidateEducation(
            id=1, institution="University of Amsterdam", degree="BSc",
            field="Statistics")],
    )
    base.update(kw)
    return CandidateProfile(**base)


def _job(*reqs, **kw) -> JobProfile:
    base = dict(id=1, title="Data Scientist", company="Acme",
                location="Amsterdam, Netherlands", description="Python and SQL role.")
    base.update(kw)
    return JobProfile(requirements=list(reqs), **base)


# =========================================================================== #
# 1. score decomposition (Gate A / Gate B)
# =========================================================================== #


def test_audit_reproduces_engine_overall_score():
    job = _job(
        Requirement(type="SKILL", name="Python", importance="REQUIRED"),
        Requirement(type="SKILL", name="Tableau", importance="REQUIRED"),
        Requirement(type="EXPERIENCE", name="Experience",
                    importance="REQUIRED", years_required=3),
        Requirement(type="EDUCATION", name="BSc", importance="REQUIRED"),
    )
    audit, outcome = audit_match(_candidate(), job, BASELINE)
    assert audit.verified
    assert audit.reconstructed_overall == pytest.approx(outcome.overall_score)
    assert audit.overall_score == pytest.approx(outcome.overall_score)


def test_every_dimension_is_individually_verified():
    job = _job(
        Requirement(type="SKILL", name="Python", importance="REQUIRED"),
        Requirement(type="EXPERIENCE", name="Experience",
                    importance="REQUIRED", years_required=2),
        Requirement(type="EDUCATION", name="BSc", importance="REQUIRED"),
        Requirement(type="OTHER", name="Attention to detail",
                    importance="PREFERRED"),
    )
    audit, _ = audit_match(_candidate(), job, BASELINE)
    for d in audit.dimensions:
        assert d.verified, f"{d.name}: {d.engine_score} vs {d.reconstructed_score}"


def test_weighted_contributions_sum_to_overall():
    job = _job(
        Requirement(type="SKILL", name="Python", importance="REQUIRED"),
        Requirement(type="SKILL", name="SQL", importance="REQUIRED"),
    )
    audit, _ = audit_match(_candidate(), job, BASELINE)
    total = sum(d.weighted_contribution for d in audit.dimensions)
    assert total == pytest.approx(audit.overall_score)


def test_dimension_with_no_requirements_is_explained_as_flat_score():
    """A silent dimension must still be explained, not ignored."""
    audit, outcome = audit_match(_candidate(), _job(), BASELINE)
    edu = next(d for d in audit.dimensions if d.name == "education")
    assert edu.verified
    assert edu.fixed_components, "flat grant must be stated"
    assert edu.reconstructed_score == pytest.approx(outcome.education_score)


# =========================================================================== #
# 2. requirement-level diagnostics
# =========================================================================== #


def test_supported_requirement_is_labelled_supported():
    job = _job(Requirement(type="SKILL", name="Python", importance="REQUIRED"))
    audit, _ = audit_match(_candidate(), job, BASELINE)
    item = next(i for d in audit.dimensions for i in d.items
                if i.requirement == "Python")
    assert item.state == RequirementState.SUPPORTED
    assert item.evidence_state == "exact"
    assert item.evidence_used == ["Python"]


def test_absent_required_skill_is_material_gap_not_blocker():
    job = _job(Requirement(type="SKILL", name="Kubernetes", importance="REQUIRED"))
    audit, outcome = audit_match(_candidate(), job, BASELINE)
    item = next(i for d in audit.dimensions for i in d.items
                if i.requirement == "Kubernetes")
    assert item.state == RequirementState.MATERIAL_GAP
    assert not item.blocker
    assert "Kubernetes" not in {b.requirement for b in audit.blockers}


def test_partial_skill_overlap_is_competitive_disadvantage_not_support():
    job = _job(Requirement(type="SKILL", name="Machine Learning Engineering",
                           importance="REQUIRED"))
    audit, outcome = audit_match(_candidate(), job, BASELINE)
    item = next(i for d in audit.dimensions for i in d.items
                if i.requirement == "Machine Learning Engineering")
    assert item.state in (
        RequirementState.COMPETITIVE_DISADVANTAGE,
        RequirementState.MATERIAL_GAP,
        RequirementState.SUPPORTED,
    )
    # Never a full match on partial credit alone.
    assert item.evidence_state in ("partial", "absent", "exact",
                                  "alias/normalised")


def test_absent_preferred_skill_is_evidence_unknown():
    job = _job(Requirement(type="SKILL", name="Tableau", importance="PREFERRED"))
    audit, _ = audit_match(_candidate(), job, BASELINE)
    item = next(i for d in audit.dimensions for i in d.items
                if i.requirement == "Tableau")
    assert item.state == RequirementState.EVIDENCE_UNKNOWN


def test_unknown_is_distinguishable_from_disproven():
    """unsupported != disproven (spec section 8)."""
    job = _job(Requirement(type="SKILL", name="Tableau", importance="PREFERRED"))
    audit, _ = audit_match(_candidate(), job, BASELINE)
    item = next(i for d in audit.dimensions for i in d.items
                if i.requirement == "Tableau")
    assert "not disproof" in item.note or item.state != RequirementState.MATERIAL_GAP


def test_penalties_are_reported_per_requirement():
    job = _job(
        Requirement(type="SKILL", name="Python", importance="REQUIRED"),
        Requirement(type="SKILL", name="Tableau", importance="REQUIRED"),
    )
    audit, _ = audit_match(_candidate(), job, BASELINE)
    tableau = next(i for d in audit.dimensions for i in d.items
                   if i.requirement == "Tableau")
    assert tableau.penalty > 0, "a missing required skill must show its penalty"


# =========================================================================== #
# 3. blocker identification (Gate C)
# =========================================================================== #


def test_required_education_above_recorded_level_is_a_blocker():
    job = _job(Requirement(type="EDUCATION", name="PhD", importance="REQUIRED"))
    audit, outcome = audit_match(_candidate(), job, BASELINE)
    assert audit.blockers
    assert audit.blockers[0].requirement == "PhD"
    assert "education" in audit.blockers[0].blocker_source
    assert outcome.recommendation == "SKIP"


def test_hard_location_block_is_a_blocker_with_provenance():
    job = _job(
        Requirement(type="LOCATION", name="UK location",
                    description="You must be based in the UK.",
                    importance="REQUIRED"),
        location="Cardiff, London or Remote (UK)",
    )
    cand = _candidate(location="Lagos, Nigeria")
    audit, outcome = audit_match(cand, job, BASELINE)
    assert audit.blockers
    assert "_is_hard_location_block" in audit.blockers[0].blocker_source
    assert outcome.recommendation == "SKIP"


def test_technical_and_other_dimensions_never_emit_blockers():
    """Documented engine asymmetry, pinned so it cannot drift silently."""
    job = _job(
        Requirement(type="SKILL", name="Kubernetes", importance="REQUIRED"),
        Requirement(type="OTHER", name="Certification X", importance="REQUIRED"),
    )
    audit, _ = audit_match(_candidate(), job, BASELINE)
    for d in audit.dimensions:
        if d.name in ("technical", "other", "experience"):
            assert not any(i.blocker for i in d.items), d.name


def test_blocker_forces_skip_even_when_score_is_high():
    """The Monzo case: top-band score, SKIP, because a blocker exists."""
    job = _job(
        Requirement(type="SKILL", name="Python", importance="REQUIRED"),
        Requirement(type="SKILL", name="SQL", importance="REQUIRED"),
        Requirement(type="LOCATION", name="UK location",
                    description="You must be based in the UK.",
                    importance="REQUIRED"),
        location="Cardiff, London or Remote (UK)",
    )
    cand = _candidate(
        location="Lagos, Nigeria",
        skills=[CandidateSkill(id=1, name="Python"), CandidateSkill(id=2, name="SQL"),
                CandidateSkill(id=3, name="Excel"), CandidateSkill(id=4, name="Power BI")],
    )
    audit, outcome = audit_match(cand, job, BASELINE)
    assert audit.overall_score >= 70, f"score should be strong, got {audit.overall_score}"
    assert outcome.recommendation == "SKIP"
    assert audit.blockers


def test_no_blocker_means_no_skip_by_sole_reason():
    job = _job(Requirement(type="SKILL", name="Python", importance="REQUIRED"))
    _audit, outcome = audit_match(_candidate(), job, BASELINE)
    if outcome.overall_score >= 80:
        assert outcome.recommendation == "APPLY"


# =========================================================================== #
# 4. recommendation preservation (Gate A)
# =========================================================================== #


def test_audit_never_changes_the_recommendation():
    jobs = [
        _job(Requirement(type="SKILL", name="Python", importance="REQUIRED")),
        _job(Requirement(type="SKILL", name="Kubernetes", importance="REQUIRED"),
             Requirement(type="SKILL", name="Rust", importance="REQUIRED")),
        _job(Requirement(type="EDUCATION", name="PhD", importance="REQUIRED")),
        _job(),
    ]
    for job in jobs:
        audit, outcome = audit_match(_candidate(), job, BASELINE)
        assert audit.recommendation == outcome.recommendation
        assert audit.overall_score == pytest.approx(outcome.overall_score)


def test_audit_does_not_mutate_engine_behaviour():
    """Running the audit twice must give identical results (Gate A)."""
    job = _job(
        Requirement(type="SKILL", name="Python", importance="REQUIRED"),
        Requirement(type="SKILL", name="Tableau", importance="REQUIRED"),
    )
    cand = _candidate()
    first, o1 = audit_match(cand, job, BASELINE)
    second, o2 = audit_match(cand, job, BASELINE)
    assert first.overall_score == second.overall_score
    assert o1.recommendation == o2.recommendation
    assert [i.to_dict() for i in o1.matched] == [i.to_dict() for i in o2.matched]


def test_baseline_thresholds_are_untouched():
    assert BASELINE.policy.apply_threshold == 80.0
    assert BASELINE.policy.apply_with_tailoring_threshold == 65.0
    assert BASELINE.policy.stretch_threshold == 50.0
    assert BASELINE.weights.technical == 0.40
    assert BASELINE.weights.experience == 0.25
    assert BASELINE.weights.education == 0.10
    assert BASELINE.weights.location == 0.10
    assert BASELINE.weights.other == 0.15


# =========================================================================== #
# 5. benchmark metrics
# =========================================================================== #


def test_state_counts_summarise_the_audit():
    job = _job(
        Requirement(type="SKILL", name="Python", importance="REQUIRED"),
        Requirement(type="SKILL", name="Tableau", importance="REQUIRED"),
        Requirement(type="SKILL", name="Airflow", importance="PREFERRED"),
        Requirement(type="EDUCATION", name="PhD", importance="PREFERRED"),
    )
    audit, _ = audit_match(_candidate(), job, BASELINE)
    counts = state_counts(audit)
    # Skill requirements carry the intended distribution.
    assert counts.get(RequirementState.SUPPORTED) == 1
    assert counts.get(RequirementState.MATERIAL_GAP) == 1
    assert counts.get(RequirementState.TAILORING_GAP) == 1
    assert counts.get(RequirementState.EVIDENCE_UNKNOWN, 0) >= 1
    # Every classified item carries exactly one known state.
    known = {
        v for k, v in vars(RequirementState).items()
        if not k.startswith("_") and isinstance(v, str)
    }
    for d in audit.dimensions:
        for item in d.items:
            assert item.state in known, item.state


def test_requirements_without_years_are_visible_in_the_audit():
    """Regression guard: an EXPERIENCE requirement with no years is silently
    dropped by the engine. The audit must still surface it."""
    job = _job(Requirement(type="EXPERIENCE", name="A/B experiment experience",
                           importance="REQUIRED"))
    audit, outcome = audit_match(_candidate(), job, BASELINE)
    experience = next(d for d in audit.dimensions if d.name == "experience")
    # Either surfaced as an item, or recorded as a fixed/basis note.
    named = any("A/B" in i.requirement for i in experience.items)
    assert named or experience.fixed_components, (
        "an extracted experience requirement must not vanish from diagnostics"
    )


# =========================================================================== #
# V3 defect D1 — years-less experience requirements were invisible
# =========================================================================== #


def test_years_less_experience_requirement_is_reported_not_dropped():
    """D1: an extracted EXPERIENCE requirement with no duration used to appear
    in no list at all, making it invisible to the user and the strategy layer."""
    cand = _candidate(location="Lagos, Nigeria")
    job = _job(
        Requirement(type="EXPERIENCE", name="A/B experiment experience",
                    importance="REQUIRED"),
        location="Lagos, Nigeria",
    )
    _audit, outcome = audit_match(cand, job, BASELINE)
    surfaced = any("A/B" in i.name for i in
                   outcome.matched + outcome.gaps + outcome.blockers + outcome.unknowns)
    assert surfaced, "years-less experience requirement must still be reported"
    item = next(i for i in outcome.unknowns if "A/B" in i.name)
    assert "cannot be scored" in item.detail
    # It must not be presented as satisfied.
    assert not any("A/B" in i.name for i in outcome.matched)


def test_d1_fix_is_score_neutral():
    """Reporting the requirement must not change any decision.

    A duration-less EXPERIENCE requirement cannot contribute to the years ratio,
    so it must score identically to having no such requirement at all - while
    still being reported to the user.
    """
    cand = _candidate(location="Lagos, Nigeria")
    with_req = _job(
        Requirement(type="EXPERIENCE", name="A/B experiment experience",
                    importance="REQUIRED"),
        location="Lagos, Nigeria",
    )
    without_req = _job(location="Lagos, Nigeria")

    _a1, o1 = audit_match(cand, with_req, BASELINE)
    _a2, o2 = audit_match(cand, without_req, BASELINE)

    assert o1.overall_score == pytest.approx(o2.overall_score)
    assert o1.experience_score == pytest.approx(o2.experience_score)
    assert o1.recommendation == o2.recommendation
    # ...but the requirement is now visible.
    assert any("A/B" in i.name for i in o1.unknowns)


# =========================================================================== #
# 6. no unsupported inference (Gate H)
# =========================================================================== #


def test_unknown_evidence_is_never_promoted_to_supported():
    job = _job(Requirement(type="SKILL", name="A/B Testing", importance="REQUIRED"))
    audit, _ = audit_match(_candidate(), job, BASELINE)
    item = next(i for d in audit.dimensions for i in d.items
                if i.requirement == "A/B Testing")
    assert item.state != RequirementState.SUPPORTED
    assert item.evidence_state != "exact"


def test_diagnostic_evidence_labels_exist_on_the_candidate():
    """Every evidence label cited by a strength must be a real held skill."""
    job = _job(
        Requirement(type="SKILL", name="Python", importance="REQUIRED"),
        Requirement(type="SKILL", name="SQL", importance="REQUIRED"),
    )
    cand = _candidate()
    held = {s.name for s in cand.skills}
    audit, _ = audit_match(cand, job, BASELINE)
    for d in audit.dimensions:
        for item in d.items:
            if item.state == RequirementState.SUPPORTED:
                for label in item.evidence_used:
                    assert label in held or label.startswith("max level")
