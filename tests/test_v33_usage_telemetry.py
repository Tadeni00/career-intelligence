"""Telemetry tests for the V3.3 measurement revision.

`_json_completion` previously discarded `response.usage`, so no per-call token
telemetry existed for any V3.3 run. These tests pin the instrumented contract:

  1. usage present  -> input/output/total tokens captured
  2. usage absent   -> extraction still succeeds, telemetry marked unavailable
                       (never fabricated zeros)
  3. extraction content is identical whether or not usage is present
  4. retry attempts are aggregated, and a failed call still exposes telemetry

No network calls: the provider's client is stubbed. The extraction contract
under test remains `ExtractedJobRequirements@2`; nothing here changes prompt,
schema, canonicalization or matching.
"""

from __future__ import annotations

import json

import pytest
from app.ai.openai_provider import OpenAIProvider, finalize_usage
from app.core.config import get_settings
from app.schemas import ExtractedJobRequirements


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeUsage:
    def __init__(self, prompt: int | None, completion: int | None,
                 total: int | None) -> None:
        self.prompt_tokens = prompt
        self.completion_tokens = completion
        self.total_tokens = total
        self.prompt_tokens_details = None
        self.completion_tokens_details = None


class _FakeCompletion:
    def __init__(self, content: str, usage: object | None) -> None:
        self.choices = [_FakeChoice(content)]
        # The real SDK always exposes `.usage`; it may be None. Absence is
        # modelled by the attribute being None, not by removing it.
        self.usage = usage


class _FakeCompletions:
    def __init__(self) -> None:
        self.payload: dict = {}
        self.usage: object | None = _FakeUsage(4276, 280, 4556)
        self.payloads: list[str] = []

    def create(self, **kwargs):
        self.payloads.append(json.dumps(self.payload))
        return _FakeCompletion(json.dumps(self.payload), self.usage)


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


REQUIREMENTS_PAYLOAD = {
    "required_skills": ["Python"],
    "preferred_skills": ["SQL"],
    "experience_requirements": ["5+ years in machine learning"],
    "education_requirements": ["MSc in Computer Science"],
    "location_requirements": [],
    "other_requirements": [],
}


def test_usage_is_captured_when_present():
    """Test 1 -- a response carrying usage produces real token telemetry."""
    provider = _provider()
    provider.client.chat.completions.payload = REQUIREMENTS_PAYLOAD

    provider.extract_job_requirements("Some job posting")

    usage = provider.last_usage
    assert usage is not None
    assert usage["available"] is True
    assert usage["input_tokens"] == 4276
    assert usage["output_tokens"] == 280
    assert usage["total_tokens"] == 4556
    assert usage["provider"] == provider.name
    assert usage["model"] == provider.model
    assert usage["timestamp"]
    assert usage["attempts"] == 1


def test_missing_usage_is_tolerated_and_not_fabricated():
    """Test 2 -- absent usage still extracts, and absence is recorded as None."""
    provider = _provider()
    provider.client.chat.completions.payload = REQUIREMENTS_PAYLOAD
    provider.client.chat.completions.usage = None

    result = provider.extract_job_requirements("Some job posting")

    assert isinstance(result, ExtractedJobRequirements)
    assert result.required_skills == ["Python"]
    assert len(result.experience_requirements) == 1
    usage = provider.last_usage
    assert usage["available"] is False
    # None, not 0 -- a real zero would be indistinguishable from unmeasured.
    assert usage["input_tokens"] is None
    assert usage["output_tokens"] is None
    assert usage["total_tokens"] is None


def test_extraction_content_is_identical_with_and_without_usage():
    """Test 3 -- telemetry is metadata only; the extraction cannot move."""
    with_usage = _provider()
    with_usage.client.chat.completions.payload = REQUIREMENTS_PAYLOAD
    with_usage.client.chat.completions.usage = _FakeUsage(4276, 280, 4556)

    without_usage = _provider()
    without_usage.client.chat.completions.payload = REQUIREMENTS_PAYLOAD
    without_usage.client.chat.completions.usage = None

    a = with_usage.extract_job_requirements("Some job posting")
    b = without_usage.extract_job_requirements("Some job posting")

    assert a.model_dump() == b.model_dump()
    assert with_usage.last_usage["available"] is True
    assert without_usage.last_usage["available"] is False


def test_usage_detail_fields_are_preserved_when_provider_offers_them():
    """Provider-specific detail is preserved but never required."""
    provider = _provider()
    usage = _FakeUsage(100, 20, 120)
    usage.prompt_tokens_details = type("D", (), {"model_dump": lambda self: {"cached": 5}})()
    provider.client.chat.completions.payload = REQUIREMENTS_PAYLOAD
    provider.client.chat.completions.usage = usage

    provider.extract_job_requirements("Some job posting")

    assert provider.last_usage["extra"] == [
        {"prompt_tokens_details": {"cached": 5}}]
    assert provider.last_usage["total_tokens"] == 120


def test_retry_attempts_are_aggregated():
    """Each attempt that reported usage contributes to the total."""
    provider = _provider()
    settings_holder = finalize_usage
    records = [
        {"attempt": 1, "available": True, "input_tokens": 10,
         "output_tokens": 1, "total_tokens": 11, "extra": None},
        {"attempt": 2, "available": True, "input_tokens": 10,
         "output_tokens": 2, "total_tokens": 12, "extra": None},
    ]
    folded = settings_holder(provider, records)
    assert folded["attempts"] == 2
    assert folded["input_tokens"] == 20
    assert folded["output_tokens"] == 3
    assert folded["total_tokens"] == 23


def test_partial_usage_fields_are_not_treated_as_zero():
    """A field the provider omits stays None even when siblings are present."""
    provider = _provider()
    usage = _FakeUsage(500, None, None)
    provider.client.chat.completions.payload = REQUIREMENTS_PAYLOAD
    provider.client.chat.completions.usage = usage

    provider.extract_job_requirements("Some job posting")

    assert provider.last_usage["input_tokens"] == 500
    assert provider.last_usage["output_tokens"] is None
    assert provider.last_usage["total_tokens"] is None


def test_usage_snapshot_never_raises_on_a_provider_without_telemetry():
    """A provider exposing no `last_usage` still yields an honest record."""
    provider = _provider()
    provider.client.chat.completions.payload = REQUIREMENTS_PAYLOAD
    del provider.last_usage

    assert getattr(provider, "last_usage", None) is None
    assert provider.extract_job_requirements("Some job posting") is not None


@pytest.mark.parametrize("payload", [REQUIREMENTS_PAYLOAD])
def test_temperature_and_schema_contract_untouched(payload):
    """The instrumented call must still send the frozen request shape."""
    provider = _provider()
    provider.client.chat.completions.payload = payload
    seen: dict = {}

    original = provider.client.chat.completions.create

    def spy(**kwargs):
        seen.update(kwargs)
        return original(**kwargs)

    provider.client.chat.completions.create = spy
    provider.extract_job_requirements("Some job posting")

    assert seen["temperature"] == 0.1
    assert seen["response_format"] == {"type": "json_object"}
    assert seen["model"] == provider.model
    assert "seed" not in seen
