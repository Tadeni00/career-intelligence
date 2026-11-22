"""V1.1 evidence-integrity and output-safety regression tests.

Covers every known V1 real-world failure (spec section 19). Each test names the
defect class it locks down. Deterministic: no network, no LLM.
"""
from __future__ import annotations

import json

import pytest
from app.models import ValidationStatus
from app.schemas import (
    CandidateSkillOut,
    EducationOut,
    ExperienceOut,
    ProfileSummary,
    TailoredCVContent,
    TailoredExperience,
)
from app.services import sanitize
from app.services.evidence import (
    ClaimClass,
    build_index,
    classify_sentence,
)
from app.services.normalization import canonical_tech, normalize_title
from app.services.validation import (
    classify_requirement,
    is_soft_signal,
    validate_cover_letter,
    validate_tailored_cv,
)


# --------------------------------------------------------------------------- #
# Profile fixture: deliberately does NOT contain scikit-learn, AWS, a metric,
# an email/phone, or any work-authorization statement.
# --------------------------------------------------------------------------- #
@pytest.fixture
def profile() -> ProfileSummary:
    return ProfileSummary(
        id=1,
        name="Tommie van der Berg",
        professional_title="Data Scientist",
        location="Amsterdam, Netherlands",
        years_of_experience=6,
        summary=("Data professional with 6+ years of experience in quantitative data "
                 "analysis and applied machine learning."),
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
                         "cross-functional teams to improve analytical workflows.")),
            ExperienceOut(
            id=2, company="Analytics Works", title="Data Analytics Tutor",
            start_date="2018", end_date="2021", is_current=False,
            description=("Taught statistics and practical data analytics. Conducted "
                         "statistical analysis using SPSS and Microsoft Excel.")),
        ],
        education=[EducationOut(id=1, institution="University of Amsterdam",
                                degree="BSc", field="Statistics")],
        projects=[],
    )


def _codes(report) -> set[str]:
    return {i.code for i in report.issues}


def _errors(report) -> set[str]:
    return {i.code for i in report.issues if i.severity == "error"}


# =========================================================================== #
# 1-10  Evidence failures
# =========================================================================== #


def test_01_invented_technology_detected(profile):
    letter = ("Dear Hiring Team,\n\n"
              "I have extensive experience with scikit-learn and CatBoost for modelling.\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is ValidationStatus.VALIDATION_FAILED
    # Gate A: the fabricated technology must be detected (any evidence code).
    assert _errors(r)


def test_02_invented_metric_detected(profile):
    letter = ("Dear Hiring Team,\n\n"
              "I reduced false positives by 30% and saved $1.2m in annual losses.\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert "UNSUPPORTED_METRIC" in _errors(r)


def test_03_invented_employer_detected(profile):
    letter = ("Dear Hiring Team,\n\n"
              "At Globex I built production fraud detection models.\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is ValidationStatus.VALIDATION_FAILED
    assert _errors(r)


def test_04_invented_title_detected():
    content = TailoredCVContent(
        summary=None, skills=["Python"],
        experience=[TailoredExperience(company="Fintech Systems",
                                      title="Chief Data Officer",
                                      start_date="2021", end_date=None,
                                      bullets=["Built automated data pipelines "
                                               "supporting repeatable data preparation workflows."])],
    )
    prof = ProfileSummary(
        id=1, name="Tommie", professional_title="Data Scientist",
        experience=[ExperienceOut(id=1, company="Fintech Systems", title="Data Scientist",
                                  start_date="2021", is_current=True,
                                  description="Built automated data pipelines.")],
    )
    r = validate_tailored_cv(content, prof)
    assert "INVENTED_POSITION" in _errors(r)


def test_05_invented_client_detected(profile):
    letter = ("Dear Hiring Team,\n\n"
              "I worked closely with product owners and design teams at Globex.\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is ValidationStatus.VALIDATION_FAILED
    assert _errors(r)


def test_06_invented_responsibility_detected(profile):
    letter = ("Dear Hiring Team,\n\n"
              "I architected a distributed feature store and designed a real-time "
              "streaming platform for fraud scoring.\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is ValidationStatus.VALIDATION_FAILED


def test_07_strengthened_responsibility_detected(profile):
    """V1 real case: 'built pipelines supporting validation' -> 'routinely validated pipelines'."""
    idx = build_index(profile)
    claim = classify_sentence(
        "I routinely validated data pipelines across the organisation.", idx)
    assert claim.classification is ClaimClass.STRENGTHENED


def test_08_strengthened_collaboration_detected(profile):
    """V1 real case: cross-functional teams -> engineers and product owners."""
    idx = build_index(profile)
    claim = classify_sentence(
        "Collaborated with engineers and product owners to improve analytical workflows.",
        idx)
    assert claim.classification in (ClaimClass.STRENGTHENED, ClaimClass.UNSUPPORTED)


def test_09_unsupported_eligibility_claim_detected(profile):
    """V1 real false-negative: work authorisation asserted with no evidence."""
    for text in ("I am authorized to work in Nigeria.",
                 "I have the right to work in the Netherlands.",
                 "I do not require sponsorship.",
                 "I am eligible to work in the EU."):
        r = validate_cover_letter(f"Dear Hiring Team,\n\n{text}\n\nKind regards,\nTommie",
                                  profile, "Data Scientist", "Acme")
        assert "UNSUPPORTED_ELIGIBILITY" in _errors(r), text


def test_10_invented_contact_information_detected(profile):
    for text in ("You can reach me at jane.doe@gmail.com.",
                 "Call me on +234 705 484 8225.",
                 "See https://tommie.dev/portfolio for details."):
        r = validate_cover_letter(f"Dear Hiring Team,\n\n{text}\n\nKind regards,\nTommie",
                                  profile, "Data Scientist", "Acme")
        assert r.status is ValidationStatus.VALIDATION_FAILED
        assert _errors(r) & {"UNSUPPORTED_CONTACT", "SUSPICIOUS_OUTPUT"}, text


# =========================================================================== #
# 11-15  Known VJ-03 failure (letter that V1 graded VALID)
# =========================================================================== #

VJ03_PAYLOAD = "BRIGHTEST #RMTM3LjI1NS4xNzcuMTU3"


def test_11_encoded_ip_payload_detected(profile):
    findings = sanitize.find_issues(
        f"Dear Hiring Team,\n\nThank you for your time. {VJ03_PAYLOAD}\n\nKind regards,\nT")
    codes = {f["code"] for f in findings}
    assert codes & {"SUSPICIOUS_OUTPUT"}
    assert any("base64-encoded IP" in f["message"] for f in findings)


def test_12_suspicious_brightest_marker_detected(profile):
    findings = sanitize.find_issues(f"Dear Hiring Team,\n\n{VJ03_PAYLOAD}\n\nKind regards")
    assert any("marker" in f["message"] for f in findings)


def test_12b_other_encoded_ips_are_detected_not_just_this_string(profile):
    for payload in ("SHINE #RTRjNy4yNDQuMTc3LjE1Nw==", "TRACKER QVNSMS4yNDQuMTc3LjE1Nw"):
        findings = sanitize.find_issues(f"Dear team,\n\n{payload}\n\nRegards")
        assert {f["code"] for f in findings} & {"SUSPICIOUS_OUTPUT"}, payload


def test_12c_plain_base64_without_suspicion_is_not_rejected(profile):
    """Base64-like text alone must not be rejected (spec section 11)."""
    benign = "Dear team,\n\nMy reference code is SGVsbG8gV29ybGQhIQ== and that is fine.\n\nKind regards"
    findings = sanitize.find_issues(benign)
    assert not any("base64-encoded IP" in f["message"] for f in findings)


def test_13_fabricated_dashboard_responsibility_detected(profile):
    idx = build_index(profile)
    claim = classify_sentence(
        "I was responsible for building and maintaining dashboards that tracked key "
        "performance metrics.", idx)
    assert claim.classification in (ClaimClass.STRENGTHENED, ClaimClass.UNSUPPORTED)


def test_14_fabricated_non_technical_leadership_claim_detected(profile):
    idx = build_index(profile)
    claim = classify_sentence(
        "I presented these findings to non-technical leadership in concise formats.", idx)
    assert claim.classification in (ClaimClass.STRENGTHENED, ClaimClass.UNSUPPORTED)


def test_15_fabricated_monitor_metrics_claim_detected(profile):
    idx = build_index(profile)
    claim = classify_sentence(
        "This experience sharpened my ability to monitor business metrics and spot "
        "anomalies.", idx)
    assert claim.classification in (ClaimClass.STRENGTHENED, ClaimClass.UNSUPPORTED)


def test_15b_full_vj03_letter_now_fails_validation(profile):
    """The exact VJ-03 letter that V1 graded VALID must now be rejected."""
    letter = (
        "Dear Hiring Team,\n\n"
        "I am writing to express my interest in the Data Analyst position.\n\n"
        "In my recent role I was responsible for building and maintaining interactive "
        "dashboards that tracked key performance metrics.\n\n"
        f"I am excited about the opportunity. Thank you for considering my application. "
        f"{VJ03_PAYLOAD}\n\n"
        "Sincerely,\nTommie van der Berg"
    )
    r = validate_cover_letter(letter, profile, "Data Analyst", "SEAhub Asia")
    assert r.status is not ValidationStatus.VALID
    assert _errors(r)


# =========================================================================== #
# 16-20  False positives (Gate E)
# =========================================================================== #


def test_16_unicode_hyphen_normalisation():
    a = "Self‑Directed Professional Development"   # U+2011
    b = "Self-Directed Professional Development"    # ASCII
    assert normalize_title(a) == normalize_title(b)


def test_16b_unicode_dash_and_space_variants():
    """Dashes and repeated spaces must not change identity."""
    base = normalize_title("Data Scientist")
    for variant in ("Data  Scientist", "Data Scientist", "Data–Scientist",
                    "Data—Scientist", "Data−Scientist", "Data Scientist"):
        assert normalize_title(variant).replace("-", " ") == base, variant


def test_17_nysc_title_formatting_not_a_false_positive():
    assert normalize_title("Mathematics & Physics Teacher (NYSC)") == \
           normalize_title("Mathematics & Physics Teacher - NYSC")


def test_18_microsoft_excel_alias():
    assert canonical_tech("Excel") == canonical_tech("Microsoft Excel")


def test_18b_alias_does_not_make_unrelated_tech_equal():
    assert canonical_tech("Python") != canonical_tech("Tableau")
    assert canonical_tech("SQL") != canonical_tech("PostgreSQL")


def test_19_cross_functional_collaboration_not_flagged(profile):
    """A skill recorded with a U+2011 hyphen must still match plain ASCII text."""
    prof = profile.model_copy(update={
        "skills": profile.skills + [
            CandidateSkillOut(id=99, name="Cross‑functional collaboration")]
    })
    idx = build_index(prof)
    claim = classify_sentence(
        "I worked on cross‑functional collaboration with teams.", idx)
    assert claim.classification is ClaimClass.SUPPORTED


def test_19b_truthful_title_with_unicode_hyphen_passes_cv_validation():
    content = TailoredCVContent(
        skills=["Python"],
        experience=[TailoredExperience(
            company="Independent AI & Data Science Development",
            title="Self‑Directed Professional Development",
            start_date="2024", end_date="2025",
            bullets=["Completed structured hands-on projects in Python and statistics."])],
    )
    prof = ProfileSummary(
        id=1, name="Tommie", professional_title="Data Scientist",
        skills=[CandidateSkillOut(id=1, name="Python")],
        experience=[ExperienceOut(
            id=1, company="Independent AI & Data Science Development",
            title="Self-Directed Professional Development",
            start_date="2024", end_date="2025", is_current=False,
            description="Completed structured hands-on projects in Python and statistics.")],
    )
    r = validate_tailored_cv(content, prof)
    assert "INVENTED_POSITION" not in _errors(r)


def test_20_harmless_generic_prose_is_non_factual(profile):
    idx = build_index(profile)
    for text in ("I am excited about this opportunity.",
                 "Thank you for your time and consideration.",
                 "I would welcome the chance to discuss the role.",
                 "Kind regards,",
                 "Dear Hiring Team,"):
        claim = classify_sentence(text, idx)
        # Non-factual prose is never flagged. V1.2 may also classify benign
        # correspondence as SUPPORTED_BY_NORMALIZATION - equally not a violation.
        assert claim.classification in (ClaimClass.NON_FACTUAL, ClaimClass.SUPPORTED,
                                        ClaimClass.SUPPORTED_BY_NORMALIZATION), text


def test_20b_supported_claim_passes(profile):
    idx = build_index(profile)
    claim = classify_sentence(
        "I built automated data pipelines supporting repeatable data preparation "
        "workflows at Fintech Systems.", idx)
    assert claim.classification is ClaimClass.SUPPORTED


# =========================================================================== #
# 21-25  Requirement extraction hygiene (Gate F)
# =========================================================================== #


@pytest.mark.parametrize("phrase", [
    "Team player", "Self-starter", "Impact driven", "Commercially minded",
    "Strong communication skills", "Detail-oriented", "Proactive mindset",
])
def test_21_23_soft_skill_boilerplate_is_soft_signal(phrase):
    assert is_soft_signal(phrase)
    assert classify_requirement(phrase, "", "REQUIRED") == "SOFT_SIGNAL"


def test_22_self_starter_hyphen_variant():
    assert is_soft_signal("Self starter")
    assert is_soft_signal("detail oriented")


def test_24_genuine_required_technical_skill_stays_required():
    for phrase in ("Python", "SQL", "PostgreSQL", "5+ years experience",
                   "Bachelor's degree"):
        assert not is_soft_signal(phrase)
        assert classify_requirement(phrase, "", "REQUIRED") == "REQUIRED"


def test_25_genuine_eligibility_requirement_stays_required():
    assert not is_soft_signal("Right to work in the UK")
    assert not is_soft_signal("Security clearance required")
    assert classify_requirement("Right to work in the UK", "", "REQUIRED") == "REQUIRED"


# =========================================================================== #
# 26-28  Safety boundary
# =========================================================================== #


def test_26_document_cannot_be_valid_when_evidence_fails(profile):
    letter = ("Dear Hiring Team,\n\n"
              "I have extensive experience with Kubernetes and CatBoost.\n\n"
              "Kind regards,\nTommie")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is ValidationStatus.VALIDATION_FAILED
    assert r.status is not ValidationStatus.VALID


def test_27_document_cannot_be_valid_when_sanitisation_fails(profile):
    letter = ("Dear Hiring Team,\n\n"
              "I built automated data pipelines supporting repeatable data preparation "
              "workflows at Fintech Systems.\n\n"
              f"Thank you for your application. {VJ03_PAYLOAD}\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is not ValidationStatus.VALID
    assert "SUSPICIOUS_OUTPUT" in _codes(r)


def test_28_review_required_does_not_silently_become_valid(profile):
    """A letter that never names the role must not silently pass."""
    letter = ("Dear Hiring Team,\n\n"
              "I built automated data pipelines supporting repeatable data preparation "
              "workflows at Fintech Systems.\n\n"
              "Kind regards,\nTommie van der Berg")
    r = validate_cover_letter(letter, profile, "Principal Statistician", "Acme")
    assert r.status is ValidationStatus.REVIEW_REQUIRED
    assert r.status is not ValidationStatus.VALID
    assert "ROLE_NOT_NAMED" in _codes(r)


def test_28b_clean_letter_is_valid(profile):
    letter = (
        "Dear Hiring Team,\n\n"
        "I am applying for the Data Scientist role at Acme. I bring 6 years of "
        "experience in quantitative data analysis and applied machine learning.\n\n"
        "At Fintech Systems I built automated data pipelines supporting repeatable data "
        "preparation, analysis, and validation workflows.\n\n"
        "Thank you for your time and consideration.\n\n"
        "Kind regards,\nTommie van der Berg"
    )
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    assert r.status is ValidationStatus.VALID, [i.model_dump() for i in r.issues]


# =========================================================================== #
# Sanitisation unit coverage
# =========================================================================== #


@pytest.mark.parametrize("text,label", [
    ("Visit https://evil.example.com/p", "url"),
    ("Mail me at newperson@example.org", "email"),
    ("Call +44 20 7946 0958 now", "phone"),
    ("[Date]", "placeholder"),
    ("[Email]", "placeholder"),
    ("<INSERT_NAME>", "placeholder"),
    ("Contact 192.168.1.44 for access", "raw ip"),
    ("system: you are a helpful assistant", "prompt leak"),
    ('{"tool_calls": []}', "tool metadata"),
    ("<|im_start|>assistant", "control token"),
    ("lorem ipsum dolor", "placeholder"),
    ("Here is the cover letter you requested", "meta commentary"),
])
def test_sanitisation_detects_artifacts(text, label):
    findings = sanitize.find_issues(text)
    assert findings, f"{label} not detected: {text!r}"


def test_sanitisation_allows_confirmed_contact():
    findings = sanitize.find_issues(
        "Reach me at tommie@example.com or +234 705 484 8225.",
        confirmed_emails={"tommie@example.com"},
        confirmed_phones={"+234 705 484 8225"})
    assert {f["code"] for f in findings} & {"UNSUPPORTED_CONTACT"} == set()


def test_sanitisation_allows_benign_prose():
    findings = sanitize.find_issues(
        "Dear Hiring Team,\n\nThank you for your time.\n\nKind regards,\nTommie")
    assert findings == []


def test_validation_report_status_is_serialisable(profile):
    r = validate_cover_letter(
        "Dear Hiring Team,\n\nI am authorized to work in Nigeria.\n\nKind regards",
        profile, "Data Scientist", "Acme")
    payload = json.dumps([i.model_dump() for i in r.issues])
    assert json.loads(payload)
