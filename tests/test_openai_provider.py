"""Regression tests for the OpenAIProvider production-path defect repair.

These reproduce the exact malformed response shapes observed from the live
endpoint during real-world validation, and confirm well-formed responses still
work. The offline-provider tests are untouched and still run separately.

The defect (Critical, E8 workflow defect) was:
  extract_cv                 -> experience[].responsibilities returned null/str,
                                'title' emitted as 'job_title', skills[] as strings
  extract_job_requirements   -> required_skills[] returned objects instead of strings
  generate_cover_letter      -> model letterhead/preamble leaked above the greeting

No network calls: the provider's client is stubbed.
"""

from __future__ import annotations

import json

import pytest
from app.ai.openai_provider import (
    OpenAIProvider,
    _coerce_extracted_cv,
    _coerce_job_requirements,
    _strip_letter_preamble,
)
from app.core.config import get_settings
from app.schemas import ExtractedCV, ExtractedJobRequirements, ProfileSummary

# --------------------------------------------------------------- fixtures


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeCompletion:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    """Stands in for client.chat.completions."""

    def __init__(self) -> None:
        self.payload: dict = {}
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if "response_format" in kwargs:
            return _FakeCompletion(json.dumps(self.payload))
        return _FakeCompletion(self.payload)


class _FakeClient:
    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions()})()


def _provider() -> OpenAIProvider:
    settings = get_settings().model_copy(
        update={"ai_api_key": "test-key", "ai_base_url": "https://example.invalid/v1"}
    )
    provider = OpenAIProvider(settings)
    provider.client = _FakeClient()
    return provider


def _stub(provider: OpenAIProvider, payload: dict | str) -> None:
    provider.client.chat.completions.payload = payload


@pytest.fixture
def profile() -> ProfileSummary:
    return ProfileSummary(
        id=1,
        name="Jane Doe",
        professional_title="Data Scientist",
        location="Amsterdam",
        years_of_experience=6,
        skills=[{"id": 1, "name": "Python"}, {"id": 2, "name": "SQL"}],
        experience=[
            {
                "id": 1,
                "company": "Acme",
                "title": "Data Scientist",
                "start_date": "2021",
                "end_date": None,
                "description": "Built fraud detection models.",
                "is_current": True,
            }
        ],
        education=[
            {"id": 1, "institution": "Uni", "degree": "MSc", "field": "Data Science"}
        ],
    )


# --------------------------------------------- observed-shape regressions


def test_extract_job_requirements_accepts_object_shaped_skills():
    """Observed: required_skills[0] was {'name': 'Python', ...} not a string."""
    payload = {
        "required_skills": [
            {"name": "Python", "description": "", "importance": "REQUIRED", "years_required": None},
            {"name": "SQL", "description": "", "importance": "REQUIRED", "years_required": None},
        ],
        "preferred_skills": [{"name": "Kubernetes", "description": "", "importance": "PREFERRED"}],
        "experience_requirements": [
            {
                "name": "5+ years experience",
                "description": "You must have 5+ years experience.",
                "importance": "REQUIRED",
                "years_required": 5,
            }
        ],
        "education_requirements": [],
        "location_requirements": [],
        "other_requirements": [],
        "responsibilities": ["Build models"],
        "issues": [],
    }
    provider = _provider()
    _stub(provider, payload)

    result = provider.extract_job_requirements("Required: Python, SQL. 5+ years experience.")

    assert isinstance(result, ExtractedJobRequirements)
    assert result.required_skills == ["Python", "SQL"]
    assert result.preferred_skills == ["Kubernetes"]
    assert result.experience_requirements[0].years_required == 5


def test_extract_job_requirements_still_accepts_well_formed_strings():
    """Regression guard: valid string lists must not be altered."""
    payload = {
        "required_skills": ["Python", "SQL"],
        "preferred_skills": ["Kubernetes"],
        "experience_requirements": [
            {
                "name": "5+ years",
                "description": "5+ years",
                "importance": "REQUIRED",
                "years_required": 5,
            }
        ],
        "education_requirements": [],
        "location_requirements": [],
        "other_requirements": [],
        "responsibilities": ["Build models"],
        "issues": [],
    }
    provider = _provider()
    _stub(provider, payload)

    result = provider.extract_job_requirements("Required: Python, SQL.")
    assert result.required_skills == ["Python", "SQL"]
    assert result.preferred_skills == ["Kubernetes"]


def test_extract_cv_accepts_null_and_scalar_list_fields():
    """Observed: experience[0].responsibilities and .achievements were null."""
    payload = {
        "name": "Jane Doe",
        "professional_title": "Data Scientist",
        "email": None,
        "phone": None,
        "location": "Amsterdam",
        "summary": "ML engineer.",
        "experience": [
            {
                "company": "Acme",
                "job_title": "Data Scientist",
                "start_date": "2021",
                "end_date": None,
                "description": "Built fraud models.",
                "responsibilities": None,
                "achievements": None,
                "is_current": True,
            }
        ],
        "education": [
            {
                "institution": "Uni",
                "degree": "MSc",
                "field": "Data Science",
                "start_date": None,
                "end_date": "2019",
                "description": None,
            }
        ],
        "projects": [],
        "skills": [{"name": "Python", "category": "Programming"}],
        "certifications": [],
        "other": [],
        "issues": [],
    }
    provider = _provider()
    _stub(provider, payload)

    result = provider.extract_cv("Jane Doe\nData Scientist\nAmsterdam")

    assert isinstance(result, ExtractedCV)
    assert result.experience[0].title == "Data Scientist"  # mapped from job_title
    assert result.experience[0].responsibilities == []
    assert result.experience[0].achievements == []
    assert result.experience[0].company == "Acme"


def test_extract_cv_accepts_delimited_string_for_list_field():
    """A model may return one string where a list is required."""
    payload = {
        "name": "Jane Doe",
        "experience": [
            {
                "company": "Acme",
                "title": "Data Scientist",
                "start_date": "2021",
                "end_date": None,
                "description": None,
                "responsibilities": "Built fraud models. Ran model evaluation.",
                "achievements": "Cut manual review by 30%",
                "is_current": True,
            }
        ],
        "education": [],
        "projects": [],
        "skills": [],
        "certifications": [],
        "other": [],
        "issues": [],
    }
    provider = _provider()
    _stub(provider, payload)

    result = provider.extract_cv("Jane Doe")
    assert result.experience[0].responsibilities == [
        "Built fraud models.",
        "Ran model evaluation.",
    ]
    assert result.experience[0].achievements == ["Cut manual review by 30%"]


def test_extract_cv_still_accepts_well_formed_response():
    provider = _provider()
    _stub(
        provider,
        {
            "name": "Jane Doe",
            "professional_title": "Data Scientist",
            "email": "jane@example.com",
            "phone": None,
            "location": "Amsterdam",
            "summary": "ML engineer.",
            "experience": [
                {
                    "company": "Acme",
                    "title": "Data Scientist",
                    "start_date": "2021",
                    "end_date": None,
                    "description": "Built fraud models.",
                    "responsibilities": ["Built fraud models"],
                    "achievements": [],
                    "is_current": True,
                }
            ],
            "education": [],
            "projects": [],
            "skills": [{"name": "Python", "category": None}],
            "certifications": [],
            "other": [],
            "issues": [],
        },
    )

    result = provider.extract_cv("Jane Doe")
    assert result.experience[0].title == "Data Scientist"
    assert result.experience[0].responsibilities == ["Built fraud models"]
    assert result.skills[0].name == "Python"


def test_coercion_rejects_unexpected_shape_rather_than_dropping_it():
    """Narrow adapters must not silently swallow genuinely wrong data."""
    with pytest.raises(TypeError):
        _as_str_rejects()


def _as_str_rejects() -> None:
    from app.ai.openai_provider import _as_str_list

    _as_str_list(12345, "responsibilities")


def test_coercion_preserves_dict_content_as_label():
    """Structured content must not be discarded - its label is kept."""
    out = _coerce_job_requirements({"required_skills": [{"name": "Python"}]})
    assert out["required_skills"] == ["Python"]


def test_coercion_leaves_requirement_objects_untouched():
    """Structured objects are not reshaped into strings.

    V3.3 note: the object is no longer byte-identical to the input. The
    V3.1/V3.3 contract deliberately enriches it with the two new fields and
    normalises years to float, but the substance - name, description and
    importance - must survive unchanged, and the element must stay a dict.
    """
    payload = {
        "experience_requirements": [
            {"name": "x", "description": "d", "importance": "REQUIRED", "years_required": 3}
        ]
    }
    out = _coerce_job_requirements(payload)
    element = out["experience_requirements"][0]
    assert isinstance(element, dict), "structured elements must stay objects"
    assert element["name"] == "x"
    assert element["description"] == "d"
    assert element["importance"] == "REQUIRED"
    assert element["years_required"] == 3.0
    # V3.3 evidence fields are present and default to None.
    assert element["source_text"] is None
    assert element["category"] is None


def test_coerce_extracted_cv_leaves_non_dict_experience_alone():
    out = _coerce_extracted_cv({"experience": ["not-a-dict"]})
    assert out["experience"] == ["not-a-dict"]


# --------------------------------------------- cover-letter boundary


def test_strip_letter_preamble_removes_observed_letterhead():
    """Observed: model emitted contact block + [Date] above the greeting."""
    text = (
        "Jane Doe  \n"
        "Amsterdam, Netherlands  \n"
        "jane.doe@email.com  \n"
        "+31612345678  \n"
        "\n"
        "[Date]\n"
        "\n"
        "Hiring Team  \n"
        "Acme  \n"
        "\n"
        "Dear Hiring Team,\n\n"
        "I am writing to apply for the role.\n\n"
        "Kind regards,\nJane Doe"
    )
    out = _strip_letter_preamble(text, "Jane Doe", "Acme")
    assert out.startswith("Dear Hiring Team,")
    assert "jane.doe@email.com" not in out
    assert "[Date]" not in out
    assert "Amsterdam, Netherlands" not in out.split("Dear")[0]
    assert out.endswith("Jane Doe")


def test_strip_letter_preamble_keeps_letter_that_starts_at_greeting():
    text = "Dear Hiring Team,\n\nI am applying.\n\nKind regards,\nJane Doe"
    assert _strip_letter_preamble(text, "Jane Doe", "Acme") == text


def test_strip_letter_preamble_does_not_cut_real_prose():
    """Prose above a greeting must be preserved, not truncated."""
    text = (
        "I read your posting with great interest.\n\n"
        "Dear Hiring Team,\n\n"
        "I am applying.\n"
    )
    out = _strip_letter_preamble(text, "Jane Doe", "Acme")
    assert "I read your posting" in out


def test_generate_cover_letter_strips_preamble_end_to_end(profile):
    letter = (
        "Jane Doe\njane@example.com\n\n[Date]\n\n"
        "Dear Hiring Team,\n\n"
        "I am writing to apply for the Data Scientist role at Acme.\n\n"
        "Kind regards,\nJane Doe"
    )
    provider = _provider()
    _stub(provider, letter)

    out = provider.generate_cover_letter(profile, "Python and SQL needed.", "Data Scientist", "Acme")

    assert out.startswith("Dear Hiring Team,")
    assert "[Date]" not in out
