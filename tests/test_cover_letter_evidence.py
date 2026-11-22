"""Regression tests for evidence-grounded cover-letter generation.

The defect: ``OfflineProvider.generate_cover_letter`` appended a fixed sentence
to the opening paragraph regardless of the candidate::

    " The work in your description — building and evaluating production-grade
    models — is the work I have spent my career doing, and it is the part I
    most want to keep doing."

That asserts a universal career-experience claim. No profile can evidence it, so
``validate_cover_letter`` classified the sentence as ``PLAUSIBLE_BUT_UNVERIFIED``
(``CLAIM_UNVERIFIED``, severity LOW) and every generated letter was at best
``REVIEW_REQUIRED``. Some profiles with richer prose were also tripping
``CLAIM_STRENGTHENING`` on the same sentence.

The fix replaces it with a sentence naming only skills that are simultaneously
(a) on the confirmed profile and (b) requested by the job, taken from
``analysis.relevant_skills``. When that intersection is empty the sentence is
omitted rather than replaced with an invention.

These tests drive the real generator and the real validator. No network, no
database, no AI provider configuration. They do not weaken or bypass validation.
"""

from __future__ import annotations

from app.ai.offline_provider import OfflineProvider
from app.services.evidence import classify_sentence
from app.services.validation import (
    _extra_evidence,
    _sentences,
    build_index,
    tokens,
    validate_cover_letter,
)
from app.schemas import ProfileSummary

# The exact fixed text that must no longer appear.
UNIVERSAL_CLAIM_FRAGMENT = "is the work I have spent my career doing"

PYTHON_SQL_JD = """\
Data Scientist at Example Analytics.

Required: Python, SQL, and 5+ years of experience in production machine learning.
You will build and evaluate statistical models and data pipelines.
Bachelor's degree in a related field is required.
"""

UNRELATED_JD = """\
Marine Biologist at Example Ocean Institute.

Required: scuba diving, coral reef survey methods, and 3+ years of fieldwork.
You will catalogue deep-sea biodiversity and publish survey findings.
"""


def _rich_profile() -> ProfileSummary:
    return ProfileSummary(
        id=1,
        name="Test Candidate",
        professional_title="Data Scientist",
        location="Lagos, Nigeria",
        years_of_experience=6,
        summary="Data professional focused on quantitative analysis.",
        skills=[
            {"id": 1, "name": "Python"},
            {"id": 2, "name": "SQL"},
            {"id": 3, "name": "Machine Learning"},
        ],
        experience=[
            {
                "id": 1,
                "company": "Example Analytics",
                "title": "Data Scientist",
                "start_date": "2021",
                "end_date": None,
                "is_current": True,
                "description": "Built data pipelines in Python and SQL for production reporting.",
            }
        ],
    )


def _limited_profile() -> ProfileSummary:
    """A candidate with almost nothing confirmed: no experience, no skills."""
    return ProfileSummary(
        id=2,
        name="Limited Candidate",
        professional_title=None,
        location=None,
        years_of_experience=None,
        summary=None,
        skills=[],
        experience=[],
    )


def _letter(profile: ProfileSummary, jd: str, title: str, company: str | None) -> str:
    return OfflineProvider().generate_cover_letter(
        profile=profile, job_description=jd, job_title=title, company=company
    )


def _validate(letter: str, profile: ProfileSummary, title: str, company: str | None, jd: str):
    return validate_cover_letter(letter, profile, title, company, job_description=jd)


# ---------------------------------------------- 2. the unsupported claim is gone


def test_universal_career_claim_never_appears() -> None:
    """Requirement 2: no universal experience statement, for any input."""
    for profile in (_rich_profile(), _limited_profile()):
        for jd in (PYTHON_SQL_JD, UNRELATED_JD):
            letter = _letter(profile, jd, "Data Scientist", "Example Analytics")
            assert UNIVERSAL_CLAIM_FRAGMENT not in letter, letter[:300]
            assert "The work in your description" not in letter


# ------------------------------- 1. relevant confirmed experience is reflected


def test_relevant_confirmed_experience_is_reflected() -> None:
    """Requirement 1: evidenced skills are named, and only evidenced ones.

    Since Task 8 the skills are carried by the experience sentence itself rather
    than by a bare bridge sentence ("I would bring Machine Learning."), which was
    both thin and ungrammatical when a single skill was named.
    """
    profile = _rich_profile()
    letter = _letter(profile, PYTHON_SQL_JD, "Data Scientist", "Example Analytics")

    confirmed = {s.name for s in profile.skills}
    body = "\n".join(letter.splitlines()[3:-2])
    for skill in confirmed:
        if skill in body:
            assert skill in confirmed
    assert "Python" in body and "SQL" in body, body
    assert "I would bring" not in letter, letter


def test_every_generated_sentence_is_evidence_supported() -> None:
    """Requirement 1/5: no sentence in the letter trips the validator."""
    profile = _rich_profile()
    jd = PYTHON_SQL_JD
    letter = _letter(profile, jd, "Data Scientist", "Example Analytics")
    idx = build_index(profile, _extra_evidence(profile))
    job_terms = tokens(jd) | tokens("Data Scientist") | tokens("Example Analytics")

    accepted = {"SUPPORTED", "NON_FACTUAL", "SUPPORTED_BY_NORMALIZATION"}
    for sentence in _sentences(letter):
        claim = classify_sentence(sentence, idx, job_terms=job_terms)
        assert claim.classification.value in accepted, (
            f"unsupported sentence: {sentence!r} -> {claim.classification.value}"
        )


# --------------------- 3. limited evidence yields a conservative letter


def test_limited_profile_omits_the_claim_rather_than_inventing() -> None:
    """Requirement 3: nothing evidenced -> nothing claimed."""
    profile = _limited_profile()
    letter = _letter(profile, PYTHON_SQL_JD, "Data Scientist", "Example Analytics")

    assert "I would bring" not in letter
    # Still job-specific: it names the role and addresses the employer.
    assert "I am applying for the Data Scientist role." in letter
    assert "Dear Example Analytics hiring team," in letter


def test_limited_profile_invents_no_skills_or_history() -> None:
    """Requirement 3: no skills, employers or years invented.

    Job terms may still appear inside the honest gap disclosure ("my background
    is thinner on Python; SQL"), which is the opposite of a claim. What must
    never appear is the candidate *asserting* those skills or a history.
    """
    profile = _limited_profile()
    letter = _letter(profile, PYTHON_SQL_JD, "Data Scientist", "Example Analytics")

    assert "years of experience as" not in letter
    assert "At " not in letter, letter
    assert "I would bring" not in letter
    assert "I bring " not in letter


def test_limited_profile_letter_still_validates() -> None:
    """Requirement 3/5: a conservative letter is not punished for being short."""
    profile = _limited_profile()
    letter = _letter(profile, PYTHON_SQL_JD, "Data Scientist", "Example Analytics")
    report = _validate(letter, profile, "Data Scientist", "Example Analytics", PYTHON_SQL_JD)

    assert report.status.value == "VALID", [i.code for i in report.issues]


# --------------------------------- 4. unsupported claims are still detected


def test_unsupported_claims_elsewhere_are_still_detected() -> None:
    """Requirement 4: the fix did not make the validator permissive."""
    profile = _rich_profile()
    honest = _letter(profile, PYTHON_SQL_JD, "Data Scientist", "Example Analytics")
    assert _validate(honest, profile, "Data Scientist", "Example Analytics",
                     PYTHON_SQL_JD).status.value == "VALID"

    # Inject an employer the candidate never worked for.
    tampered = honest.replace(
        "Kind regards,",
        "At Globex Corporation I owned the platform roadmap.\n\nKind regards,",
    )
    issues = _validate(tampered, profile, "Data Scientist", "Example Analytics",
                       PYTHON_SQL_JD).issues
    assert any(i.code == "INVENTED_EMPLOYER" for i in issues), [i.code for i in issues]


def test_unevidenced_technology_claim_is_still_detected() -> None:
    """Requirement 4: fabrication signals still hard-fail.

    No intensifier is used, because "deep" is caught earlier as a scope
    escalation and would mask the technology check being exercised here.
    """
    profile = _rich_profile()
    letter = (
        "Dear Example Analytics hiring team,\n\n"
        "I am applying for the Data Scientist role.\n\n"
        "I would bring Python and SQL, along with Kubernetes and Terraform.\n\n"
        "Kind regards,\nTest Candidate"
    )
    issues = _validate(letter, profile, "Data Scientist", "Example Analytics",
                       PYTHON_SQL_JD).issues
    assert any(i.code == "UNSUPPORTED_CLAIM" for i in issues), [i.code for i in issues]
    assert any("Kubernetes" in str(i.detail) or "Terraform" in str(i.detail)
               for i in issues), [(i.code, i.detail) for i in issues]


# ------------------------------------ 5. evidenced letters keep their claims


def test_supported_claims_are_retained() -> None:
    """Requirement 5: the replacement is additive, not a deletion."""
    profile = _rich_profile()
    letter = _letter(profile, PYTHON_SQL_JD, "Data Scientist", "Example Analytics")

    assert "I am applying for the Data Scientist role." in letter
    assert "Dear Example Analytics hiring team," in letter
    assert "Example Analytics" in letter          # confirmed employer in the body
    assert "At Example Analytics I " in letter     # evidenced experience stated
    assert "Python" in letter and "SQL" in letter  # evidenced skills
    assert "Kind regards," in letter


def test_validation_status_is_valid_for_a_well_evidenced_letter() -> None:
    """Requirement 5: appropriate status, earned by evidence not by leniency."""
    profile = _rich_profile()
    letter = _letter(profile, PYTHON_SQL_JD, "Data Scientist", "Example Analytics")
    report = _validate(letter, profile, "Data Scientist", "Example Analytics", PYTHON_SQL_JD)

    assert report.status.value == "VALID", [(i.code, i.detail) for i in report.issues]
    assert report.issues == []


def test_relevant_skills_only_come_from_the_confirmed_profile() -> None:
    """The replacement must never introduce a skill the profile lacks."""
    profile = _rich_profile()
    letter = _letter(profile, UNRELATED_JD, "Marine Biologist", "Example Ocean Institute")

    # This job asks for scuba diving and coral survey work; the profile has none
    # of it, so the bridge sentence must be absent rather than invented, and no
    # foreign technology may be claimed.
    assert "I would bring" not in letter
    for foreign in ("scuba", "coral"):
        assert foreign.lower() not in letter.lower()
