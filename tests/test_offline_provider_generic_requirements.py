"""Regression tests for generic job requirements in the offline provider.

The defect: ``OfflineProvider.extract_job_requirements`` classified generic
job-description sentences as required or preferred and appended them to the
local lists ``other_required`` / ``other_preferred``, but the return path never
assigned those lists onto ``ExtractedJobRequirements``. Every catch-all
requirement was therefore discarded, and ``other_requirements`` only ever
received the eligibility branch.

The fix writes both lists back onto the result, preserving the importance the
parser assigned, and de-duplicates on the normalised requirement name.

These tests drive the provider's public extraction method and the service-level
``extract_requirements`` path. No network, no database, no AI provider
configuration.
"""

from __future__ import annotations

from app.ai.offline_provider import OfflineProvider
from app.models import Importance
from app.schemas import ExtractedJobRequirements
from app.services.extraction import extract_requirements

REPRESENTATIVE_JD = """\
Data Scientist at Example Analytics.

Required: Python, SQL, and 5+ years of experience building models.
Required: Demonstrable ownership of at least one production data pipeline.
Required: Bachelor's degree in a related field is required.
Preferred: Familiarity with dbt and Snowflake is a plus.
Preferred: Experience with Kubernetes is nice to have.
Applicants must have the right to work in the UK.
We offer a competitive salary and free lunch every Friday.
"""


def _other(result: ExtractedJobRequirements) -> list[tuple[str, str]]:
    return [(r.importance.value, r.name) for r in result.other_requirements]


def test_generic_required_requirement_survives_extraction() -> None:
    result = OfflineProvider().extract_job_requirements(REPRESENTATIVE_JD)
    required = [n for i, n in _other(result) if i == "REQUIRED"]
    assert any("production data pipeline" in n for n in required), required


def test_generic_preferred_requirement_survives_extraction() -> None:
    result = OfflineProvider().extract_job_requirements(REPRESENTATIVE_JD)
    preferred = [n for i, n in _other(result) if i == "PREFERRED"]
    assert any("dbt" in n for n in preferred), preferred


def test_name_description_and_importance_are_preserved() -> None:
    result = OfflineProvider().extract_job_requirements(REPRESENTATIVE_JD)
    item = next(r for r in result.other_requirements if "dbt" in r.name)

    assert item.importance is Importance.PREFERRED
    assert isinstance(item.name, str) and item.name
    assert isinstance(item.description, str) and item.description
    # name is the truncated sentence, description the full one
    assert item.description.startswith(item.name[:40])
    assert item.years_required is None


def test_technical_classification_is_unchanged() -> None:
    """Skills, education and experience paths must be unaffected."""
    result = OfflineProvider().extract_job_requirements(REPRESENTATIVE_JD)
    assert result.required_skills == ["Python", "SQL"]
    assert "Kubernetes" in result.preferred_skills
    assert len(result.education_requirements) == 1
    assert "Bachelor" in result.education_requirements[0].name


def test_eligibility_requirement_still_classified_as_other() -> None:
    """The eligibility branch keeps working and keeps its own importance."""
    result = OfflineProvider().extract_job_requirements(REPRESENTATIVE_JD)
    names = [n for _, n in _other(result)]
    assert any("right to work" in n for n in names), names


def test_eligibility_is_not_duplicated_by_the_write_back() -> None:
    """Eligibility sentences take the earlier branch, so they must appear once."""
    result = OfflineProvider().extract_job_requirements(REPRESENTATIVE_JD)
    right_to_work = [n for _, n in _other(result) if "right to work" in n]
    assert len(right_to_work) == 1, right_to_work


def test_repeated_sentence_yields_one_requirement() -> None:
    """A requirement stated twice must not become two rows."""
    jd = (
        "Required: Demonstrable ownership of a production data pipeline.\n"
        "Required: Demonstrable ownership of a production data pipeline.\n"
    )
    result = OfflineProvider().extract_job_requirements(jd)
    pipeline = [n for _, n in _other(result) if "production data pipeline" in n]
    assert len(pipeline) == 1, pipeline


def test_ambiguous_sentence_is_not_promoted() -> None:
    """Text with no required/preferred marker must not become a requirement."""
    jd = (
        "We offer a competitive salary and free lunch every Friday.\n"
        "The office is a short walk from the station.\n"
    )
    result = OfflineProvider().extract_job_requirements(jd)
    assert result.other_requirements == [], [r.name for r in result.other_requirements]


def test_service_path_returns_them_in_the_analysis() -> None:
    """The service-level extraction path must also carry them."""
    outcome = extract_requirements(
        OfflineProvider(), REPRESENTATIVE_JD, model="offline"
    )
    names = [r.name for r in outcome.requirements.other_requirements]
    assert any("production data pipeline" in n for n in names), names
    assert any("dbt" in n for n in names), names
    # The requirement count includes generic requirements (Task 10) plus the
    # years requirement now correctly extracted from the mixed sentence (Task 12).
    assert outcome.meta.requirement_count == 8, outcome.meta.requirement_count


def test_analysis_of_a_job_is_unaffected_by_generic_requirements() -> None:
    """`analyze_cv_for_job` keys off required/preferred skills only."""
    from app.schemas import ProfileSummary

    profile = ProfileSummary(
        id=1, name="T", professional_title="Data Scientist",
        skills=[{"id": 1, "name": "Python"}, {"id": 2, "name": "SQL"}],
    )
    analysis = OfflineProvider().analyze_cv_for_job(
        profile, REPRESENTATIVE_JD, "Data Scientist", "Example Analytics"
    )
    assert "Python" in analysis.relevant_skills
    # dbt/Snowflake are not on the profile, so they must not become candidate skills.
    assert "dbt" not in analysis.relevant_skills
