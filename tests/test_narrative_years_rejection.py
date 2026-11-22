"""Regression tests for narrative-year false positives in experience extraction.

The defect: ``OfflineProvider.extract_job_requirements`` extracted *any* years
pattern as an experience requirement, even when the sentence contained narrative
references such as company history ("grown over the last 10 years") or customer
age ranges ("16-17 year olds"). These were incorrectly added to
``experience_requirements`` with PREFERRED importance.

The fix adds context-aware filtering: when a sentence lacks explicit
Required/Preferred markers, positive patterns ("years of experience", "years as
a data scientist") confirm a professional experience requirement, while negative
patterns ("year old", "last X years", "founded X years ago", "X years in
[location]") suppress it. Sentences with explicit markers continue to work as
before.

These tests drive the public extraction method. No network, no database, no AI
provider configuration.
"""

from __future__ import annotations

from app.ai.offline_provider import OfflineProvider
from app.models import Importance
from app.schemas import ExtractedJobRequirements


# The exact Monzo sentences that produced false positives.
MONZO_HISTORY = (
    "After starting as a prepaid card, our product offering has grown a lot "
    "in the last 10 years in the UK."
)
MONZO_AGE = (
    "As well as personal and business bank accounts, we offer joint accounts, "
    "accounts for 16-17 year olds, a free kids account and credit cards in the UK."
)

# Explicit required/preferred experience (must continue to work).
EXPLICIT_REQUIRED = "Required: 5+ years of experience in Python."
EXPLICIT_PREFERRED = "Preferred: 3+ years experience with PyTorch."

# Marker-less but genuine experience (supported by existing parser behaviour).
MARKERLESS_YOU_HAVE = "You have 2+ years of experience as a machine learning engineer."
MARKERLESS_PROFESSIONAL = "3+ years professional experience in ML."
MARKERLESS_AS_A_ROLE = "2+ years as a data scientist."
MARKERLESS_IN_FIELD = "4+ years in machine learning."
MARKERLESS_RELEVANT = "3+ years of relevant experience."

# Mixed skills-and-years (Task 12).
MIXED_SKILLS_YEARS = "Required: Python, SQL, and 5+ years of experience building models."
MIXED_PREFERRED = "Preferred: 3+ years with PyTorch and TensorFlow."

# Other narrative patterns that must not become experience.
COMPANY_HISTORY_VARIANTS = [
    "We have been operating for 5 years.",
    "Founded 10 years ago.",
    "Over the past 3 years we have grown.",
    "10 years in the UK market.",
    "5 years at the company.",
    "3 years since launch.",
]
AGE_VARIANTS = [
    "The product is available for 18-25 year olds.",
    "Children 12 years and older welcome.",
]


def _experience(result: ExtractedJobRequirements) -> list[tuple[float | None, Importance, str]]:
    return [(e.years_required, e.importance, e.name) for e in result.experience_requirements]


def test_monzo_company_history_no_experience() -> None:
    """The 10-year company-history statement must not create an experience requirement."""
    result = OfflineProvider().extract_job_requirements(MONZO_HISTORY)
    assert result.experience_requirements == [], (
        f"Expected no experience requirements, got {_experience(result)}"
    )


def test_monzo_customer_age_no_experience() -> None:
    """The 16-17 year-old customer-eligibility statement must not create an experience requirement."""
    result = OfflineProvider().extract_job_requirements(MONZO_AGE)
    assert result.experience_requirements == [], (
        f"Expected no experience requirements, got {_experience(result)}"
    )


def test_explicit_required_experience() -> None:
    """Explicit 'Required:' prefix must yield a REQUIRED experience requirement."""
    result = OfflineProvider().extract_job_requirements(EXPLICIT_REQUIRED)
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    assert years == 5.0
    assert imp == Importance.REQUIRED
    assert "5+ years" in name


def test_explicit_preferred_experience() -> None:
    """Explicit 'Preferred:' prefix must yield a PREFERRED experience requirement."""
    result = OfflineProvider().extract_job_requirements(EXPLICIT_PREFERRED)
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    assert years == 3.0
    assert imp == Importance.PREFERRED
    assert "3+ years" in name


def test_markerless_you_have_experience() -> None:
    """'You have X years experience' is a REQUIRED marker and must work."""
    result = OfflineProvider().extract_job_requirements(MARKERLESS_YOU_HAVE)
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    assert years == 2.0
    assert imp == Importance.REQUIRED


def test_markerless_professional_experience() -> None:
    """'X+ years professional experience' without markers must be captured (positive context)."""
    result = OfflineProvider().extract_job_requirements(MARKERLESS_PROFESSIONAL)
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    assert years == 3.0
    # No explicit marker → defaults to PREFERRED per existing semantics.
    assert imp == Importance.PREFERRED


def test_markerless_as_a_role() -> None:
    """'X+ years as a data scientist' without markers must be captured."""
    result = OfflineProvider().extract_job_requirements(MARKERLESS_AS_A_ROLE)
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    assert years == 2.0
    assert imp == Importance.PREFERRED


def test_markerless_in_field() -> None:
    """'X+ years in machine learning' without markers must be captured."""
    result = OfflineProvider().extract_job_requirements(MARKERLESS_IN_FIELD)
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    assert years == 4.0
    assert imp == Importance.PREFERRED


def test_markerless_relevant_experience() -> None:
    """'X+ years of relevant experience' without markers must be captured."""
    result = OfflineProvider().extract_job_requirements(MARKERLESS_RELEVANT)
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    assert years == 3.0
    assert imp == Importance.PREFERRED


def test_mixed_skills_and_years_task12() -> None:
    """Task 12: mixed skills-and-years sentence must yield both."""
    result = OfflineProvider().extract_job_requirements(MIXED_SKILLS_YEARS)
    assert "Python" in result.required_skills
    assert "SQL" in result.required_skills
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    assert years == 5.0
    assert imp == Importance.REQUIRED


def test_mixed_preferred_skills_and_years_task12() -> None:
    """Task 12: preferred mixed skills-and-years sentence must yield both."""
    result = OfflineProvider().extract_job_requirements(MIXED_PREFERRED)
    assert "PyTorch" in result.preferred_skills
    assert "TensorFlow" in result.preferred_skills
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    assert years == 3.0
    assert imp == Importance.PREFERRED


def test_description_with_both_narrative_and_genuine_experience() -> None:
    """A description containing both narrative years and a genuine experience requirement."""
    text = (
        f"{MONZO_HISTORY} "
        f"Required: 5+ years of experience in Python. "
        f"{MONZO_AGE}"
    )
    result = OfflineProvider().extract_job_requirements(text)
    # Only the explicit requirement should be extracted.
    assert len(result.experience_requirements) == 1, _experience(result)
    years, imp, name = _experience(result)[0]
    assert years == 5.0
    assert imp == Importance.REQUIRED
    assert "Python" in name


def test_html_normalized_before_experience_extraction_task11() -> None:
    """HTML markup must be cleaned (Task 11) before the experience context check runs."""
    html = f"<p>{MONZO_HISTORY}</p><ul><li>Required: 5+ years experience.</li></ul>"
    result = OfflineProvider().extract_job_requirements(html)
    # Narrative cleaned → no exp; list item with marker → exp.
    assert len(result.experience_requirements) == 1, _experience(result)
    years, imp, name = _experience(result)[0]
    assert years == 5.0
    assert imp == Importance.REQUIRED
    # No markup in extracted name.
    import re
    MARKUP = re.compile(r"</?[A-Za-z][^<>]*>|\b(?:href|src|style|class|alt|title)\s*=", re.I)
    assert MARKUP.search(name) is None


def test_deterministic_extraction() -> None:
    """Repeated extraction must produce identical results."""
    for _ in range(5):
        r1 = _experience(OfflineProvider().extract_job_requirements(MONZO_HISTORY))
        r2 = _experience(OfflineProvider().extract_job_requirements(MARKERLESS_PROFESSIONAL))
        assert r1 == []
        assert len(r2) == 1
        assert r2[0][0] == 3.0


def test_company_history_variants_suppressed() -> None:
    """Various company-history phrasings must not create experience requirements."""
    for text in COMPANY_HISTORY_VARIANTS:
        result = OfflineProvider().extract_job_requirements(text)
        assert result.experience_requirements == [], f"Failed for: {text}"


def test_age_variants_suppressed() -> None:
    """Various age-range phrasings must not create experience requirements."""
    for text in AGE_VARIANTS:
        result = OfflineProvider().extract_job_requirements(text)
        assert result.experience_requirements == [], f"Failed for: {text}"


def test_fails_with_original_behavior() -> None:
    """This test would fail with the pre-fix logic (no context check)."""
    # Before the fix, both would produce experience requirements.
    for text in (MONZO_HISTORY, MONZO_AGE):
        result = OfflineProvider().extract_job_requirements(text)
        assert result.experience_requirements == [], f"Regression: {text}"