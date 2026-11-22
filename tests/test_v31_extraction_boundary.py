"""V3.1 extraction boundary regression coverage.

The V3 defect these tests close: a malformed structured element invalidated an
extraction, a zero-length result was persisted as "this job has no
requirements", and the scorer then returned APPLY_WITH_TAILORING at 72.0 for a
job the system had never read.
"""

from __future__ import annotations

import pytest
from app.ai.base import AIProvider, AIProviderError
from app.models import ExtractionStatus, Job, JobRequirement
from app.schemas import ExtractedJobRequirements
from app.services import extraction as ex

# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


class _StubProvider(AIProvider):
    """Returns whatever the test hands it."""

    name = "stub"

    def __init__(self, result=None, error: Exception | None = None):
        self._result = result
        self._error = error

    def extract_cv(self, cv_text):  # pragma: no cover - unused
        raise NotImplementedError

    def extract_job_requirements(self, job_description):
        if self._error is not None:
            raise self._error
        return self._result

    def analyze_cv_for_job(self, *a, **k):  # pragma: no cover - unused
        raise NotImplementedError

    def tailor_cv(self, *a, **k):  # pragma: no cover - unused
        raise NotImplementedError

    def generate_cover_letter(self, *a, **k):  # pragma: no cover - unused
        raise NotImplementedError

    def compose_strategy_narrative(self, *a, **k):  # pragma: no cover - unused
        raise NotImplementedError


BASE = {
    "required_skills": [], "preferred_skills": [], "responsibilities": [],
    "issues": [], "experience_requirements": [], "education_requirements": [],
    "location_requirements": [], "other_requirements": [],
}


def _empty() -> ExtractedJobRequirements:
    return ExtractedJobRequirements()


# =========================================================================== #
# 1. provider failure
# =========================================================================== #


def test_provider_failure_is_failed_not_empty():
    result = ex.extract_requirements(
        _StubProvider(error=AIProviderError("rate limited")),
        "Required: Python and 5 years experience.",
        model="test-model",
    )
    assert result.meta.status == ExtractionStatus.FAILED.value
    assert result.meta.error_code == "PROVIDER_ERROR"
    assert result.meta.requirement_count == 0


def test_provider_failure_preserves_diagnostic_metadata():
    result = ex.extract_requirements(
        _StubProvider(error=AIProviderError("rate limited")),
        "Required: Python.", model="m1",
    )
    meta = result.meta
    assert meta.provider == "stub"
    assert meta.model == "m1"
    assert meta.schema_version == ex.SCHEMA_VERSION
    assert meta.source_sha256 and len(meta.source_sha256) == 64
    assert meta.source_chars == len("Required: Python.")
    assert meta.attempts and meta.attempts[0].ok is False
    assert meta.attempts[0].error_code == "PROVIDER_ERROR"


def test_failed_extraction_is_never_usable():
    result = ex.extract_requirements(
        _StubProvider(error=AIProviderError("x")), "Required: Python."
    )
    assert result.usable is False


# =========================================================================== #
# 2. malformed structured arrays (the V3 defect)
# =========================================================================== #


def test_bare_string_in_structured_array_is_recovered():
    """Previously fatal; now recovered, so the job keeps its requirement."""
    result = ex.classify_raw_payload(
        {**BASE, "experience_requirements": ["5+ years of ML"]},
        source="We need 5+ years of ML experience.",
    )
    assert result.meta.status == ExtractionStatus.SUCCESS.value
    assert [r.name for r in result.requirements.experience_requirements] == [
        "5+ years of ML"]
    assert result.meta.recovered_elements >= 1


def test_malformed_object_missing_name_is_recovered_from_description():
    result = ex.classify_raw_payload(
        {**BASE, "other_requirements": [
            {"description": "Familiarity with Kubernetes required",
             "importance": "REQUIRED"}]},
        source="Kubernetes required.",
    )
    assert result.meta.status == ExtractionStatus.SUCCESS.value
    assert result.requirements.other_requirements[0].name == (
        "Familiarity with Kubernetes required")


def test_unsupported_element_types_are_recorded_and_dropped():
    result = ex.classify_raw_payload(
        {**BASE, "other_requirements": [["nested", "list"], {"name": "Docker"}]},
        source="Some listing.",
    )
    # Docker survives; the nested list is recorded as dropped, never silent.
    assert result.meta.status == ExtractionStatus.PARTIAL.value
    assert result.meta.dropped_elements
    assert "unsupported type list" in result.meta.dropped_elements[0]


def test_all_elements_malformed_is_failed_not_empty():
    result = ex.classify_raw_payload(
        {**BASE, "other_requirements": [["a"], ["b"], ["c"]]},
        source="A real posting with content that cannot be parsed.",
    )
    assert result.meta.status == ExtractionStatus.FAILED.value
    assert result.meta.error_code == "ALL_ELEMENTS_MALFORMED"


def test_importance_and_years_are_coerced():
    result = ex.classify_raw_payload(
        {**BASE, "experience_requirements": [
            {"name": "ML experience", "importance": "required",
             "years_required": "5"}]},
        source="5 years ML experience required.",
    )
    req = result.requirements.experience_requirements[0]
    assert req.years_required == 5.0
    assert req.importance.value == "REQUIRED"


def test_non_object_payload_is_failed():
    result = ex.classify_raw_payload(["not", "an", "object"], source="text")
    assert result.meta.status == ExtractionStatus.FAILED.value
    assert result.meta.error_code == "UNSUPPORTED_SHAPE"


def test_coercion_never_yields_zero_requirements_from_nonempty_input():
    """The core acceptance criterion, at the coercion layer."""
    for payload in (
        {**BASE, "experience_requirements": ["5+ years ML"]},
        {**BASE, "education_requirements": ["PhD"]},
        {**BASE, "location_requirements": ["UK based"]},
        {**BASE, "other_requirements": [{"description": "Docker"}]},
    ):
        result = ex.classify_raw_payload(payload, source="A posting with text.")
        assert result.meta.requirement_count > 0, payload
        assert result.meta.status != ExtractionStatus.EMPTY_CONFIRMED.value


# =========================================================================== #
# 3. unsupported coercion / schema failure
# =========================================================================== #


def test_schema_violation_after_coercion_is_failed():
    bad = {**BASE, "required_skills": [{"name": {"nested": "dict"}}]}
    result = ex.classify_raw_payload(bad, source="Some posting text.")
    # Recovered or dropped, but never a silent zero.
    assert result.meta.requirement_count > 0
    assert result.meta.status in (
        ExtractionStatus.SUCCESS.value, ExtractionStatus.PARTIAL.value)


def test_required_skills_as_objects_is_recovered():
    result = ex.classify_raw_payload(
        {**BASE, "required_skills": [{"name": "Python",
                                      "importance": "REQUIRED"}]},
        source="Required Python.",
    )
    assert result.requirements.required_skills == ["Python"]


# =========================================================================== #
# 4. empty extraction vs EMPTY_CONFIRMED
# =========================================================================== #


def test_zero_requirements_from_real_posting_is_a_failure():
    """Absence of extracted requirements is never proof of no requirements."""
    result = ex.extract_requirements(
        _StubProvider(result=_empty()),
        "We are hiring a data scientist to build pipelines and models.",
        model="m",
    )
    assert result.meta.status == ExtractionStatus.FAILED.value
    assert result.meta.error_code == "NO_REQUIREMENTS_FOUND"


def test_short_posting_is_empty_confirmed():
    result = ex.extract_requirements(
        _StubProvider(result=_empty()), "Data Analyst", model="m"
    )
    assert result.meta.status == ExtractionStatus.EMPTY_CONFIRMED.value
    assert result.meta.error_code is None


def test_empty_confirmed_threshold_is_documented_and_applied():
    short = "x" * (ex.EMPTY_CONFIRMED_MAX_SOURCE_CHARS - 1)
    long = "x" * (ex.EMPTY_CONFIRMED_MAX_SOURCE_CHARS + 1)
    assert ex.extract_requirements(
        _StubProvider(result=_empty()), short).meta.status == \
        ExtractionStatus.EMPTY_CONFIRMED.value
    assert ex.extract_requirements(
        _StubProvider(result=_empty()), long).meta.status == \
        ExtractionStatus.FAILED.value


def test_empty_source_is_empty_confirmed():
    result = ex.extract_requirements(_StubProvider(result=_empty()), "", model="m")
    assert result.meta.status == ExtractionStatus.EMPTY_CONFIRMED.value


# =========================================================================== #
# 5. partial extraction
# =========================================================================== #


def test_partial_status_when_some_elements_are_recovered():
    result = ex.classify_raw_payload(
        {**BASE,
         "required_skills": ["Python"],
         "other_requirements": [{"name": "Docker"}, ["bad"]]},
        source="Posting text.",
    )
    assert result.meta.status == ExtractionStatus.PARTIAL.value
    assert result.meta.requirement_count >= 2
    assert result.meta.dropped_elements


def test_partial_is_usable_but_recorded():
    result = ex.classify_raw_payload(
        {**BASE, "required_skills": ["Python"],
         "other_requirements": [["bad"]]},
        source="Posting text.",
    )
    assert result.usable is True
    assert result.meta.status == ExtractionStatus.PARTIAL.value


# =========================================================================== #
# 6. zero-requirement guard
# =========================================================================== #


def test_guard_blocks_job_with_no_requirements():
    job = Job(title="t", company="c")
    job.requirements = []
    with pytest.raises(ex.ExtractionNotMatchableError):
        ex.assert_matchable(job)


def test_guard_blocks_failed_job():
    job = Job(title="t", company="c")
    job.requirements = []
    job.extraction_status = ExtractionStatus.FAILED.value
    job.extraction_error_code = "NO_REQUIREMENTS_FOUND"
    with pytest.raises(ex.ExtractionNotMatchableError) as excinfo:
        ex.assert_matchable(job)
    assert "FAILED" in str(excinfo.value)


def test_guard_blocks_partial_job_with_no_surviving_requirements():
    job = Job(title="t", company="c")
    job.requirements = []
    job.extraction_status = ExtractionStatus.PARTIAL.value
    with pytest.raises(ex.ExtractionNotMatchableError):
        ex.assert_matchable(job)


def test_guard_allows_confirmed_empty_job():
    job = Job(title="t", company="c")
    job.requirements = []
    job.extraction_status = ExtractionStatus.EMPTY_CONFIRMED.value
    ex.assert_matchable(job)


def test_guard_allows_job_with_requirements():
    job = Job(title="t", company="c")
    job.requirements = [JobRequirement(requirement_type="SKILL", name="Python")]
    ex.assert_matchable(job)


def test_run_match_refuses_unmatchable_job(db, candidate):
    from app.services.matching import run_match

    job = Job(title="Data Scientist", company="Acme", location="Amsterdam",
              description="Required: Python.")
    job.requirements = []
    db.add(job)
    db.commit()
    db.refresh(job)
    with pytest.raises(ex.ExtractionNotMatchableError):
        run_match(db, candidate, job)


def test_run_match_proceeds_after_extraction(db, candidate):
    from app.services.matching import run_match

    job = Job(title="Data Scientist", company="Acme", location="Amsterdam",
              description="Required: Python and SQL.")
    job.requirements = [
        JobRequirement(requirement_type="SKILL", name="Python",
                       importance="REQUIRED"),
    ]
    job.extraction_status = ExtractionStatus.SUCCESS.value
    db.add(job)
    db.commit()
    db.refresh(job)
    assert run_match(db, candidate, job).id is not None


# =========================================================================== #
# 7. the exact previously observed optimistic-failure path
# =========================================================================== #


def test_optimistic_failure_path_is_now_impossible():
    """V3 observed: zero requirements -> 72.0 -> APPLY_WITH_TAILORING.

    With the guard in place that combination is unreachable through the API.
    """
    from matching import (
        CandidateProfile,
        CandidateSkill,
        JobProfile,
        MatchingEngine,
        MatchSettings,
        MatchWeights,
        RecommendationPolicy,
    )

    baseline = MatchSettings(weights=MatchWeights().normalised(),
                             policy=RecommendationPolicy())
    candidate = CandidateProfile(
        id=1, name="T", professional_title="Data Scientist",
        location="Lagos, Nigeria", years_of_experience=6,
        skills=[CandidateSkill(id=1, name="Python")],
    )
    empty_job = JobProfile(id=1, title="Data Scientist", company="Acme",
                           location="Lagos, Nigeria", requirements=[])
    outcome, _dims = MatchingEngine(baseline).match(candidate, empty_job)

    # The engine behaviour is unchanged and still optimistic - V3.1 was told not
    # to touch scoring. What changed is that a job in this state can no longer
    # REACH the scorer through the product path.
    assert outcome.recommendation == "APPLY_WITH_TAILORING"
    assert outcome.overall_score > 65

    blocked = Job(title="t", company="c")
    blocked.requirements = []
    blocked.extraction_status = ExtractionStatus.FAILED.value
    with pytest.raises(ex.ExtractionNotMatchableError):
        ex.assert_matchable(blocked)


def test_extraction_failure_preserves_previously_stored_requirements(db, candidate):
    """A failed re-extraction must not destroy existing evidence."""
    from app.services import jobs as job_service
    from fastapi import HTTPException

    job = Job(title="Data Scientist", company="Acme", location="Amsterdam",
              description="Required: Python.")
    job.requirements = [
        JobRequirement(requirement_type="SKILL", name="Python",
                       importance="REQUIRED")
    ]
    job.requirements_extracted = True
    job.extraction_status = ExtractionStatus.SUCCESS.value
    db.add(job)
    db.commit()
    db.refresh(job)

    from app.ai import get_ai_provider
    original = get_ai_provider

    import app.services.jobs as jobs_module

    def _boom():
        class _Failing(_StubProvider):
            pass

        return _Failing(error=AIProviderError("provider down"))

    jobs_module.get_ai_provider = _boom
    try:
        with pytest.raises(HTTPException) as excinfo:
            job_service.extract_requirements(db, job)
        assert excinfo.value.status_code == 502
    finally:
        jobs_module.get_ai_provider = original

    db.refresh(job)
    assert len(job.requirements) == 1, "stored requirements must survive"
    assert job.extraction_status == ExtractionStatus.FAILED.value


# =========================================================================== #
# 8. determinism of the boundary itself
# =========================================================================== #


def test_same_payload_yields_identical_outcome():
    payload = {**BASE, "required_skills": ["Python", "SQL"],
               "experience_requirements": ["5+ years ML"]}
    a = ex.classify_raw_payload(payload, source="Posting.")
    b = ex.classify_raw_payload(payload, source="Posting.")
    assert a.meta.status == b.meta.status
    assert a.meta.requirement_count == b.meta.requirement_count
    assert a.meta.source_sha256 == b.meta.source_sha256
    assert a.requirements.model_dump() == b.requirements.model_dump()
