"""Matching engine behaviour."""

from __future__ import annotations

import pytest
from matching import (
    CandidateEducation,
    CandidateExperience,
    CandidateProfile,
    CandidateSkill,
    JobProfile,
    MatchingEngine,
    MatchSettings,
    RecommendationPolicy,
    Requirement,
)
from matching.config import MatchWeights


def make_candidate(**overrides) -> CandidateProfile:
    profile = CandidateProfile(
        id=1,
        name="Tommie",
        professional_title="Data Scientist | Machine Learning Engineer",
        location="Amsterdam, Netherlands",
        years_of_experience=6,
        preferred_roles=["Data Scientist", "Machine Learning Engineer"],
        preferred_locations=["Amsterdam"],
        remote_preference="HYBRID",
        minimum_salary=70000,
        skills=[
            CandidateSkill(name="Python"),
            CandidateSkill(name="SQL"),
            CandidateSkill(name="Statistics"),
            CandidateSkill(name="Machine Learning"),
            CandidateSkill(name="PostgreSQL"),
            CandidateSkill(name="Model Evaluation"),
        ],
        experience=[
            CandidateExperience(
                title="Machine Learning Engineer",
                company="Fintech Systems",
                start_date="2021",
                end_date="",
                description="Built fraud detection models and evaluation pipelines.",
            ),
            CandidateExperience(
                title="Data Scientist",
                company="Analytics Works",
                start_date="2019",
                end_date="2021",
                description="Statistical modelling and ETL pipelines.",
            ),
        ],
        education=[
            CandidateEducation(
                institution="University of Amsterdam", degree="MSc", field="Data Science"
            )
        ],
    )
    for key, value in overrides.items():
        setattr(profile, key, value)
    return profile


def skill(name, importance="REQUIRED"):
    return Requirement(type="SKILL", name=name, importance=importance)


def run(candidate, job, settings=None):
    return MatchingEngine(settings).match(candidate, job)[0]


def test_strong_match_recommends_apply():
    job = JobProfile(
        title="Machine Learning Engineer",
        company="Company A",
        location="Amsterdam, Netherlands",
        remote_status="Hybrid",
        salary_min=80000,
        salary_max=100000,
        requirements=[
            skill("Python"),
            skill("Machine Learning"),
            skill("SQL"),
            skill("Statistics"),
            skill("Model Evaluation"),
        ],
    )
    outcome = run(make_candidate(), job)
    assert outcome.overall_score >= 80
    assert outcome.recommendation == "APPLY"
    assert {item.name for item in outcome.matched} >= {"Python", "SQL", "Statistics"}
    assert outcome.blockers == []
    assert "scores" in outcome.explanation


def test_partial_match_reports_gaps_not_blockers():
    job = JobProfile(
        title="Machine Learning Engineer",
        company="Company B",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Python"), skill("Kubernetes"), skill("Rust")],
    )
    outcome = run(make_candidate(), job)
    gap_names = {item.name for item in outcome.gaps}
    assert "Kubernetes" in gap_names
    assert "Rust" in gap_names
    assert outcome.blockers == []
    assert outcome.recommendation in {"STRETCH", "SKIP", "APPLY_WITH_TAILORING"}


def test_missing_required_skill_is_a_gap_and_reduces_score():
    with_gap = JobProfile(
        title="Machine Learning Engineer",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Python"), skill("Kubernetes")],
    )
    without_gap = JobProfile(
        title="Machine Learning Engineer",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Python")],
    )
    candidate = make_candidate()
    assert run(candidate, with_gap).overall_score < run(candidate, without_gap).overall_score


def test_missing_preferred_skill_is_unknown_not_gap():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Python"), skill("Tableau", importance="PREFERRED")],
    )
    outcome = run(make_candidate(), job)
    assert any(item.name == "Tableau" for item in outcome.unknowns)
    assert not any(item.name == "Tableau" for item in outcome.gaps)


def test_skill_aliases_are_recognised():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Postgres")],
    )
    outcome = run(make_candidate(), job)
    assert any(item.name == "Postgres" for item in outcome.matched)


def test_partial_skill_overlap_is_not_a_full_match():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Machine Learning Engineering")],
    )
    outcome = run(make_candidate(), job)
    assert not any(
        item.name == "Machine Learning Engineering" for item in outcome.matched
    )


def test_experience_match_and_gap():
    satisfied = JobProfile(
        title="Machine Learning Engineer",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[
            Requirement(
                type="EXPERIENCE", name="Machine learning experience", importance="REQUIRED", years_required=3
            )
        ],
    )
    outcome = run(make_candidate(), satisfied)
    assert outcome.experience_score > 50
    assert any(item.category == "EXPERIENCE" for item in outcome.matched)

    too_much = JobProfile(
        title="Machine Learning Engineer",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[
            Requirement(
                type="EXPERIENCE", name="Senior experience", importance="REQUIRED", years_required=15
            )
        ],
    )
    gap_outcome = run(make_candidate(), too_much)
    assert gap_outcome.experience_score < outcome.experience_score
    assert any(item.category == "EXPERIENCE" for item in gap_outcome.gaps)


def test_unknown_years_requirement_is_reported_as_unknown():
    job = JobProfile(
        title="Machine Learning Engineer",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[
            Requirement(type="EXPERIENCE", name="Experience", importance="REQUIRED", years_required=5)
        ],
    )
    outcome = run(make_candidate(years_of_experience=None, experience=[]), job)
    assert any(item.category == "EXPERIENCE" for item in outcome.unknowns)


def test_education_match():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[
            Requirement(type="EDUCATION", name="MSc in a quantitative field", importance="REQUIRED")
        ],
    )
    outcome = run(make_candidate(), job)
    assert outcome.education_score >= 80
    assert outcome.recommendation != "SKIP"


def test_education_blocker_forces_skip():
    job = JobProfile(
        title="Research Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[
            Requirement(type="EDUCATION", name="PhD in Machine Learning", importance="REQUIRED")
        ],
    )
    outcome = run(make_candidate(), job)
    assert outcome.blockers
    assert outcome.recommendation == "SKIP"
    assert "blocker" in outcome.explanation.lower()


def test_location_match():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam, Netherlands",
        remote_status="Hybrid",
        requirements=[skill("Python")],
    )
    outcome = run(make_candidate(), job)
    assert outcome.location_score >= 90


def test_remote_preference_conflict_is_a_gap():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="On-site",
        requirements=[skill("Python")],
    )
    outcome = run(make_candidate(remote_preference="REMOTE"), job)
    assert outcome.location_score < 60
    assert any(item.name == "On-site requirement" for item in outcome.gaps)


def test_hard_location_mismatch_is_a_blocker():
    job = JobProfile(
        title="Data Scientist",
        location="Tokyo, Japan",
        remote_status="On-site",
        requirements=[
            skill("Python"),
            Requirement(
                type="LOCATION",
                name="Based in Tokyo",
                description="You must be based in Tokyo.",
                importance="REQUIRED",
            ),
        ],
    )
    outcome = run(make_candidate(), job)
    assert outcome.blockers
    assert outcome.recommendation == "SKIP"


def test_remote_role_ignores_location_mismatch():
    job = JobProfile(
        title="Data Scientist",
        location="Tokyo, Japan",
        remote_status="Remote",
        requirements=[skill("Python")],
    )
    outcome = run(make_candidate(), job)
    assert not any(item.category == "LOCATION" for item in outcome.blockers)
    assert outcome.location_score > 50


def test_work_authorisation_is_unknown_not_blocker():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[
            skill("Python"),
            Requirement(
                type="LOCATION",
                name="Work authorization",
                description="Applicants must have the right to work in the Netherlands.",
                importance="REQUIRED",
            ),
        ],
    )
    outcome = run(make_candidate(), job)
    assert outcome.recommendation != "SKIP"
    assert any(item.category == "OTHER" for item in outcome.unknowns)


def test_salary_below_minimum_is_a_gap():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        salary_min=40000,
        salary_max=50000,
        requirements=[skill("Python")],
    )
    outcome = run(make_candidate(), job)
    assert any(item.name == "Salary" for item in outcome.gaps)


def test_unstated_salary_is_unknown():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Python")],
    )
    outcome = run(make_candidate(), job)
    assert any(item.name == "Salary" for item in outcome.unknowns)


def test_no_requirements_yields_neutral_dimensions():
    job = JobProfile(title="Data Scientist", location="Amsterdam", remote_status="Remote")
    outcome = run(make_candidate(), job)
    assert outcome.technical_score == 70.0
    assert outcome.education_score == 70.0
    assert any(item.category == "SKILL" for item in outcome.unknowns) is False


def test_candidate_without_skills_scores_zero_and_is_unknown():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Python")],
    )
    outcome = run(make_candidate(skills=[]), job)
    assert outcome.technical_score == 0.0
    assert any(item.name == "Candidate skill inventory" for item in outcome.unknowns)


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (95, "APPLY"),
        (80, "APPLY"),
        (79.9, "APPLY_WITH_TAILORING"),
        (65, "APPLY_WITH_TAILORING"),
        (64.9, "STRETCH"),
        (50, "STRETCH"),
        (49.9, "SKIP"),
        (0, "SKIP"),
    ],
)
def test_recommendation_thresholds(score, expected):
    policy = RecommendationPolicy(
        apply_threshold=80, apply_with_tailoring_threshold=65, stretch_threshold=50
    )
    assert policy.decide(score, has_blocker=False) == expected


def test_blocker_overrides_score():
    policy = RecommendationPolicy()
    assert policy.decide(99.0, has_blocker=True) == "SKIP"


def test_thresholds_are_configurable():
    policy = RecommendationPolicy(
        apply_threshold=95, apply_with_tailoring_threshold=90, stretch_threshold=85
    )
    assert policy.decide(85, has_blocker=False) == "STRETCH"
    assert policy.decide(92, has_blocker=False) == "APPLY_WITH_TAILORING"


def test_weights_are_configurable():
    skill_only = MatchSettings(
        weights=MatchWeights(
            technical=1.0, experience=0.0, education=0.0, location=0.0, other=0.0
        ).normalised()
    )
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Python"), skill("Kubernetes")],
    )
    outcome = run(make_candidate(), job, skill_only)
    assert outcome.overall_score == outcome.technical_score


def test_weights_normalise():
    weights = MatchWeights(
        technical=40, experience=25, education=10, location=10, other=15
    ).normalised()
    assert sum(
        [weights.technical, weights.experience, weights.education, weights.location, weights.other]
    ) == pytest.approx(1.0)


def test_confidence_reflects_profile_completeness():
    job = JobProfile(
        title="Data Scientist",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Python")],
    )
    rich = run(make_candidate(), job).confidence
    sparse = run(
        make_candidate(skills=[], experience=[], education=[], location="", years_of_experience=None),
        job,
    ).confidence
    assert rich > sparse


def test_seniority_penalty():
    job = JobProfile(
        title="Senior Machine Learning Engineer",
        location="Amsterdam",
        remote_status="Remote",
        requirements=[skill("Python")],
    )
    junior = run(make_candidate(years_of_experience=1, experience=[]), job)
    senior = run(make_candidate(years_of_experience=12), job)
    assert senior.experience_score >= junior.experience_score
