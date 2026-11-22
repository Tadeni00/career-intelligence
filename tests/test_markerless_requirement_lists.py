"""Regression tests for marker-less requirement list extraction.

The defect: ``OfflineProvider.extract_job_requirements`` required explicit
``Required:`` or ``Preferred:`` markers to extract skills or experience
requirements. Structured job descriptions using headings like "Requirements:"
followed by bullet lists without per-bullet markers were not parsed.

The fix adds section-aware parsing: when a recognized requirements-section
heading (``Requirements``, ``Qualifications``, etc.) is found, subsequent
sentences are treated as implicit requirements even without per-sentence
markers. Non-requirement sections (benefits, legal, etc.) are excluded.

These tests cover the SEAhub-style description structure and verify backward
compatibility with explicit-marker descriptions.
"""

from __future__ import annotations

from app.ai.offline_provider import OfflineProvider
from app.models import Importance
from app.schemas import ExtractedJobRequirements


# Synthetic SEAhub-style description: marketing intro -> Job Summary ->
# Responsibilities -> Requirements (marker-less bullets) -> Benefits
SEAHUB_STYLE = """\
Build What's Next With Us

At SEAhub Asia, your career isn't just a job - it's a launchpad.
We move fast, think big, and build futures together.

Job Summary
Support the Data Analytics team by assisting with data validation, report generation, and basic analysis.

Responsibilities:
Prepare reports and perform data analysis to support data-driven decision-making.
Monitor key business performance metrics to identify trends, patterns, and anomalies.

Requirements:
0-1 year of experience in data analysis or a related field.
Foundational knowledge of SQL, Excel, and data visualization platforms such as Power BI or Tableau.
Exposure to Python for data analysis is an added advantage.
Highly detail-oriented with a strong focus on maintaining data quality and accuracy.
Strong communication skills with the ability to present findings and insights clearly.
Demonstrates a proactive mindset and willingness to learn new tools, technologies, and analytical techniques.
Well-organized, with the ability to prioritize and manage multiple tasks effectively.

Benefits:
Competitive salary packages for high performers.
Wellbeing perks that help you thrive inside and outside work.
"""

# Explicit marker description (backward compatibility)
EXPLICIT_MARKERS = """\
Required: Python, SQL, and 5+ years of experience.
Preferred: Familiarity with dbt.
"""

# Mixed: explicit skills marker, marker-less experience
MIXED_MARKERLESS_EXP = """\
Required: Python, SQL.
3+ years of experience in machine learning.
"""

# Benefits section that must not become requirements
BENEFITS_ONLY = """\
Benefits:
Competitive salary.
Health insurance.
Free lunch.
"""

# Legal/disclaimer section that must not become requirements
LEGAL_ONLY = """\
Equal opportunity employer. We celebrate diversity.
"""


def _skills(result: ExtractedJobRequirements) -> list[str]:
    return list(result.required_skills) + list(result.preferred_skills)


def _experience(result: ExtractedJobRequirements) -> list[tuple[float | None, Importance, str]]:
    return [(e.years_required, e.importance, e.name) for e in result.experience_requirements]


def _other(result: ExtractedJobRequirements) -> list[tuple[Importance, str]]:
    return [(o.importance, o.name) for o in result.other_requirements]


def test_seahub_style_extracts_skills_from_markerless_bullets() -> None:
    """SEAhub-style Requirements section yields skills without per-bullet markers."""
    result = OfflineProvider().extract_job_requirements(SEAHUB_STYLE)
    # SQL, Excel, Power BI, Tableau, Python should be found
    skills = _skills(result)
    assert "SQL" in skills, skills
    assert "Excel" in skills, skills
    assert "Power BI" in skills, skills
    assert "Tableau" in skills, skills
    assert "Python" in skills, skills
    # All should be PREFERRED (conservative default for implicit requirements)
    assert result.required_skills == [], result.required_skills
    assert set(result.preferred_skills) == {"SQL", "Excel", "Power BI", "Tableau", "Python"}


def test_seahub_style_extracts_experience_without_numeric_range() -> None:
    """The '0-1 year of experience' sentence becomes an experience requirement."""
    result = OfflineProvider().extract_job_requirements(SEAHUB_STYLE)
    assert result.experience_requirements
    years, imp, name = _experience(result)[0]
    # The synthetic description preserves "0-1" so years=0.0 (first number in range).
    assert years == 0.0
    assert imp == Importance.REQUIRED
    assert "experience" in name.lower()


def test_seahub_style_soft_skills_become_other_requirements() -> None:
    """Behavioral bullets in requirements section become generic OTHER requirements."""
    result = OfflineProvider().extract_job_requirements(SEAHUB_STYLE)
    other = _other(result)
    # Should capture detail-oriented, communication, proactive, organized
    assert any("detail" in n.lower() for _, n in other), other
    assert any("communication" in n.lower() for _, n in other), other
    assert any("proactive" in n.lower() for _, n in other), other
    assert any("organized" in n.lower() for _, n in other), other


def test_benefits_section_excluded() -> None:
    """Benefits section must not produce any requirements."""
    result = OfflineProvider().extract_job_requirements(BENEFITS_ONLY)
    assert result.required_skills == []
    assert result.preferred_skills == []
    assert result.experience_requirements == []
    assert result.other_requirements == []


def test_legal_section_excluded() -> None:
    """Legal/disclaimer section must not produce requirements."""
    result = OfflineProvider().extract_job_requirements(LEGAL_ONLY)
    assert result.required_skills == []
    assert result.preferred_skills == []
    assert result.experience_requirements == []
    assert result.other_requirements == []


def test_explicit_markers_still_work() -> None:
    """Backward compatibility: explicit Required/Preferred markers work without sections."""
    result = OfflineProvider().extract_job_requirements(EXPLICIT_MARKERS)
    assert "Python" in result.required_skills
    assert "SQL" in result.required_skills
    # "dbt" is not in skill vocabulary, so it becomes a generic PREFERRED other requirement.
    other = _other(result)
    assert any("dbt" in n for _, n in other), other
    assert result.experience_requirements
    years, imp, _ = _experience(result)[0]
    assert years == 5.0
    assert imp == Importance.REQUIRED


def test_mixed_explicit_skills_markerless_experience() -> None:
    """Explicit skills marker + marker-less experience sentence in same description.

    Without a requirements section, the experience sentence defaults to PREFERRED
    (conservative), even though it has positive context. This is correct behaviour:
    explicit markers or a requirements section are needed for REQUIRED.
    """
    result = OfflineProvider().extract_job_requirements(MIXED_MARKERLESS_EXP)
    assert "Python" in result.required_skills
    assert "SQL" in result.required_skills
    assert result.experience_requirements
    years, imp, _ = _experience(result)[0]
    assert years == 3.0
    assert imp == Importance.PREFERRED


def test_seahub_html_normalization_before_section_detection() -> None:
    """HTML markup is cleaned (Task 11) before section detection runs."""
    html = (
        "<div>Marketing intro</div>"
        "<h2>Requirements:</h2>"
        "<ul><li>Foundational knowledge of SQL and Excel.</li>"
        "<li>Exposure to Python.</li></ul>"
    )
    result = OfflineProvider().extract_job_requirements(html)
    skills = _skills(result)
    assert "SQL" in skills
    assert "Excel" in skills
    assert "Python" in skills
    # No markup in extracted names
    import re
    MARKUP = re.compile(r"</?[A-Za-z][^<>]*>|\b(?:href|src|style|class|alt|title)\s*=", re.I)
    for skill in skills:
        assert MARKUP.search(skill) is None
    for _, _, name in _experience(result):
        assert MARKUP.search(name) is None
    for _, name in _other(result):
        assert MARKUP.search(name) is None


def test_deterministic_extraction() -> None:
    """Repeated extraction yields identical results."""
    for _ in range(5):
        r1 = OfflineProvider().extract_job_requirements(SEAHUB_STYLE)
        r2 = OfflineProvider().extract_job_requirements(SEAHUB_STYLE)
        assert r1.required_skills == r2.required_skills
        assert r1.preferred_skills == r2.preferred_skills
        assert [(e.years_required, e.importance) for e in r1.experience_requirements] == [
            (e.years_required, e.importance) for e in r2.experience_requirements
        ]


def test_empty_description_yields_no_requirements() -> None:
    for source in ("", "   ", "<p></p>", "<div>Benefits:</div><ul><li>Free lunch</li></ul>"):
        result = OfflineProvider().extract_job_requirements(source)
        assert result.required_skills == [], source
        assert result.preferred_skills == [], source
        assert result.experience_requirements == [], source
        assert result.other_requirements == [], source


def test_fails_with_previous_implementation() -> None:
    """This test would fail before the section-aware fix."""
    # Before the fix, marker-less bullets in a Requirements section produced nothing.
    result = OfflineProvider().extract_job_requirements(SEAHUB_STYLE)
    assert "SQL" in result.preferred_skills
    assert result.experience_requirements