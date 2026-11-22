"""Regression tests for the offline provider's work-authorization extraction defect.

The defect was an ``AttributeError`` raised by
``OfflineProvider.extract_job_requirements`` whenever a job description mentioned
work authorization, visa sponsorship, citizenship, residency or security
clearance::

    AttributeError: 'ExtractedJobRequirements' object has no attribute
    'other_required'. Did you mean: 'other_requirements'?

The branch appended to ``result.other_required``, which is not a field of
``ExtractedJobRequirements``. Because the branch runs mid-loop, the exception
escaped ``extract_job_requirements`` and, through ``analyze_cv_for_job``, every
generation endpoint that analyses a job description -- tailored CV generation
and cover-letter generation both returned HTTP 500.

The fix appends to the schema's real field, ``other_requirements``, which is
what ``app/services/jobs.py`` consumes when persisting requirements with
``requirement_type="OTHER"``.

These tests are pure and deterministic: no network, no database, no AI provider
configuration. Document validation is a separate concern -- nothing here asserts
that a generated document is ``VALID``.
"""

from __future__ import annotations

import pytest
from app.ai.offline_provider import OfflineProvider
from app.schemas import Importance

# --------------------------------------------------------------- fixtures

VISA_SPONSORSHIP = """\
Senior Data Scientist at Example Analytics.

We are looking for a data scientist to join our risk team.

Required: Python, SQL, and 5+ years of experience in production machine learning.

You must have the right to work in the UK. We cannot sponsor a visa for this role.
"""

WORK_AUTHORIZATION = """\
Machine Learning Engineer.

Required: Python, PyTorch, and 3+ years of experience shipping models.

Applicants must have existing work authorization in the United States.
"""

CITIZENSHIP = """\
Data Analyst.

Required: SQL, Excel, and 2+ years of experience in analytics.

Only US citizens may be considered for this position.
"""

RESIDENCY = """\
Research Scientist.

Required: R, and 4+ years of experience in quantitative research.

This role is open to residents of the Netherlands only.
"""

SECURITY_CLEARANCE = """\
Data Platform Engineer.

Required: Kubernetes, Terraform, and 5+ years of experience in platform engineering.

An active security clearance is required for this position.
"""

ORDINARY_DESCRIPTION = """\
Senior Data Scientist at Example Analytics.

Required: Python, SQL, and 5+ years of experience in production machine learning.
You will build and evaluate statistical models and data pipelines.
Bachelor's degree in a related field is required.
"""


@pytest.fixture
def provider() -> OfflineProvider:
    return OfflineProvider()


def _requirement_texts(result) -> list[str]:
    return [r.name.lower() for r in result.other_requirements]


# --------------------------------------------------------------- the defect


@pytest.mark.parametrize(
    ("label", "description"),
    [
        ("visa sponsorship", VISA_SPONSORSHIP),
        ("work authorization", WORK_AUTHORIZATION),
        ("citizenship", CITIZENSHIP),
        ("residency", RESIDENCY),
        ("security clearance", SECURITY_CLEARANCE),
    ],
)
def test_eligibility_description_does_not_raise(
    provider: OfflineProvider, label: str, description: str
) -> None:
    """The defect: any of these markers raised AttributeError mid-loop."""
    try:
        result = provider.extract_job_requirements(description)
    except AttributeError as exc:  # pragma: no cover - the regression itself
        pytest.fail(f"{label}: extract_job_requirements raised {exc!r}")
    assert isinstance(result.other_requirements, list)


def test_schema_has_no_other_required_attribute() -> None:
    """Guard the root cause: the name the code used is not on the schema."""
    from app.schemas import ExtractedJobRequirements

    assert not hasattr(ExtractedJobRequirements(), "other_required")
    assert "other_requirements" in ExtractedJobRequirements.model_fields


# ------------------------------------------------- information is retained


def test_visa_sentence_is_retained_in_other_requirements(
    provider: OfflineProvider,
) -> None:
    result = provider.extract_job_requirements(VISA_SPONSORSHIP)
    assert result.other_requirements, "the visa sentence must not be dropped"
    texts = _requirement_texts(result)
    assert any("sponsor a visa" in t for t in texts), texts
    assert any("right to work" in t for t in texts), texts


def test_work_authorization_sentence_is_retained(provider: OfflineProvider) -> None:
    result = provider.extract_job_requirements(WORK_AUTHORIZATION)
    texts = _requirement_texts(result)
    assert any("work authorization" in t for t in texts), texts


def test_citizenship_sentence_is_retained(provider: OfflineProvider) -> None:
    result = provider.extract_job_requirements(CITIZENSHIP)
    texts = _requirement_texts(result)
    assert any("us citizens" in t for t in texts), texts


def test_residency_sentence_is_retained(provider: OfflineProvider) -> None:
    result = provider.extract_job_requirements(RESIDENCY)
    texts = _requirement_texts(result)
    assert any("residents" in t for t in texts), texts


def test_security_clearance_sentence_is_retained(provider: OfflineProvider) -> None:
    result = provider.extract_job_requirements(SECURITY_CLEARANCE)
    texts = _requirement_texts(result)
    assert any("security clearance" in t for t in texts), texts


def test_eligibility_requirement_carries_importance_and_description(
    provider: OfflineProvider,
) -> None:
    """Items must satisfy the ExtractedRequirement contract jobs.py persists."""
    result = provider.extract_job_requirements(SECURITY_CLEARANCE)
    item = result.other_requirements[0]
    assert isinstance(item.name, str) and item.name
    assert isinstance(item.description, str) and item.description
    assert item.importance in tuple(Importance)
    assert item.importance in (Importance.REQUIRED, Importance.PREFERRED)


def test_eligibility_is_a_requirement_not_an_issue(provider: OfflineProvider) -> None:
    """Stated eligibility is an established requirement, not missing information.

    The distinction matters: `issues` records what the description did not say,
    while `other_requirements` records what it did say and must be enforced.
    """
    result = provider.extract_job_requirements(CITIZENSHIP)
    joined = " ".join(result.issues).lower()
    assert "citizen" not in joined, joined
    assert result.other_requirements


# ------------------------------------------- unaffected behaviour preserved


def test_ordinary_description_has_no_eligibility_requirements(
    provider: OfflineProvider,
) -> None:
    result = provider.extract_job_requirements(ORDINARY_DESCRIPTION)
    assert result.other_requirements == []


def test_ordinary_description_still_extracts_normally(
    provider: OfflineProvider,
) -> None:
    """The unrelated branches must be unaffected by the fix."""
    result = provider.extract_job_requirements(ORDINARY_DESCRIPTION)
    skills = [s.lower() for s in result.required_skills]
    assert "python" in skills, skills
    assert "sql" in skills, skills
    assert result.education_requirements
    assert result.other_requirements == []


def test_deterministic_across_repeated_calls(provider: OfflineProvider) -> None:
    first = provider.extract_job_requirements(VISA_SPONSORSHIP)
    second = provider.extract_job_requirements(VISA_SPONSORSHIP)
    assert [r.name for r in first.other_requirements] == [
        r.name for r in second.other_requirements
    ]


def test_analyze_cv_for_job_survives_eligibility_description() -> None:
    """analyze_cv_for_job is the caller that turned the defect into HTTP 500."""
    from app.schemas import ProfileSummary

    profile = ProfileSummary(
        id=1,
        name="Test Candidate",
        professional_title="Data Scientist",
        skills=[
            {"id": 1, "name": "Python"},
            {"id": 2, "name": "SQL"},
        ],
    )
    result = OfflineProvider().analyze_cv_for_job(
        profile=profile,
        job_description=VISA_SPONSORSHIP,
        job_title="Senior Data Scientist",
        company="Example Analytics",
    )
    assert result is not None
