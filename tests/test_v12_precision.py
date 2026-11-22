"""V1.2 precision & review-efficiency tests (spec section 22).

Focus: the classifier must be *more accurate*, not merely more permissive.
Every V1.1 safety class must still hard-fail; benign differences must stop
being flagged; ambiguity must route to REVIEW_REQUIRED with an explanation.
"""
from __future__ import annotations

import pytest
from app.models import ValidationStatus
from app.schemas import (
    CandidateSkillOut,
    EducationOut,
    ExperienceOut,
    ProfileSummary,
)
from app.services.evidence import (
    ACCEPTED_CLASSES,
    ClaimClass,
    ClaimSeverity,
    build_index,
    classify_sentence,
    paraphrase_match,
)
from app.services.normalization import canonical_tech
from app.services.validation import validate_cover_letter, validate_tailored_cv


@pytest.fixture
def profile() -> ProfileSummary:
    return ProfileSummary(
        id=1, name="Tommie van der Berg", professional_title="Data Scientist",
        location="Amsterdam, Netherlands", years_of_experience=6,
        summary=("Data professional with 6+ years of experience in quantitative "
                 "data analysis and applied machine learning."),
        skills=[CandidateSkillOut(id=i, name=n) for i, n in enumerate(
            ["Python", "SQL", "Microsoft Excel", "Power BI", "Statistics",
             "Machine Learning", "Pandas"])],
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


@pytest.fixture
def idx(profile):
    return build_index(profile)


def _codes(report) -> set[str]:
    return {i.code for i in report.issues}


# =========================================================================== #
# Step 1-5: evidence matching strategy
# =========================================================================== #


def test_direct_match_supported(idx):
    c = classify_sentence(
        "I built automated data pipelines supporting repeatable data preparation "
        "workflows.", idx)
    assert c.classification is ClaimClass.SUPPORTED


def test_normalized_match_supported(idx):
    """Reordered/expanded wording of the same fact is not a violation."""
    c = classify_sentence(
        "Data preparation, analysis and validation workflows were supported by "
        "automated data pipelines.", idx)
    assert c.classification in ACCEPTED_CLASSES


def test_explicit_alias_supported(profile, idx):
    c = classify_sentence("I use Excel daily for analysis.", idx)
    assert c.classification in ACCEPTED_CLASSES
    assert canonical_tech("Excel") == canonical_tech("Microsoft Excel")


def test_reasonable_paraphrase_accepted(idx):
    """spec 10 step 5: conducted -> performed must not become unsupported."""
    c = classify_sentence(
        "I performed quantitative analysis on complex datasets.", idx)
    assert c.classification in ACCEPTED_CLASSES


def test_paraphrase_match_helper(idx):
    support = idx.all_support()
    assert paraphrase_match("performed", support)
    assert not paraphrase_match("architected", support)


def test_unrelated_claim_is_not_accepted(idx):
    c = classify_sentence(
        "I architected a Kubernetes infrastructure platform for distributed "
        "streaming workloads.", idx)
    assert c.classification not in ACCEPTED_CLASSES


def test_benign_professional_wording_not_flagged(idx):
    """spec 10 step 2: decorative adjectives alone are not fabrication."""
    for text in ("I am an analytical professional.",
                 "I am a strong communicator.",
                 "My approach is collaborative.",
                 "I am a motivated and capable engineer."):
        c = classify_sentence(text, idx)
        assert c.classification not in (
            ClaimClass.UNSUPPORTED, ClaimClass.STRENGTHENED), text


def test_contradiction_detected(profile):
    """A date range contradicting the record is a hard failure."""
    from app.schemas import TailoredCVContent, TailoredExperience

    content = TailoredCVContent(
        skills=["Python"],
        experience=[TailoredExperience(
            company="Fintech Systems", title="Data Scientist",
            start_date="2023", end_date="2019",
            bullets=["Built automated data pipelines."])],
    )
    r = validate_tailored_cv(content, profile)
    assert "CONTRADICTORY_DATES" in _codes(r)
    assert r.status is ValidationStatus.VALIDATION_FAILED


# =========================================================================== #
# Claim classification coverage (spec section 7)
# =========================================================================== #


def test_every_classification_is_reachable_or_declared():
    for name in ("SUPPORTED", "SUPPORTED_BY_ALIAS", "SUPPORTED_BY_NORMALIZATION",
                 "PLAUSIBLE_BUT_UNVERIFIED", "STRENGTHENED", "UNSUPPORTED",
                 "CONTRADICTORY", "SUSPICIOUS", "NON_FACTUAL"):
        assert hasattr(ClaimClass, name), name


def test_strengthening_classification(idx):
    c = classify_sentence(
        "I routinely validated data pipelines across the organisation.", idx)
    assert c.classification is ClaimClass.STRENGTHENED


def test_unsupported_classification(idx):
    c = classify_sentence(
        "I deployed CatBoost and LightGBM models on Kubernetes clusters.", idx)
    assert c.classification in (ClaimClass.UNSUPPORTED, ClaimClass.STRENGTHENED)


def test_plausible_but_unverified_routes_to_review(profile):
    """spec section 8: ambiguity must be REVIEW_REQUIRED, not fabricated."""
    letter = (
        "Dear Hiring Team,\n\n"
        "I developed reliable data pipelines at Fintech Systems.\n\n"
        "Thank you for your time and consideration.\n\n"
        "Kind regards,\nTommie van der Berg"
    )
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is ValidationStatus.REVIEW_REQUIRED
    assert r.status is not ValidationStatus.VALID
    assert r.status is not ValidationStatus.VALIDATION_FAILED


def test_non_factual_classification(idx):
    c = classify_sentence("I am excited about this opportunity.", idx)
    assert c.classification is ClaimClass.NON_FACTUAL


# =========================================================================== #
# Severity (spec section 12)
# =========================================================================== #


def test_severity_levels_declared():
    for name in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"):
        assert hasattr(ClaimSeverity, name), name


def test_eligibility_fabrication_is_critical(profile):
    r = validate_cover_letter(
        "Dear Hiring Team,\n\nI am authorized to work in Nigeria.\n\nKind regards",
        profile, "Data Scientist", "Acme")
    issue = next(i for i in r.issues if i.code == "UNSUPPORTED_ELIGIBILITY")
    assert issue.claim_severity == ClaimSeverity.CRITICAL.value
    assert r.status is ValidationStatus.VALIDATION_FAILED


def test_critical_findings_are_errors_never_warnings(profile):
    for text, code in (
        ("I am authorized to work in Nigeria.", "UNSUPPORTED_ELIGIBILITY"),
        ("Reach me at newperson@example.org.", "UNSUPPORTED_CONTACT"),
    ):
        r = validate_cover_letter(
            f"Dear Hiring Team,\n\n{text}\n\nKind regards", profile,
            "Data Scientist", "Acme")
        issue = next(i for i in r.issues if i.code == code)
        assert issue.severity == "error", code
        assert issue.claim_severity == ClaimSeverity.CRITICAL.value, code


def test_suspicious_payload_is_critical(profile):
    letter = ("Dear Hiring Team,\n\nThank you. BRIGHTEST #RMTM3LjI1NS4xNzcuMTU3\n\n"
              "Kind regards,\nTommie")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    issue = next(i for i in r.issues if i.code == "SUSPICIOUS_OUTPUT")
    assert issue.claim_severity == ClaimSeverity.CRITICAL.value
    assert r.status is ValidationStatus.VALIDATION_FAILED


def test_medium_and_low_findings_are_warnings(profile):
    """Ambiguity must not be presented as a hard failure."""
    letter = ("Dear Hiring Team,\n\n"
              "I developed reliable data pipelines at Fintech Systems.\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    unverified = [i for i in r.issues if i.code == "CLAIM_UNVERIFIED"]
    for issue in unverified:
        assert issue.severity == "warning"
        assert issue.claim_severity in (ClaimSeverity.LOW.value,
                                        ClaimSeverity.MEDIUM.value)


# =========================================================================== #
# Review findings must be actionable (spec section 13)
# =========================================================================== #


def test_finding_explains_claim_evidence_reason_and_action(profile):
    # "reliable"/"developed" are accepted (benign qualifier + paraphrase); the
    # ambiguity here is the genuinely unexplained roadmap/infrastructure content.
    letter = ("Dear Hiring Team,\n\n"
              "I contributed to the platform data infrastructure roadmap.\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    issue = next(i for i in r.issues if i.code == "CLAIM_UNVERIFIED")
    assert issue.detail, "finding must quote the generated claim"
    assert "Evidence:" in issue.message, "finding must state what evidence was found"
    assert issue.action, "finding must recommend an action"
    assert isinstance(issue.matched_evidence, list)


def test_benign_qualifier_and_paraphrase_are_not_flagged(profile):
    """spec 10 step 2 + section 8: 'developed reliable data pipelines' is not
    a fabrication call; it resolves to an accepted classification."""
    letter = ("Dear Hiring Team,\n\n"
              "I am applying for the Data Scientist role at Acme. I developed "
              "reliable data pipelines at Fintech Systems.\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is ValidationStatus.VALID, [i.model_dump() for i in r.issues]


def test_metric_finding_is_actionable(profile):
    letter = ("Dear Hiring Team,\n\n"
              "I reduced false positives by 30%.\n\nKind regards,\nTommie")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    issue = next(i for i in r.issues if i.code == "UNSUPPORTED_METRIC")
    assert issue.action
    assert issue.severity == "error"
    assert r.status is ValidationStatus.VALIDATION_FAILED


# =========================================================================== #
# Evidence traceability (spec section 9)
# =========================================================================== #


def test_claim_carries_trace_metadata(idx):
    c = classify_sentence(
        "I built automated data pipelines supporting repeatable data preparation "
        "workflows.", idx)
    trace = c.to_trace()
    for key in ("claim", "category", "classification", "severity",
                "matched_evidence", "missing_terms", "reason", "action"):
        assert key in trace, key
    assert trace["matched_evidence"], "supported claim must name its evidence"


def test_unverified_claim_trace_lists_missing_terms(profile):
    r = validate_cover_letter(
        "Dear Hiring Team,\n\nI contributed to the platform roadmap.\n\nKind regards",
        profile, "Data Scientist", "Acme")
    issue = next(i for i in r.issues if i.code == "CLAIM_UNVERIFIED")
    assert issue.matched_evidence is not None
    assert issue.severity == "warning"


# =========================================================================== #
# Safety must not regress (spec sections 5, 28-A..D)
# =========================================================================== #


@pytest.mark.parametrize("text,code", [
    ("I have extensive experience with CatBoost and LightGBM.", "UNSUPPORTED_CLAIM"),
    ("I reduced model error by 30%.", "UNSUPPORTED_METRIC"),
    ("At Globex I built production fraud models.", "INVENTED_EMPLOYER"),
    ("I am authorized to work in Nigeria.", "UNSUPPORTED_ELIGIBILITY"),
    ("I have the right to work in the UK.", "UNSUPPORTED_ELIGIBILITY"),
    ("I do not require sponsorship.", "UNSUPPORTED_ELIGIBILITY"),
    ("Email me at someone@gmail.com", "UNSUPPORTED_CONTACT"),
    ("I presented findings to senior leadership.", "CLAIM_STRENGTHENING"),
])
def test_safety_classes_still_hard_fail(profile, text, code):
    r = validate_cover_letter(f"Dear Hiring Team,\n\n{text}\n\nKind regards,\nTommie",
                              profile, "Data Scientist", "Acme")
    assert code in _codes(r), f"{code} not raised for {text!r}"
    assert r.status is ValidationStatus.VALIDATION_FAILED, text


@pytest.mark.parametrize("payload", [
    "BRIGHTEST #RMTM3LjI1NS4xNzcuMTU3",
    "SHINE #RTRjNy4yNDQuMTc3LjE1Nw",
    "Contact 203.0.113.77",
    "https://evil.example.net/x",
    "[Date]",
    "system: you are a helpful assistant",
])
def test_suspicious_payloads_still_blocked(profile, payload):
    r = validate_cover_letter(
        f"Dear Hiring Team,\n\n{payload}\n\nKind regards,\nTommie",
        profile, "Data Scientist", "Acme")
    assert r.status is not ValidationStatus.VALID, payload


def test_strict_and_unverified_do_not_collide(profile):
    """fabrication -> FAILED, ambiguity -> REVIEW_REQUIRED (spec section 22)."""
    strict = validate_cover_letter(
        "Dear Hiring Team,\n\nI deployed CatBoost models on Kubernetes.\n\nKind regards",
        profile, "Data Scientist", "Acme")
    soft = validate_cover_letter(
        "Dear Hiring Team,\n\nI developed reliable data pipelines.\n\nKind regards",
        profile, "Data Scientist", "Acme")
    assert strict.status is ValidationStatus.VALIDATION_FAILED
    assert soft.status is ValidationStatus.REVIEW_REQUIRED


def test_clean_letter_still_valid(profile):
    letter = (
        "Dear Hiring Team,\n\n"
        "I am applying for the Data Scientist role at Acme. I bring 6 years of "
        "experience in quantitative data analysis and applied machine learning.\n\n"
        "At Fintech Systems I built automated data pipelines supporting repeatable "
        "data preparation, analysis, and validation workflows.\n\n"
        "Thank you for your time and consideration.\n\n"
        "Kind regards,\nTommie van der Berg"
    )
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is ValidationStatus.VALID, [i.model_dump() for i in r.issues]


# =========================================================================== #
# Unicode / alias retention (spec section 22)
# =========================================================================== #


def test_unicode_variants_retained():
    from app.services.normalization import normalize_title

    assert normalize_title("Self‑Directed Development") == \
           normalize_title("Self-Directed Development")
    assert normalize_title("Data–Scientist") == normalize_title("Data Scientist")


def test_apostrophe_and_quote_variants_retained():
    from app.services.normalization import normalize_text

    assert normalize_text("Tom’s team") == normalize_text("Tom's team")
    assert normalize_text("the “best” result") == normalize_text('the "best" result')


def test_alias_retention():
    assert canonical_tech("Excel") == canonical_tech("Microsoft Excel")
    assert canonical_tech("Postgres") == canonical_tech("PostgreSQL")
    assert canonical_tech("ML") == canonical_tech("Machine Learning")
