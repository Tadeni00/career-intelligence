"""Regression tests for HTML markup in stored job descriptions.

The defect: ``OfflineProvider.extract_job_requirements`` split the stored job
description on sentence punctuation and newline characters without ever
separating markup from text. Descriptions captured from posting pages therefore
produced requirement names such as::

    <p<span style="font-weight: 400;"✅ We can sponsor visas

Two separate corruptions are covered here. Well-formed or lightly broken
fragments (``<p<span style="font-weight: 400;">``) are handled by the parser.
More damaging is capture tooling that strips every ``>`` from the document, so
the stored text contains no well-formed tag at all - 7 of the 14 stored jobs
look like this, with dozens of ``<`` and zero ``>``. Both are repaired before
parsing so that requirement names, descriptions and the 120-character name
limit measure real content.

These tests drive the provider's public extraction method, the service-level
``extract_requirements`` path, and the normalisation helper directly. No
network, no database, no AI provider configuration.
"""

from __future__ import annotations

import re

from app.ai.offline_provider import OfflineProvider
from app.models import Importance
from app.schemas import ExtractedJobRequirements
from app.services.extraction import extract_requirements
from app.services.normalization import html_to_text

# Anything that still looks like a tag, or like an attribute fragment.
MARKUP_RE = re.compile(
    r"</?[A-Za-z][^<>]*>" r"|" r"\b(?:href|src|style|class|alt|title)\s*=",
    re.IGNORECASE,
)

# Reproduces the real capture: every ">" removed from an otherwise normal page.
BRACKET_LESS_JD = (
    '<div class="content-intro"<pWe are hiring a Data Scientist.'
    '<ul<liRequired: Python, SQL, and 5+ years of experience.'
    '<liRequired: Demonstrable ownership of at least one production '
    'data pipeline.'
    '<liPreferred: Familiarity with dbt is a plus.</ul>'
    '<pApply at Acme &amp; Co.'
    ' href="https://acme.example/jobs/1"now.</p>'
)

PLAIN_JD = """\
Data Scientist at Example Analytics.

Required: Python, SQL, and 5+ years of experience building models.
Preferred: Familiarity with dbt is a plus.
"""


def _other(result: ExtractedJobRequirements) -> list[tuple[str, str]]:
    return [(r.importance.value, r.name) for r in result.other_requirements]


# --- helper level ------------------------------------------------------------


def test_ordinary_html_becomes_readable_text() -> None:
    assert html_to_text("<p>We are hiring a Data Scientist.</p>") == (
        "We are hiring a Data Scientist."
    )
    assert html_to_text(
        '<div class="intro"><span style="font-weight: 400;">Apply now.</span></div>'
    ) == "Apply now."


def test_malformed_fragment_does_not_leak_tags() -> None:
    """The exact shape reported in the defect."""
    out = html_to_text(
        '<p<span style="font-weight: 400;">✅ We can sponsor a visa.</span></p>'
    )
    assert out == "✅ We can sponsor a visa."
    assert MARKUP_RE.search(out) is None


def test_bracket_less_markup_is_repaired() -> None:
    """Capture that stripped every ">" leaves no well-formed tag to parse."""
    out = html_to_text(BRACKET_LESS_JD)
    assert "We are hiring a Data Scientist." in out
    assert "Required: Python, SQL, and 5+ years of experience." in out
    assert MARKUP_RE.search(out) is None


def test_bracket_less_repair_does_not_eat_prose() -> None:
    """A tag name must not absorb the word that follows it."""
    assert html_to_text("<pAfter starting as a card, we grew a lot.") == (
        "After starting as a card, we grew a lot."
    )
    assert html_to_text("<pWe are hiring in London.") == "We are hiring in London."
    # A "<" that is not a tag stays a "<".
    assert html_to_text("Budget < 50000 and 5 < 10 years.") == (
        "Budget < 50000 and 5 < 10 years."
    )


def test_html_entities_are_decoded() -> None:
    assert html_to_text("At Acme &amp; Co.") == "At Acme & Co."
    assert html_to_text("Python &#8211; 5 years") == "Python \u2013 5 years"
    assert html_to_text("<p>R&amp;D focus</p>") == "R&D focus"


def test_lists_keep_requirement_boundaries() -> None:
    out = html_to_text("<ul><li>Required: Python</li><li>Required: SQL</li></ul>")
    assert out.split("\n") == ["Required: Python", "Required: SQL"]


def test_script_and_style_content_is_not_text() -> None:
    assert html_to_text(
        '<script>var x = "Required: Hacker";</script><p>Required: R</p>'
    ) == "Required: R"
    assert html_to_text(
        "<style>.a{color:red}</style><p>Required: S</p>"
    ) == "Required: S"
    # Nothing but a script leaves no text at all.
    assert html_to_text("<script>secret()</script>") == ""


def test_plain_text_is_unchanged_apart_from_entities() -> None:
    assert html_to_text(PLAIN_JD) == PLAIN_JD
    assert html_to_text("Just a sentence.") == "Just a sentence."
    assert html_to_text("5 < 10 and 3 > 2") == "5 < 10 and 3 > 2"


def test_empty_and_unusable_input_yields_empty_string() -> None:
    assert html_to_text(None) == ""
    assert html_to_text("") == ""
    assert html_to_text("<p></p>") == ""
    assert html_to_text("<div><span></span></div>") == ""


def test_repeated_normalisation_is_deterministic() -> None:
    for source in (BRACKET_LESS_JD, PLAIN_JD, "<ul><li>Required: X</li></ul>"):
        assert html_to_text(source) == html_to_text(source)


# --- public extraction path --------------------------------------------------


def test_public_extraction_removes_markup_from_requirement_names() -> None:
    result = OfflineProvider().extract_job_requirements(BRACKET_LESS_JD)
    assert result.other_requirements
    for requirement in result.other_requirements:
        assert MARKUP_RE.search(requirement.name) is None, requirement.name
        assert MARKUP_RE.search(requirement.description) is None


def test_public_extraction_preserves_required_and_preferred() -> None:
    """Task 10 write-back still works once the text is clean."""
    result = OfflineProvider().extract_job_requirements(BRACKET_LESS_JD)
    pairs = _other(result)
    required = [n for i, n in pairs if i == "REQUIRED"]
    preferred = [n for i, n in pairs if i == "PREFERRED"]

    assert any("production data pipeline" in n for n in required), pairs
    assert any("dbt" in n for n in preferred), pairs
    assert all(i in {"REQUIRED", "PREFERRED"} for i, _ in pairs)


def test_importance_and_lengths_are_correct_after_cleanup() -> None:
    result = OfflineProvider().extract_job_requirements(BRACKET_LESS_JD)
    assert result.other_requirements
    for requirement in result.other_requirements:
        assert isinstance(requirement.importance, Importance)
        # The name limit must measure content, not markup.
        assert len(requirement.name) <= 120
        assert requirement.name == requirement.name.strip()
        assert requirement.description.startswith(requirement.name[:20])


def test_public_extraction_on_plain_text_is_unchanged() -> None:
    clean = OfflineProvider().extract_job_requirements(PLAIN_JD)
    pairs = _other(clean)
    assert clean.required_skills == ["Python", "SQL"], pairs
    assert any("dbt" in n for i, n in pairs if i == "PREFERRED"), pairs
    for _, name in pairs:
        assert MARKUP_RE.search(name) is None, name


def test_public_extraction_is_deterministic() -> None:
    provider = OfflineProvider()
    first = _other(provider.extract_job_requirements(BRACKET_LESS_JD))
    second = _other(provider.extract_job_requirements(BRACKET_LESS_JD))
    assert first == second


def test_empty_html_creates_no_invented_requirements() -> None:
    for source in ("", "   ", "<p></p>", "<script>x()</script>", "<html><body></body></html>"):
        result = OfflineProvider().extract_job_requirements(source)
        assert result.other_requirements == [], source
        assert result.required_skills == [], source
        assert result.preferred_skills == [], source


def test_service_level_extraction_cleans_markup() -> None:
    """``extract_requirements`` is what the jobs service persists; it must be clean."""
    result = extract_requirements(OfflineProvider(), BRACKET_LESS_JD)
    assert result.requirements.other_requirements
    for requirement in result.requirements.other_requirements:
        assert MARKUP_RE.search(requirement.name) is None, requirement.name
    pairs = _other(result.requirements)
    assert any("production data pipeline" in n for _, n in pairs), pairs
    assert any("dbt" in n for i, n in pairs if i == "PREFERRED"), pairs
    assert result.meta.requirement_count > 0