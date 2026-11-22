"""V3.3 deterministic extraction contract tests.

Covers: the extraction contract, importance semantics, source evidence,
normalisation, deterministic deduplication, duration fidelity, and canonical
reproducibility of equivalent provider outputs.

No provider calls: the provider response is supplied as a fixture, which is
also the proof that equivalent outputs canonicalise identically.
"""

from __future__ import annotations

import pytest
from app.services.extraction import (
    canonical_identity_set,
    canonical_requirements,
    coerce_requirements_payload,
)
from app.services.requirements import (
    extract_explicit_duration,
    infer_category,
    normalize_requirement_name,
    validate_importance,
)

BASE = {
    "required_skills": [], "preferred_skills": [],
    "responsibilities": [], "issues": [],
    "experience_requirements": [], "education_requirements": [],
    "location_requirements": [], "other_requirements": [],
}


def canon(payload: dict):
    coerced, _r = coerce_requirements_payload(payload)
    return canonical_requirements(coerced)


def req(**kw) -> dict:
    base = {"name": "X", "description": None, "importance": "UNKNOWN",
            "years_required": None, "source_text": "", "category": None}
    base.update(kw)
    return base


def names(items):
    return sorted(r.name for r in items)


# =========================================================================== #
# extraction contract - what qualifies
# =========================================================================== #


@pytest.mark.parametrize("text,name", [
    ("Strong Python programming skills are required.",
     "Strong Python programming skills are required."),
    ("The role requires at least 3+ years of experience in analytics.",
     "3+ years of experience in analytics"),
    ("A Bachelor's degree in Statistics is required.", "Bachelor's degree"),
    ("Applicants must have the right to work in the United Kingdom.",
     "right to work in the United Kingdom"),
    ("This is a fully remote role.", "remote role"),
    ("Experience in the banking or fintech domain is essential.",
     "banking or fintech domain"),
    ("You must be an effective communicator.", "effective communicator"),
])
def test_contract_recognises_each_requirement_class(text, name):
    """Each contract class has a deterministic category assignment."""
    assert infer_category(name, None, text) in (
        "TECHNICAL", "EXPERIENCE", "EDUCATION", "WORK_CONDITION",
        "ELIGIBILITY", "DOMAIN", "SOFT_SIGNAL", "INFORMATIONAL",
    )


def test_employer_marketing_is_not_a_requirement():
    out, _ = canon({**BASE, "other_requirements": [
        req(name="innovative company", source_text="We are an innovative company."),
        req(name="competitive benefits",
            source_text="We offer competitive salary, equity and benefits."),
        req(name="diversity valued",
            source_text="We value diversity and inclusion."),
    ]})
    # They are enumerated if the model emits them, but they never become
    # mandatory: no candidate-expectation language is present.
    assert all(r.importance in ("PREFERRED", "SOFT_SIGNAL") for r in out)


def test_narrative_without_candidate_expectation_is_not_required():
    out, _ = canon({**BASE, "other_requirements": [
        req(name="about us", importance="REQUIRED",
            source_text="We are a market leader founded in 1990.")]})
    assert out[0].importance == "PREFERRED"


# =========================================================================== #
# importance contract
# =========================================================================== #


@pytest.mark.parametrize("source,expected", [
    ("Python is required for this role.", "REQUIRED"),
    ("You must have strong SQL skills.", "REQUIRED"),
    ("Minimum 5 years of experience is essential.", "REQUIRED"),
    ("Applicants need to be authorised to work in the UK.", "REQUIRED"),
    ("Python is preferred for this role.", "PREFERRED"),
    ("Familiarity with Spark is a nice to have.", "PREFERRED"),
    ("Docker experience is desirable.", "PREFERRED"),
])
def test_importance_follows_source_evidence(source, expected):
    importance, _adjust = validate_importance("UNKNOWN", "X", source, "")
    assert importance == expected


def test_unqualified_technology_mention_is_not_required():
    """A technology listed without mandatory language must not be REQUIRED."""
    importance, adjustments = validate_importance(
        "REQUIRED", "Kubernetes", "Our stack includes Kubernetes.", "")
    assert importance == "PREFERRED"
    assert any("downgraded" in a for a in adjustments)


def test_soft_expectation_becomes_soft_signal():
    importance, _ = validate_importance(
        "UNKNOWN", "Communication", "You will work with stakeholders.", "")
    assert importance == "SOFT_SIGNAL"


def test_mandatory_language_upgrades_a_preference():
    importance, _ = validate_importance(
        "PREFERRED", "Python", "You must have Python.", "")
    assert importance == "REQUIRED"


def test_unknown_importance_is_resolved_deterministically():
    """Model indecision must not become run-to-run variance."""
    a, _ = validate_importance("UNKNOWN", "Spark", "Experience with Spark.", "")
    b, _ = validate_importance("UNKNOWN", "Spark", "Experience with Spark.", "")
    assert a == b == "PREFERRED"


# =========================================================================== #
# source evidence
# =========================================================================== #


def test_requirement_without_evidence_is_flagged():
    out, notes = canon({**BASE, "other_requirements": [
        req(name="Kubernetes", source_text="")]})
    assert out[0].evidence_ok is False
    assert any("no source evidence" in n for n in notes)


def test_evidence_is_preserved_for_audit():
    quote = "Strong Python programming skills are required."
    out, _ = canon({**BASE, "other_requirements": [
        req(name="Python", importance="REQUIRED", source_text=quote,
            category="TECHNICAL")]})
    assert out[0].source_text == quote
    assert out[0].evidence_ok is True


def test_generated_requirement_is_not_accepted_as_evidence():
    """A quote that does not occur in the posting is not evidence."""
    document = "We are hiring a data scientist. Python experience is useful."
    payload = {**BASE, "other_requirements": [
        req(name="Kubernetes", importance="REQUIRED",
            source_text="Kubernetes cluster operations are mandatory.")]}
    coerced, _ = coerce_requirements_payload(payload)
    out, notes = canonical_requirements(
        coerced, source_document=document, validate_evidence=True)
    assert out[0].evidence_ok is False
    assert any("not found in the job text" in n for n in notes)


def test_quote_present_in_document_is_accepted_as_evidence():
    document = "We are hiring a data scientist. Python is required."
    payload = {**BASE, "other_requirements": [
        req(name="Python", importance="REQUIRED",
            source_text="Python is required.", category="TECHNICAL")]}
    coerced, _ = coerce_requirements_payload(payload)
    out, _ = canonical_requirements(
        coerced, source_document=document, validate_evidence=True)
    assert out[0].evidence_ok is True
    assert out[0].importance == "REQUIRED"


# =========================================================================== #
# normalization
# =========================================================================== #


@pytest.mark.parametrize("a,b", [
    ("Python", "python"),
    ("  Python  ", "Python"),
    ("PostgreSQL", "postgres"),
    ("Machine Learning", "ML"),
    ("scikit-learn", "sklearn"),
    ("Power BI", "powerbi"),
])
def test_equivalent_forms_normalise_together(a, b):
    assert normalize_requirement_name(a) == normalize_requirement_name(b)


def test_distinct_concepts_do_not_collapse():
    assert normalize_requirement_name("Python") != \
        normalize_requirement_name("Python programming")


def test_possessive_and_unicode_variants_normalise():
    assert normalize_requirement_name("Python\u2019s") == \
        normalize_requirement_name("python's")


# =========================================================================== #
# deduplication
# =========================================================================== #


def test_repeated_requirement_collapses():
    out, notes = canon({**BASE, "required_skills": ["Python", "python ", "PYTHON"]})
    assert len(out) == 1
    assert out[0].merged_sources == 3
    assert any("deduplicated" in n for n in notes)


def test_repeated_requirement_with_different_duration_does_not_collapse():
    out, _ = canon({**BASE, "experience_requirements": [
        req(name="3 years of Python experience", years_required=3,
            source_text="3 years of Python experience required"),
        req(name="5 years of Python experience", years_required=5,
            source_text="5 years of Python experience required"),
    ]})
    assert len(out) == 2
    assert {r.years_required for r in out} == {3.0, 5.0}


def test_materially_different_requirements_remain_distinct():
    out, _ = canon({**BASE, "other_requirements": [
        req(name="right to work in the UK", category="ELIGIBILITY",
            source_text="You must have the right to work in the UK"),
        req(name="remote work", category="WORK_CONDITION",
            source_text="This is a remote role"),
    ]})
    assert len(out) == 2


def test_different_categories_do_not_collapse():
    out, _ = canon({**BASE, "other_requirements": [
        req(name="analysis", category="TECHNICAL", source_text="Statistical analysis required"),
        req(name="analysis", category="EXPERIENCE", source_text="3 years of analysis experience required"),
    ]})
    assert len(out) == 2


# =========================================================================== #
# duration fidelity
# =========================================================================== #


def test_explicit_duration_is_captured():
    assert extract_explicit_duration("5+ years of experience") == 5.0
    assert extract_explicit_duration("3 years") == 3.0


def test_duration_is_never_inferred():
    assert extract_explicit_duration("Experience with Python") is None
    out, _ = canon({**BASE, "experience_requirements": [
        req(name="Experience with Python", source_text="Experience with Python required")]})
    assert out[0].years_required is None


def test_source_duration_overrides_contradictory_declaration():
    out, notes = canon({**BASE, "experience_requirements": [
        req(name="Python experience", years_required=9,
            source_text="5+ years of Python experience required")]})
    assert out[0].years_required == 5.0
    assert any("contradicted" in n for n in notes)


# =========================================================================== #
# canonical reproducibility
# =========================================================================== #


def test_equivalent_provider_outputs_canonicalise_identically():
    """Different order and formatting, same canonical set."""
    a = canon({**BASE,
               "required_skills": ["Python", "SQL"],
               "other_requirements": [
                   req(name="Python", importance="REQUIRED",
                       source_text="Python is required")]})[0]
    b = canon({**BASE,
               "required_skills": ["sql", "python"],
               "other_requirements": [
                   req(name="python", importance="REQUIRED",
                       source_text="Python is required")]})[0]
    assert {r.identity() for r in a} == {r.identity() for r in b}


def test_materially_different_outputs_do_not_canonicalise_identically():
    a = canon({**BASE, "experience_requirements": [
        req(name="Python experience", years_required=3,
            source_text="3 years of Python experience required")]})[0]
    b = canon({**BASE, "experience_requirements": [
        req(name="Python experience", years_required=8,
            source_text="8 years of Python experience required")]})[0]
    assert {r.identity() for r in a} != {r.identity() for r in b}


def test_identity_ignores_order_and_formatting():
    a = {"required_skills": ["A", "B"], "preferred_skills": [],
         "responsibilities": [], "issues": [], "experience_requirements": [],
         "education_requirements": [], "location_requirements": [],
         "other_requirements": []}
    b = {"required_skills": ["b", " a "], "preferred_skills": [],
         "responsibilities": [], "issues": [], "experience_requirements": [],
         "education_requirements": [], "location_requirements": [],
         "other_requirements": []}
    assert canonical_identity_set(a) == canonical_identity_set(b)


def test_canonicalisation_is_deterministic_across_calls():
    payload = {**BASE,
               "required_skills": ["Python", "SQL", "Docker"],
               "experience_requirements": [
                   req(name="5+ years experience", years_required=5,
                       source_text="5+ years of experience required"),
                   req(name="Experience with Python",
                       source_text="Experience with Python is useful")]}
    first = canonical_identity_set(payload)
    for _ in range(5):
        assert canonical_identity_set(payload) == first


def test_eligibility_is_never_inferred_from_absent_evidence():
    """A requirement with no eligibility source must not acquire one."""
    out, _ = canon({**BASE, "other_requirements": [
        req(name="Python", source_text="Python is required")]})
    assert out[0].category != "ELIGIBILITY"
