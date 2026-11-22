"""Regression tests for years-of-experience short-circuit in job requirement extraction.

The defect: ``OfflineProvider.extract_job_requirements`` processed sentences
sequentially with early ``continue`` statements. When the skills branch matched
(first in the chain), it appended the found skills and immediately continued to
the next sentence, so a years-of-experience requirement in the *same* sentence
was never reached. The same pattern affected years→education, education→location,
etc., but the confirmed user-facing failure was skills silently swallowing years.

The fix removes the ``continue`` after the skills branch so that all independent
requirement categories are checked for every sentence. The other branches retain
their existing control flow.

These tests drive the provider's public extraction method. No network, no
database, no AI provider configuration.
"""

from __future__ import annotations

from app.ai.offline_provider import OfflineProvider
from app.models import Importance
from app.schemas import ExtractedJobRequirements


MIXED_SENTENCE = "Required: Python, SQL, and 5+ years of experience building models."
SKILLS_ONLY = "Required: Python, SQL, and Kubernetes."
YEARS_ONLY = "Required: 5+ years of experience in manufacturing."
PREFERRED_YEARS = "Preferred: 3+ years with PyTorch and TensorFlow."
MULTI_CATEGORY = "Required: Python, SQL, 5+ years, and a Bachelor degree."
HTML_MIXED = "<p>Required: Python, 5+ years experience.</p>"
TWO_SENTENCES = "Required: Python, SQL. Required: 5+ years experience."


def _extract(text: str) -> ExtractedJobRequirements:
    return OfflineProvider().extract_job_requirements(text)


# --- regression tests --------------------------------------------------------


def test_mixed_skills_and_years_in_one_sentence() -> None:
    """The confirmed defect: skills + years in one sentence must yield both."""
    result = _extract(MIXED_SENTENCE)
    assert "Python" in result.required_skills, result.required_skills
    assert "SQL" in result.required_skills, result.required_skills
    assert result.experience_requirements, "years requirement missing"
    assert result.experience_requirements[0].years_required == 5.0
    assert result.experience_requirements[0].importance == Importance.REQUIRED


def test_skills_only_sentence_still_works() -> None:
    """A sentence with only skills must not regress."""
    result = _extract(SKILLS_ONLY)
    assert set(result.required_skills) == {"Python", "SQL", "Kubernetes"}
    assert not result.experience_requirements


def test_years_only_sentence_still_works() -> None:
    """A sentence with only years (no skill vocab) must still extract years."""
    result = _extract(YEARS_ONLY)
    assert not result.required_skills
    assert result.experience_requirements
    assert result.experience_requirements[0].years_required == 5.0


def test_preferred_years_also_extracted() -> None:
    """Preferred: X years + skills must yield both preferred skills and preferred years."""
    result = _extract(PREFERRED_YEARS)
    assert "PyTorch" in result.preferred_skills
    assert "TensorFlow" in result.preferred_skills
    assert result.experience_requirements
    assert result.experience_requirements[0].years_required == 3.0
    assert result.experience_requirements[0].importance == Importance.PREFERRED


def test_multiple_requirements_in_single_sentence() -> None:
    """One sentence can produce skills, years, and (potentially) education."""
    result = _extract(MULTI_CATEGORY)
    assert "Python" in result.required_skills
    assert "SQL" in result.required_skills
    assert result.experience_requirements
    assert result.experience_requirements[0].years_required == 5.0
    # Education branch still has its own continue; not required by this fix.
    # But years extraction must not be blocked by skills.


def test_html_description_uses_task11_normalization() -> None:
    """HTML markup must be cleaned (Task 11) before the same logic runs."""
    result = _extract(HTML_MIXED)
    assert "Python" in result.required_skills
    assert result.experience_requirements
    assert result.experience_requirements[0].years_required == 5.0
    # No markup should leak into requirement names.
    import re
    MARKUP = re.compile(r"</?[A-Za-z][^<>]*>|\b(?:href|src|style|class|alt|title)\s*=", re.I)
    for req in result.experience_requirements:
        assert MARKUP.search(req.name) is None, req.name
    for req in result.required_skills:
        assert MARKUP.search(req) is None, req


def test_two_separate_sentences_both_extracted() -> None:
    """Separate sentences for skills and years must both be found (baseline)."""
    result = _extract(TWO_SENTENCES)
    assert "Python" in result.required_skills
    assert "SQL" in result.required_skills
    assert result.experience_requirements
    assert result.experience_requirements[0].years_required == 5.0


def test_extraction_is_deterministic() -> None:
    """Repeated extraction of the same input must yield identical results."""
    for _ in range(3):
        r1 = _extract(MIXED_SENTENCE)
        r2 = _extract(MIXED_SENTENCE)
        assert r1.required_skills == r2.required_skills
        assert [(e.years_required, e.importance) for e in r1.experience_requirements] == [
            (e.years_required, e.importance) for e in r2.experience_requirements
        ]


def test_service_level_extraction_preserves_fix() -> None:
    """``extract_requirements`` service must reflect the fix."""
    from app.services.extraction import extract_requirements
    result = extract_requirements(OfflineProvider(), MIXED_SENTENCE)
    assert result.requirements.required_skills == ["Python", "SQL"]
    assert result.requirements.experience_requirements
    assert result.requirements.experience_requirements[0].years_required == 5.0


def test_fails_with_old_control_flow() -> None:
    """This test documents the pre-fix behaviour - it would fail before the fix."""
    # Before the fix, the skills branch did `continue` and years was never reached.
    # The test asserts the *current* (fixed) behaviour; if someone reintroduces
    # the continue, this test fails.
    result = _extract("Required: Python, 10+ years.")
    # Python is in _SKILL_VOCAB, so skills branch fires.
    assert "Python" in result.required_skills
    # Years must also be captured - this is the fix.
    assert result.experience_requirements
    assert result.experience_requirements[0].years_required == 10.0