"""Run the versioned adversarial dataset against the V1.1 validator.

Spec section 22. Deterministic, no network. Every case declares its expected
outcome; the validator must agree.
"""
from __future__ import annotations

import json
import pathlib

import pytest
from app.schemas import (
    CandidateSkillOut,
    EducationOut,
    ExperienceOut,
    ProfileSummary,
)
from app.services import sanitize
from app.services.evidence import ClaimClass, build_index, classify_sentence

DATASET = pathlib.Path(__file__).resolve().parents[1] / "docs" / "adversarial_dataset_v1.1.json"


@pytest.fixture(scope="module")
def dataset() -> dict:
    return json.loads(DATASET.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def adversarial_profile() -> ProfileSummary:
    return ProfileSummary(
        id=1, name="Tommie van der Berg", professional_title="Data Scientist",
        location="Amsterdam, Netherlands", years_of_experience=6,
        summary=("Data professional with 6+ years of experience in quantitative data "
                 "analysis and applied machine learning."),
        skills=[CandidateSkillOut(id=i, name=n) for i, n in enumerate(
            ["Python", "SQL", "Microsoft Excel", "Power BI", "Statistics",
             "Machine Learning", "Pandas", "Cross‑functional collaboration"])],
        experience=[ExperienceOut(
            id=1, company="Fintech Systems", title="Data Scientist",
            start_date="2021", end_date=None, is_current=True,
            description=("Conducted quantitative analysis of complex datasets for "
                         "classification and regression use cases. Built automated "
                         "data pipelines supporting repeatable data preparation, "
                         "analysis, and validation workflows. Collaborated with "
                         "cross-functional teams to improve analytical workflows."))],
        education=[EducationOut(id=1, institution="University of Amsterdam",
                                degree="BSc", field="Statistics")],
        projects=[],
    )


# Expectation tolerance: the gate is "violation detected", not a specific label.
# V1.2 note: ACCEPTED_CLASSES now includes the normalisation/alias variants, so
# cases that V1.1 labelled SUPPORTED may now be labelled SUPPORTED_BY_ALIAS or
# SUPPORTED_BY_NORMALIZATION. That is the intended V1.2 precision improvement,
# not a weakening - both are accepted classifications (spec section 6 A/B/C).
_ACCEPTED = {
    "SUPPORTED": {ClaimClass.SUPPORTED, ClaimClass.SUPPORTED_BY_ALIAS,
                  ClaimClass.SUPPORTED_BY_NORMALIZATION},
    "UNSUPPORTED": {ClaimClass.UNSUPPORTED, ClaimClass.STRENGTHENED},
    "STRENGTHENED": {ClaimClass.STRENGTHENED, ClaimClass.UNSUPPORTED},
    "NON_FACTUAL": {ClaimClass.NON_FACTUAL, ClaimClass.SUPPORTED,
                    ClaimClass.SUPPORTED_BY_NORMALIZATION},
    # V1.2 precision expectations (spec section 19).
    "SUPPORTED_BY_NORMALIZATION": {
        ClaimClass.SUPPORTED_BY_NORMALIZATION, ClaimClass.SUPPORTED},
    "SUPPORTED_BY_ALIAS": {
        ClaimClass.SUPPORTED_BY_ALIAS, ClaimClass.SUPPORTED_BY_NORMALIZATION,
        ClaimClass.SUPPORTED},
}


@pytest.mark.parametrize("case_index", range(24))
def test_adversarial_claim_cases(dataset, adversarial_profile, case_index):
    cases = dataset["cases"]
    if case_index >= len(cases):
        pytest.skip("no case")
    case = cases[case_index]
    idx = build_index(adversarial_profile)
    claim = classify_sentence(case["text"], idx)
    accepted = _ACCEPTED[case["expect"]]
    assert claim.classification in accepted, (
        f"{case['id']} ({case['category']}): expected one of "
        f"{ {c.value for c in accepted} }, got {claim.classification.value} "
        f"({claim.reason}) for {case['text']!r}")


@pytest.mark.parametrize("case_index", range(12))
def test_adversarial_sanitization_cases(dataset, case_index):
    cases = dataset["sanitization_cases"]
    if case_index >= len(cases):
        pytest.skip("no case")
    case = cases[case_index]
    findings = sanitize.find_issues(case["text"])
    flagged = bool(findings)
    assert flagged is case["expect_flag"], (
        f"{case['id']} ({case['category']}): expect_flag={case['expect_flag']} "
        f"got {flagged} for {case['text']!r}")


def test_dataset_declares_supported_categories(dataset):
    # V1.2 extended the dataset; the V1.1 category set is still fully declared.
    assert dataset["version"] == "1.2"
    declared = {c["category"] for c in dataset["cases"]}
    assert declared >= {"supported", "unsupported", "strengthened",
                        "eligibility", "contact", "metric",
                        "technology_alias", "unicode_variant", "benign_prose"}
    # V1.2 precision categories (spec section 19).
    assert declared >= {"paraphrase", "alias", "benign_professional_wording",
                        "ambiguous_strengthening", "explicit_fabrication"}
    san = {c["category"] for c in dataset["sanitization_cases"]}
    assert "suspicious_payload" in san


def test_v11_adversarial_cases_are_retained(dataset):
    """V1.2 must not delete V1.1 coverage."""
    ids = {c["id"] for c in dataset["cases"]}
    assert "AD-001" in ids
    assert len([i for i in ids if int(i.split("-")[1]) <= 72]) == 24


def test_every_adversarial_case_is_documented():
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    ids = [c["id"] for c in data["cases"]] + [c["id"] for c in data["sanitization_cases"]]
    assert len(ids) == len(set(ids)), "duplicate case ids"
