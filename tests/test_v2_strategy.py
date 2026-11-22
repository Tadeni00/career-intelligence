"""V2 Application Strategy tests (spec section 28).

The strategy layer must be evidence-grounded, must never recompute the
decision, must not convert "not established" into "does not have", and must not
weaken any V1.1/V1.2 safety guarantee.
"""

from __future__ import annotations

import pytest
from app.models import EvidenceRelationship, GapSeverity, Recommendation
from app.schemas import (
    ApplicationStrategy,
    CandidateSkillOut,
    EducationOut,
    ExperienceOut,
    ProfileSummary,
    ProjectOut,
    StrategyBlockerOut,
    StrategyContext,
    StrategyGapOut,
    StrengthOut,
    TransferableEvidenceOut,
)
from app.services import strategy as strategy_service
from matching import MatchItem, MatchOutcome

# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #


@pytest.fixture
def profile() -> ProfileSummary:
    return ProfileSummary(
        id=1,
        name="Tommie van der Berg",
        professional_title="Data Scientist",
        location="Amsterdam, Netherlands",
        years_of_experience=6,
        summary=("Data professional with 6+ years of experience in quantitative "
                 "data analysis and applied machine learning."),
        skills=[CandidateSkillOut(id=i, name=n) for i, n in enumerate(
            ["Python", "SQL", "Statistics", "Machine Learning", "Pandas"])],
        experience=[ExperienceOut(
            id=1, company="Fintech Systems", title="Data Scientist",
            start_date="2021", is_current=True,
            description=("Built automated data pipelines supporting repeatable "
                         "data preparation, analysis and validation workflows."))],
        education=[EducationOut(id=1, institution="University of Amsterdam",
                                degree="BSc", field="Statistics")],
        projects=[ProjectOut(id=1, name="Fraud detection capstone",
                             description="Built fraud classification models.",
                             technologies=["Python", "scikit-learn"])],
    )


class _Req:
    def __init__(self, rid, name, importance="REQUIRED", rtype="SKILL",
                 description="", years=None):
        self.id = rid
        self.name = name
        self.importance = importance
        self.requirement_type = rtype
        self.description = description
        self.years_required = years


class _Job:
    def __init__(self, requirements):
        self.requirements = requirements
        self.title = "Data Scientist"
        self.company = "Acme"
        self.description = " ".join(r.name for r in requirements)


def _outcome(**kw) -> MatchOutcome:
    base = dict(
        technical_score=80.0, experience_score=75.0, education_score=90.0,
        location_score=60.0, other_score=70.0, overall_score=76.0,
        recommendation=Recommendation.APPLY_WITH_TAILORING.value,
        confidence=0.7, explanation="Deterministic explanation.",
    )
    base.update(kw)
    return MatchOutcome(**base)


# --------------------------------------------------------------------------- #
# Gate A - decision preservation
# --------------------------------------------------------------------------- #


def test_strategy_preserves_recommendation(profile):
    for rec in Recommendation:
        job = _Job([_Req(1, "Python")])
        s = strategy_service.build_strategy(
            profile, job,
            _outcome(recommendation=rec.value,
                     matched=[MatchItem("SKILL", "Python", importance="REQUIRED")]),
        )
        assert s.decision == rec.value, rec


def test_strategy_does_not_recompute_score(profile):
    """The strategy layer has no score input; it cannot invent one."""
    job = _Job([_Req(1, "Python")])
    s = strategy_service.build_strategy(profile, job, _outcome(overall_score=11.0))
    assert s.decision == Recommendation.APPLY_WITH_TAILORING.value
    assert not hasattr(s, "overall_score")


# --------------------------------------------------------------------------- #
# Gate B - evidence grounding
# --------------------------------------------------------------------------- #


def test_strength_requires_evidence(profile):
    job = _Job([_Req(1, "Python")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(matched=[MatchItem("SKILL", "Python", importance="REQUIRED")]),
    )
    assert s.strengths, "Python is evidenced and must appear as a strength"
    for strength in s.strengths:
        assert strength.evidence_ids, "every strength needs provenance"


def test_strength_with_fabricated_evidence_is_rejected(profile):
    s = ApplicationStrategy(
        decision="APPLY",
        strengths=[StrengthOut(requirement_name="Kubernetes",
                               evidence_ids=["Kubernetes"],
                               statement="Built Kubernetes platforms.")],
    )
    issues = strategy_service.validate_strategy(s, profile)
    codes = {i.code for i in issues}
    assert "STRATEGY_UNSUPPORTED_STRENGTH" in codes


def test_strength_without_provenance_is_rejected(profile):
    s = ApplicationStrategy(
        decision="APPLY",
        strengths=[StrengthOut(requirement_name="Python", evidence_ids=[],
                               statement="Expert Python.")],
    )
    codes = {i.code for i in strategy_service.validate_strategy(s, profile)}
    assert "STRATEGY_UNSUPPORTED_STRENGTH" in codes


# --------------------------------------------------------------------------- #
# Gate C - gap integrity
# --------------------------------------------------------------------------- #


def test_gap_says_not_established_not_does_not_have(profile):
    job = _Job([_Req(1, "AWS", "REQUIRED")])
    s = strategy_service.build_strategy(
        profile, job, _outcome(gaps=[MatchItem("SKILL", "AWS",
                                               importance="REQUIRED")]),
    )
    assert s.gaps
    text = " ".join(g.statement for g in s.gaps).lower()
    assert "not established" in text
    for forbidden in ("does not have", "has no experience", "lacks ", "never used"):
        assert forbidden not in text


@pytest.mark.parametrize("forbidden", [
    "The candidate does not have AWS.",
    "Candidate has no experience with AWS.",
    "Candidate lacks AWS skills.",
    "Candidate never used AWS.",
])
def test_gap_asserting_absence_is_rejected(profile, forbidden):
    s = ApplicationStrategy(
        decision="SKIP",
        gaps=[StrategyGapOut(requirement_name="AWS", importance="REQUIRED",
                             severity="REQUIRED_GAP", statement=forbidden)],
    )
    codes = {i.code for i in strategy_service.validate_strategy(s, profile)}
    assert "STRATEGY_GAP_INTEGRITY" in codes


def test_gap_severity_respects_importance(profile):
    reqs = [_Req(1, "AWS", "REQUIRED"), _Req(2, "Airflow", "PREFERRED")]
    job = _Job(reqs)
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(gaps=[MatchItem("SKILL", "AWS", importance="REQUIRED"),
                       MatchItem("SKILL", "Airflow", importance="PREFERRED")]),
    )
    by_name = {g.requirement_name: g.severity for g in s.gaps}
    assert by_name["AWS"] == GapSeverity.REQUIRED.value
    assert by_name["Airflow"] == GapSeverity.PREFERRED.value
    # A missing preferred skill must not carry the same urgency as required.
    assert by_name["AWS"] != by_name["Airflow"]


def test_soft_signal_gap_is_downgraded(profile):
    # "attention to detail" is a declared soft signal in the V1.1 vocabulary.
    job = _Job([_Req(1, "Attention to detail", "PREFERRED")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(gaps=[MatchItem("OTHER", "Attention to detail",
                                 importance="PREFERRED")]),
    )
    assert s.gaps and s.gaps[0].severity == GapSeverity.SOFT_SIGNAL.value


# --------------------------------------------------------------------------- #
# Gate D - blocker integrity
# --------------------------------------------------------------------------- #


def test_blocker_is_sourced_from_match_blockers(profile):
    job = _Job([_Req(1, "United States work authorization", "REQUIRED",
                     "LOCATION")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(recommendation=Recommendation.SKIP.value,
                 blockers=[MatchItem("LOCATION", "United States work authorization",
                                     importance="REQUIRED")]),
    )
    assert s.blockers
    assert "not established" in s.blockers[0].statement.lower()
    # The primary action for a blocker-led SKIP is to stop, not to apply.
    assert "application effort" in s.actions[0].action.lower()
    assert "not established" in s.actions[0].rationale.lower()


def test_blocker_without_requirement_is_rejected(profile):
    s = ApplicationStrategy(
        decision="SKIP",
        blockers=[StrategyBlockerOut(requirement_name="",
                                     statement="Something is wrong.")],
    )
    codes = {i.code for i in strategy_service.validate_strategy(s, profile)}
    assert "STRATEGY_UNSUPPORTED_BLOCKER" in codes


def test_strategy_never_invents_a_blocker(profile):
    """Blockers come only from the deterministic match, never from absence."""
    job = _Job([_Req(1, "AWS", "REQUIRED")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(gaps=[MatchItem("SKILL", "AWS", importance="REQUIRED")]),
    )
    assert s.gaps and not s.blockers


# --------------------------------------------------------------------------- #
# Gate E - claim restrictions
# --------------------------------------------------------------------------- #


def test_missing_evidence_becomes_restriction(profile):
    job = _Job([_Req(1, "AWS", "REQUIRED")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(gaps=[MatchItem("SKILL", "AWS", importance="REQUIRED")]),
    )
    subjects = {r.subject for r in s.claim_restrictions}
    assert "AWS" in subjects
    for r in s.claim_restrictions:
        assert r.reason, "a restriction must state its ground"


def test_restriction_without_reason_is_rejected(profile):
    from app.schemas import ClaimRestrictionOut

    s = ApplicationStrategy(
        decision="APPLY",
        claim_restrictions=[ClaimRestrictionOut(subject="AWS",
                                                statement="Do not claim AWS.",
                                                reason="")],
    )
    codes = {i.code for i in strategy_service.validate_strategy(s, profile)}
    assert "STRATEGY_UNGROUNDED_RESTRICTION" in codes


# --------------------------------------------------------------------------- #
# Gate F - transferable evidence
# --------------------------------------------------------------------------- #


def test_transferable_uses_confirmed_evidence(profile):
    job = _Job([_Req(1, "Experience building data pipelines", "REQUIRED",
                     "EXPERIENCE")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(matched=[MatchItem("EXPERIENCE",
                                    "Experience building data pipelines",
                                    importance="REQUIRED")]),
    )
    assert s.transferable_evidence
    for item in s.transferable_evidence:
        assert item.evidence_ids, "transferable needs evidence"
        assert item.relationship != EvidenceRelationship.UNCERTAIN.value


def test_transferable_with_fabricated_evidence_is_rejected(profile):
    s = ApplicationStrategy(
        decision="APPLY",
        transferable_evidence=[TransferableEvidenceOut(
            requirement_name="A/B testing", evidence_ids=["Globex"],
            relationship=EvidenceRelationship.TRANSFERABLE.value,
            confidence=0.9,
            statement="Ran A/B tests.")],
    )
    codes = {i.code for i in strategy_service.validate_strategy(s, profile)}
    assert "STRATEGY_UNSUPPORTED_TRANSFER" in codes


def test_uncertain_transfer_may_not_be_asserted(profile):
    s = ApplicationStrategy(
        decision="APPLY",
        transferable_evidence=[TransferableEvidenceOut(
            requirement_name="Kubernetes", evidence_ids=["Python"],
            relationship=EvidenceRelationship.UNCERTAIN.value,
            confidence=0.2,
            statement="Maybe transferable.")],
    )
    codes = {i.code for i in strategy_service.validate_strategy(s, profile)}
    assert "STRATEGY_UNCERTAIN_TRANSFER_ASSERTED" in codes


def test_transferable_without_evidence_is_rejected(profile):
    s = ApplicationStrategy(
        decision="APPLY",
        transferable_evidence=[TransferableEvidenceOut(
            requirement_name="A/B testing", evidence_ids=[],
            relationship=EvidenceRelationship.TRANSFERABLE.value,
            confidence=0.7, statement="Transferable.")],
    )
    codes = {i.code for i in strategy_service.validate_strategy(s, profile)}
    assert "STRATEGY_UNSUPPORTED_TRANSFER" in codes


def test_unsupported_requirement_is_never_transferable(profile):
    job = _Job([_Req(1, "Quantum computing", "REQUIRED")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(gaps=[MatchItem("SKILL", "Quantum computing",
                                 importance="REQUIRED")]),
    )
    assert not s.transferable_evidence


# --------------------------------------------------------------------------- #
# Gate F/G - strategy safety and eligibility
# --------------------------------------------------------------------------- #


def test_strategy_summary_cannot_assert_eligibility(profile):
    s = ApplicationStrategy(
        decision="APPLY",
        decision_summary="You are authorized to work in the United States.",
    )
    codes = {i.code for i in strategy_service.validate_strategy(s, profile)}
    assert "STRATEGY_UNSUPPORTED_ELIGIBILITY" in codes


def test_clean_strategy_validates(profile):
    job = _Job([_Req(1, "Python"), _Req(2, "AWS", "REQUIRED")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(matched=[MatchItem("SKILL", "Python", importance="REQUIRED")],
                 gaps=[MatchItem("SKILL", "AWS", importance="REQUIRED")]),
    )
    assert strategy_service.validate_strategy(s, profile) == []


def test_strategy_cannot_change_the_decision(profile):
    job = _Job([_Req(1, "Python")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(recommendation=Recommendation.SKIP.value,
                 blockers=[MatchItem("SKILL", "Python", importance="REQUIRED")]),
    )
    assert s.decision == Recommendation.SKIP.value


def test_invalid_decision_is_rejected(profile):
    s = ApplicationStrategy(decision="DEFINITELY_YES")
    codes = {i.code for i in strategy_service.validate_strategy(s, profile)}
    assert "STRATEGY_INVALID_DECISION" in codes


# --------------------------------------------------------------------------- #
# emphasis + actions
# --------------------------------------------------------------------------- #


def test_emphasis_prioritises_evidenced_material(profile):
    job = _Job([_Req(1, "Python"), _Req(2, "SQL")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(matched=[MatchItem("SKILL", "Python", importance="REQUIRED"),
                          MatchItem("SKILL", "SQL", importance="REQUIRED")]),
    )
    assert s.evidence_emphasis
    priorities = [e.priority for e in s.evidence_emphasis]
    assert priorities == sorted(priorities)


def test_skip_actions_do_not_elaborate(profile):
    job = _Job([_Req(1, "United States work authorization", "REQUIRED",
                     "LOCATION")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(recommendation=Recommendation.SKIP.value,
                 blockers=[MatchItem("LOCATION",
                                     "United States work authorization",
                                     importance="REQUIRED")]),
    )
    assert len(s.actions) <= 3
    assert "not established" in s.actions[0].rationale.lower()


def test_stretch_actions_cover_the_gaps(profile):
    job = _Job([_Req(1, "AWS", "REQUIRED")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(recommendation=Recommendation.STRETCH.value,
                 gaps=[MatchItem("SKILL", "AWS", importance="REQUIRED")]),
    )
    text = " ".join(a.action.lower() for a in s.actions)
    assert "missing requirements" in text or "requirements" in text
    assert len(s.actions) >= 3


def test_apply_with_tailoring_actions_are_practical(profile):
    job = _Job([_Req(1, "Python"), _Req(2, "AWS", "REQUIRED")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(matched=[MatchItem("SKILL", "Python", importance="REQUIRED")],
                 gaps=[MatchItem("SKILL", "AWS", importance="REQUIRED")]),
    )
    text = " ".join(a.action.lower() for a in s.actions)
    assert "do not claim" in text
    assert "eligibility" in text


# --------------------------------------------------------------------------- #
# narrative boundary (section 17/18)
# --------------------------------------------------------------------------- #


def test_narrative_context_carries_no_free_form_decision(profile):
    job = _Job([_Req(1, "Python")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(matched=[MatchItem("SKILL", "Python", importance="REQUIRED")]),
    )
    ctx = strategy_service.strategy_context(s, 76.0)
    assert isinstance(ctx, StrategyContext)
    assert ctx.decision == s.decision
    # The model receives facts, not an instruction to judge fit.
    assert not hasattr(ctx, "instructions")


# --------------------------------------------------------------------------- #
# staleness (section 26)
# --------------------------------------------------------------------------- #


def test_fingerprint_changes_when_evidence_changes(profile):
    job = _Job([_Req(1, "Python")])
    before = strategy_service.evidence_fingerprint(profile, job)

    mutated = profile.model_copy(deep=True)
    mutated.skills = [*mutated.skills, CandidateSkillOut(id=99, name="AWS")]
    after = strategy_service.evidence_fingerprint(mutated, job)
    assert before != after


def test_fingerprint_changes_when_requirements_change(profile):
    job = _Job([_Req(1, "Python")])
    before = strategy_service.evidence_fingerprint(profile, job)
    job2 = _Job([_Req(1, "Python"), _Req(2, "AWS", "REQUIRED")])
    assert before != strategy_service.evidence_fingerprint(profile, job2)


def test_fingerprint_is_stable_for_identical_state(profile):
    job = _Job([_Req(1, "Python")])
    assert (strategy_service.evidence_fingerprint(profile, job)
            == strategy_service.evidence_fingerprint(profile, job))


# --------------------------------------------------------------------------- #
# section 27 - no profile mutation
# --------------------------------------------------------------------------- #


def test_strategy_build_does_not_mutate_profile(profile):
    job = _Job([_Req(1, "AWS", "REQUIRED")])
    before = profile.model_dump_json()
    strategy_service.build_strategy(
        profile, job,
        _outcome(gaps=[MatchItem("SKILL", "AWS", importance="REQUIRED")]),
    )
    assert profile.model_dump_json() == before


def test_discovered_gap_is_not_added_to_profile(profile):
    job = _Job([_Req(1, "Kubernetes", "REQUIRED")])
    strategy_service.build_strategy(
        profile, job,
        _outcome(gaps=[MatchItem("SKILL", "Kubernetes", importance="REQUIRED")]),
    )
    assert "Kubernetes" not in {s.name for s in profile.skills}


# --------------------------------------------------------------------------- #
# usability invariants (regressions found during the real-world benchmark)
# --------------------------------------------------------------------------- #


def test_unmapped_requirements_are_aggregated_not_dumped(profile):
    """One note per unmapped requirement is a wall of text; aggregate instead."""
    reqs = [_Req(i, f"Tool{i}", "PREFERRED") for i in range(1, 9)]
    job = _Job(reqs)
    s = strategy_service.build_strategy(profile, job, _outcome())
    unmapped = [n for n in s.review_notes if "not mapped" in n.statement]
    assert len(unmapped) == 1, [n.statement for n in s.review_notes]
    # Nothing is hidden: every subject still appears in the note.
    note = unmapped[0].statement
    for i in range(1, 9):
        assert f"Tool{i}" in note


def test_skip_without_blocker_never_references_a_blocker(profile):
    job = _Job([_Req(1, "Python")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(recommendation=Recommendation.SKIP.value,
                 matched=[MatchItem("SKILL", "Python", importance="REQUIRED")]),
    )
    assert not s.blockers
    # Must not send the user to "review the stated blocker" when none exists.
    actions = " ".join(a.action.lower() for a in s.actions)
    assert "the stated blocker" not in actions
    assert "review the score breakdown" in actions
    for a in s.actions:
        assert a.priority in (1, 2), "a blockerless SKIP must stay short"


def test_single_character_terms_do_not_create_evidence(profile):
    """'B' inside 'B.Sc' must not manufacture provenance."""
    from app.services.evidence import build_index

    ref = strategy_service.RequirementRef(
        id=1, name="B experience", description="", importance="REQUIRED",
        type="EXPERIENCE",
    )
    rel, evidence, _conf = strategy_service.relationship_for(
        ref, build_index(profile)
    )
    assert evidence == [], f"spurious evidence match: {evidence}"
    assert rel is EvidenceRelationship.UNCERTAIN


def test_generic_only_requirement_reports_no_relationship(profile):
    """'Data analysis experience' has no assessable terms; do not invent one."""
    from app.services.evidence import build_index

    ref = strategy_service.RequirementRef(
        id=1, name="Data analysis experience", description="",
        importance="REQUIRED", type="EXPERIENCE",
    )
    rel, evidence, confidence = strategy_service.relationship_for(
        ref, build_index(profile)
    )
    assert rel is EvidenceRelationship.UNCERTAIN
    assert evidence == []
    assert confidence == 0.0


def test_partial_relationship_needs_two_real_terms(profile):
    from app.services.evidence import build_index

    ref = strategy_service.RequirementRef(
        id=1, name="Docker", description="", importance="PREFERRED",
        type="SKILL",
    )
    rel, _ev, _conf = strategy_service.relationship_for(ref, build_index(profile))
    assert rel is not EvidenceRelationship.PARTIAL


# --------------------------------------------------------------------------- #
# regression: V1.2 validator remains authoritative
# --------------------------------------------------------------------------- #


def test_strategy_constraints_are_prompt_guidance_only(profile):
    """Generation constraints are advisory; the validator still decides."""
    from app.services.generation import strategy_constraints

    assert callable(strategy_constraints)
    from app.services.validation import validate_cover_letter

    report = validate_cover_letter(
        "Dear Hiring Team,\n\nI reduced model error by 30%.\n\nKind regards",
        profile, "Data Scientist", "Acme",
    )
    from app.models import ValidationStatus

    assert report.status is ValidationStatus.VALIDATION_FAILED


def test_strategy_does_not_disable_validation(profile):
    job = _Job([_Req(1, "Python")])
    s = strategy_service.build_strategy(
        profile, job,
        _outcome(matched=[MatchItem("SKILL", "Python", importance="REQUIRED")]),
    )
    assert s.strengths
    # A valid strategy does not make an unsupported document acceptable.
    from app.services.validation import validate_cover_letter

    report = validate_cover_letter(
        "Dear Hiring Team,\n\nI have extensive experience with CatBoost.\n\n"
        "Kind regards", profile, "Data Scientist", "Acme",
    )
    assert report.status.value == "VALIDATION_FAILED"
