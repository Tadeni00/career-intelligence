"""V3 diagnostic completion — tests that lock in the D2 findings.

These assert the MEASURED behaviour of the extraction/sensitivity surface so it
cannot drift silently. None of them changes engine behaviour.
"""

from __future__ import annotations

import pytest
from matching import (
    CandidateProfile,
    CandidateSkill,
    JobProfile,
    MatchingEngine,
    MatchSettings,
    MatchWeights,
    RecommendationPolicy,
    Requirement,
)

BASELINE = MatchSettings(
    weights=MatchWeights().normalised(),
    policy=RecommendationPolicy(),
)

REQ = lambda t, n, imp="REQUIRED", years=None: Requirement(  # noqa: E731
    type=t, name=n, importance=imp, years_required=years
)


def _cand() -> CandidateProfile:
    return CandidateProfile(
        id=1, name="Test", professional_title="Data Scientist",
        location="Lagos, Nigeria", years_of_experience=6,
        skills=[CandidateSkill(id=1, name="Python"),
                CandidateSkill(id=2, name="SQL"),
                CandidateSkill(id=3, name="Power BI")],
    )


def _job(reqs, location="London, United Kingdom", title="Data Scientist"):
    return JobProfile(id=1, title=title, company="Acme", location=location,
                      requirements=list(reqs))


def _rec(reqs, **kw):
    out, _dims = MatchingEngine(BASELINE).match(_cand(), _job(reqs, **kw))
    return out


# =========================================================================== #
# Level 0 — cosmetic variation is genuinely score-neutral
# =========================================================================== #


def test_requirement_reordering_is_score_neutral():
    """M1: order carries no information for the engine."""
    reqs = [REQ("SKILL", "Python"), REQ("SKILL", "SQL"), REQ("SKILL", "Tableau")]
    a = _rec(reqs)
    b = _rec(list(reversed(reqs)))
    assert a.overall_score == pytest.approx(b.overall_score)
    assert a.recommendation == b.recommendation


def test_alias_renaming_is_score_neutral():
    """M2: the alias table absorbs surface variation."""
    a = _rec([REQ("SKILL", "Microsoft Excel")])
    b = _rec([REQ("SKILL", "Excel")])
    assert a.technical_score == pytest.approx(b.technical_score)
    assert a.recommendation == b.recommendation


# =========================================================================== #
# Level 2 — classification variance moves the score
# =========================================================================== #


def test_single_importance_change_moves_the_score():
    """M3: downgrading one unmet requirement from REQUIRED to PREFERRED RAISES
    the technical score, because an unmet REQUIRED item dilutes the ratio with
    weight 1.00 against 0.45. This is why one importance flip can cross a
    recommendation threshold."""
    required = _rec([REQ("SKILL", "Python"), REQ("SKILL", "SQL"),
                     REQ("SKILL", "Tableau")])
    preferred = _rec([REQ("SKILL", "Python"), REQ("SKILL", "SQL"),
                      REQ("SKILL", "Tableau", imp="PREFERRED")])
    assert preferred.technical_score > required.technical_score


def test_attaching_years_to_an_experience_requirement_moves_the_score():
    """M7: whether the extractor supplies a duration changes experience score."""
    without = _rec([REQ("EXPERIENCE", "ML experience")])
    with_years = _rec([REQ("EXPERIENCE", "ML experience", years=2)])
    assert with_years.experience_score != without.experience_score


def test_adding_an_absent_required_skill_lowers_the_score():
    """M5: an extra unmet required requirement dilutes the technical score."""
    base = _rec([REQ("SKILL", "Python"), REQ("SKILL", "SQL")])
    diluted = _rec([REQ("SKILL", "Python"), REQ("SKILL", "SQL"),
                    REQ("SKILL", "Kubernetes")])
    assert diluted.technical_score < base.technical_score


# =========================================================================== #
# Level 3 — blocker-bearing requirement classes change the decision
# =========================================================================== #


def test_adding_a_hard_location_requirement_forces_skip():
    """M8: location requirements act as a gate, not a weighted term."""
    reqs = [REQ("SKILL", "Python"), REQ("SKILL", "SQL")]
    assert _rec(reqs).recommendation != "SKIP"
    blocker_req = Requirement(
        type="LOCATION", name="UK location", importance="REQUIRED",
        description="You must be based in the UK.")
    outcome = _rec(reqs + [blocker_req])
    assert outcome.recommendation == "SKIP"
    assert outcome.blockers
    # The score is NOT what produced the SKIP.
    assert outcome.overall_score >= 50


def test_location_blocker_depends_on_description_wording_alone():
    """D3 fragility: the identical requirement blocks or does not purely on
    whether the description happens to contain a mandatory marker."""
    reqs = [REQ("SKILL", "Python"), REQ("SKILL", "SQL")]
    worded = Requirement(type="LOCATION", name="UK location",
                         importance="REQUIRED",
                         description="You must be based in the UK.")
    bare = Requirement(type="LOCATION", name="UK location",
                       importance="REQUIRED", description="")

    assert _rec(reqs + [worded]).recommendation == "SKIP"
    assert not _rec(reqs + [bare]).blockers
    assert _rec(reqs + [bare]).recommendation != "SKIP"


def test_required_degree_above_level_forces_skip_and_adds_a_blocker():
    """M10: the most decision-dominant requirement class."""
    from matching import CandidateEducation

    reqs = [REQ("SKILL", "Python"), REQ("SKILL", "SQL")]
    job = _job(reqs + [REQ("EDUCATION", "PhD")])
    with_bsc = CandidateProfile(
        id=1, name="Test", professional_title="Data Scientist",
        location="Lagos, Nigeria", years_of_experience=6,
        skills=_cand().skills,
        education=[CandidateEducation(id=1, institution="U", degree="BSc",
                                      field="Statistics")],
    )
    outcome, _dims = MatchingEngine(BASELINE).match(with_bsc, job)
    assert outcome.recommendation == "SKIP"
    assert any(b.category == "EDUCATION" for b in outcome.blockers)


def test_missing_required_skill_never_forces_skip_on_its_own():
    """M5 without a blocker: a missing required skill is a gap, not a gate."""
    outcome = _rec([REQ("SKILL", "Python"), REQ("SKILL", "Kubernetes")])
    assert not outcome.blockers
    assert outcome.recommendation != "SKIP" or outcome.overall_score < 50


# =========================================================================== #
# M11 — a lost extraction is silently OPTIMISTIC (highest-severity finding)
# =========================================================================== #


def test_lost_extraction_yields_a_positive_recommendation():
    """M11: with no requirements the job-side dimensions fall back to their
    neutral defaults (technical/education/other 70.0), and experience keeps
    credit from the candidate's own tenure. The result is a mid-APPLY score for
    a job the system never actually read. A degraded extraction therefore makes
    the system MORE positive, not less. Documented here; not changed."""
    outcome = _rec([])
    assert outcome.technical_score == pytest.approx(70.0)
    assert outcome.education_score == pytest.approx(70.0)
    assert outcome.other_score == pytest.approx(70.0)
    assert outcome.overall_score > 65
    assert outcome.recommendation == "APPLY_WITH_TAILORING"


def test_lost_extraction_flips_more_cases_than_any_other_mutation():
    """The parse-failure mode dominates every other instability class."""
    rich = [REQ("SKILL", "Python"), REQ("SKILL", "SQL"),
            REQ("SKILL", "Tableau"), REQ("SKILL", "LightGBM"),
            REQ("SKILL", "XGBoost"), REQ("SKILL", "CatBoost"),
            REQ("SKILL", "Airflow")]
    assert _rec(rich).recommendation == "STRETCH"
    assert _rec([]).recommendation == "APPLY_WITH_TAILORING"


# =========================================================================== #
# D2-D — schema/coercion asymmetry (deterministic)
# =========================================================================== #


def test_coercion_is_symmetric_across_string_and_structured_arrays():
    """V3.1 fixed the asymmetry: both array families are coerced.

    The V3 defect was that a bare string in a structured array invalidated the
    whole extraction. That is now recovered instead.
    """
    from app.ai.openai_provider import _coerce_job_requirements
    from app.schemas import ExtractedJobRequirements

    base = {"required_skills": [], "preferred_skills": [],
            "experience_requirements": [], "education_requirements": [],
            "location_requirements": [], "other_requirements": []}

    as_objects = {**base, "required_skills": [{"name": "Python",
                                              "importance": "REQUIRED"}]}
    assert ExtractedJobRequirements.model_validate(
        _coerce_job_requirements(as_objects)).required_skills == ["Python"]

    # Previously fatal, now recovered.
    as_strings = {**base, "experience_requirements": ["5+ years of ML"]}
    recovered = ExtractedJobRequirements.model_validate(
        _coerce_job_requirements(as_strings))
    assert [r.name for r in recovered.experience_requirements] == [
        "5+ years of ML"]


def test_provider_uses_no_seed_and_nonzero_temperature():
    """D2-A precondition: the extraction call is not seeded."""
    import inspect

    from app.ai.openai_provider import OpenAIProvider

    src = inspect.getsource(OpenAIProvider._json_completion)
    assert "temperature=0.1" in src
    assert "seed=" not in src, "extraction must not pass a seed"
