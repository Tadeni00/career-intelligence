"""Regression tests for cover-letter prose quality.

Task 7 removed an unevidenceable universal career claim. Task 8 addresses the
resulting and pre-existing prose defects:

* "I have also provide technical guidance ..." -- ungrammatical, because the
  generator prefixed a subject-less clause that was an infinitive.
* "Concretely, I would bring: Undertook structured hands-on development ..."
  -- a fragment introduced by a colon.
* The same description clause appeared twice, once as an experience sentence and
  again in the "Concretely" paragraph.
* "I would bring Machine Learning." -- a bare skill with no activity attached.

These tests drive the real generator and the real validator.

Heuristic checks are marked as such. Sentence-splitting, "looks like a complete
sentence", and duplication detection here are structural approximations, not a
grammar evaluator: they cannot detect every awkward construction, and a passing
run does not mean a letter would read well to a human recruiter.
"""

from __future__ import annotations

import re

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

PYTHON_SQL_JD = """\
Data Scientist at Example Analytics.

Required: Python, SQL, and 5+ years of experience in production machine learning.
You will build and evaluate statistical models and data pipelines.
Bachelor's degree in a related field is required.
"""

# Clause forms taken from the shape of real recorded descriptions: past tense,
# infinitive, and an opener that is not a verb phrase at all.
MULTI_CLAUSE_PROFILE = ProfileSummary(
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
            "description": (
                "Built data pipelines in Python and SQL for production reporting. "
                "Applied statistical modelling techniques to customer segmentation. "
                "The team met weekly to review model performance."
            ),
        },
        {
            "id": 2,
            "company": "Example Labs",
            "title": "Analyst",
            "start_date": "2019",
            "end_date": "2021",
            "is_current": False,
            "description": "Collected and validated field data using SQL and Python.",
        },
    ],
    projects=[
        {
            "id": 1,
            "name": "Fraud Pipeline",
            "description": "Designed an end-to-end detection service in Python and SQL.",
            "technologies": ["Python"],
        }
    ],
)

LIMITED_PROFILE = ProfileSummary(
    id=2,
    name="Limited Candidate",
    professional_title=None,
    location=None,
    years_of_experience=None,
    summary=None,
    skills=[],
    experience=[],
    projects=[],
)


def _letter(profile: ProfileSummary, jd: str = PYTHON_SQL_JD,
            title: str = "Data Scientist", company: str | None = "Example Analytics") -> str:
    return OfflineProvider().generate_cover_letter(
        profile=profile, job_description=jd, job_title=title, company=company
    )


def _body_sentences(letter: str) -> list[str]:
    """Sentences that are neither the sign-off boilerplate nor the greeting."""
    body = letter.split("\n\n")
    return _sentences(" ".join(body[2:-2]))


def _normalise(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


# ------------------------------------------------ 1. the reported defects are gone


def test_reported_grammar_defects_do_not_appear() -> None:
    """Case 1: neither the ungrammatical nor the fragment construction."""
    letter = _letter(MULTI_CLAUSE_PROFILE)

    # "I have also provide ..." - subject-less clause behind an auxiliary.
    assert not re.search(r"\bI have also (provide|built|worked|developed|led)\b", letter), letter
    # "I also <infinitive>" is fine; "I have also <infinitive>" is not.
    assert "I have also" not in letter, letter
    # A colon introducing a raw clause fragment.
    assert "I would bring:" not in letter, letter
    assert "Concretely" not in letter, letter


def test_bare_skill_filler_is_not_emitted() -> None:
    """Case 1/3: no standalone "I would bring <skill>." bridge sentence."""
    for profile in (MULTI_CLAUSE_PROFILE, LIMITED_PROFILE):
        letter = _letter(profile)
        assert "I would bring" not in letter, letter


# ------------------------------------ 2. complete, natural sentences for evidence


def test_experience_evidence_becomes_complete_sentences() -> None:
    """Case 2: evidence clauses carry a subject and a verb."""
    letter = _letter(MULTI_CLAUSE_PROFILE)
    body = _body_sentences(letter)

    assert body, "expected evidenced body sentences"
    for sentence in body:
        # Heuristic completeness check: a capitalised word and a finite verb
        # (past tense, or an infinitive after "I"). Not a grammar checker.
        assert sentence[:1].isupper(), f"not capitalised: {sentence!r}"
        assert not sentence.endswith(":"), f"dangling colon: {sentence!r}"
        assert sentence.endswith("."), f"no terminator: {sentence!r}"
        assert not re.search(r"\b(I|we)\b\s*$", sentence), f"no verb: {sentence!r}"


def test_employer_is_stated_before_its_continuation_clause() -> None:
    """Case 2: the employer is named once, then the clause continues in context."""
    letter = _letter(MULTI_CLAUSE_PROFILE)
    assert "At Example Analytics I built data pipelines" in letter, letter
    assert letter.count("At Example Analytics I ") == 1, (
        "the employer must not be re-stated for its own continuation clause"
    )


def test_non_verb_clause_opener_is_skipped_not_forced() -> None:
    """Case 2: a clause that cannot take a subject is omitted, not mangled."""
    letter = _letter(MULTI_CLAUSE_PROFILE)
    # "The team met weekly ..." has no subject the candidate can adopt.
    assert "The team met weekly" not in letter, letter


# ------------------------------------------- 3. conservative letter for thin profiles


def test_limited_profile_gets_no_filler_and_no_invention() -> None:
    """Case 3: short and honest beats padded."""
    letter = _letter(LIMITED_PROFILE)

    assert "I would bring" not in letter
    assert "At " not in letter
    assert "I bring " not in letter
    assert "I am applying for the Data Scientist role." in letter
    assert "Dear Example Analytics hiring team," in letter
    assert "Kind regards,\nLimited Candidate" in letter


def test_limited_profile_letter_is_validated_not_assumed() -> None:
    """Case 3/5: status comes from the validator."""
    letter = _letter(LIMITED_PROFILE)
    report = validate_cover_letter(letter, LIMITED_PROFILE, "Data Scientist",
                                  "Example Analytics", job_description=PYTHON_SQL_JD)
    assert report.status.value == "VALID", [(i.code, i.detail) for i in report.issues]


# --------------------------------------------- 4. safeguards still detect abuse


def test_invented_employer_is_still_detected() -> None:
    """Case 4: employer fabrication still fails."""
    letter = _letter(MULTI_CLAUSE_PROFILE)
    tampered = letter.replace(
        "Kind regards,",
        "At Globex Corporation I owned the platform roadmap.\n\nKind regards,",
    )
    issues = validate_cover_letter(tampered, MULTI_CLAUSE_PROFILE, "Data Scientist",
                                  "Example Analytics", job_description=PYTHON_SQL_JD).issues
    assert any(i.code == "INVENTED_EMPLOYER" for i in issues), [i.code for i in issues]


def test_invented_skill_is_still_detected() -> None:
    """Case 4: unevidenced technology still fails."""
    letter = (
        "Dear Example Analytics hiring team,\n\n"
        "I am applying for the Data Scientist role.\n\n"
        "I built pipelines in Python and SQL, along with Kubernetes and Terraform.\n\n"
        "Kind regards,\nTest Candidate"
    )
    issues = validate_cover_letter(letter, MULTI_CLAUSE_PROFILE, "Data Scientist",
                                  "Example Analytics", job_description=PYTHON_SQL_JD).issues
    assert any(i.code == "UNSUPPORTED_CLAIM" for i in issues), [i.code for i in issues]


def test_invented_achievement_is_still_detected() -> None:
    """Case 4: unevidenced metrics still fail."""
    letter = (
        "Dear Example Analytics hiring team,\n\n"
        "I am applying for the Data Scientist role.\n\n"
        "I reduced model error by 87% and led a team of 40 engineers.\n\n"
        "Kind regards,\nTest Candidate"
    )
    report = validate_cover_letter(letter, MULTI_CLAUSE_PROFILE, "Data Scientist",
                                   "Example Analytics", job_description=PYTHON_SQL_JD)
    assert report.status.value != "VALID", [(i.code, i.detail) for i in report.issues]


# --------------------------------------------------- 5. gap disclosure stays honest


def test_gap_disclosure_does_not_claim_the_missing_skill() -> None:
    """Case 5: naming a gap is not possessing it."""
    letter = _letter(LIMITED_PROFILE)
    gap_paragraph = [p for p in letter.split("\n\n") if "thinner on" in p]
    assert gap_paragraph, letter

    paragraph = gap_paragraph[0]
    assert "Python" in paragraph and "SQL" in paragraph
    # The disclosure must not read as a claim of those skills.
    assert not re.search(r"\bI (bring|use|have|worked with|built)\b[^\n]*\b(Python|SQL)\b",
                         paragraph), paragraph
    assert "rather flag that than overstate it" in paragraph


# ------------------------------------------------------- 6. no duplicated evidence


def test_no_clause_is_repeated_across_the_letter() -> None:
    """Case 6: the same recorded clause appears at most once.

    Heuristic: compares normalised sentence text. It cannot detect semantic
    repetition expressed in different words.
    """
    letter = _letter(MULTI_CLAUSE_PROFILE)
    seen: dict[str, str] = {}
    for sentence in _sentences(letter):
        key = _normalise(sentence)
        if key in seen:
            raise AssertionError(
                f"duplicated sentence {sentence!r} (first seen as {seen[key]!r})"
            )
        seen[key] = sentence


def test_evidence_clause_is_not_restated_in_a_second_paragraph() -> None:
    """Case 6: the specific defect - a clause used as body and as emphasis."""
    letter = _letter(MULTI_CLAUSE_PROFILE)
    fragments = [
        _normalise(s)
        for s in _body_sentences(letter)
        if "data pipelines in Python and SQL" in s
    ]
    assert len(fragments) == 1, f"evidence restated {len(fragments)} times: {letter}"


# --------------------------------------- 7. existing supported details stay accurate


def test_confirmed_facts_are_reported_verbatim() -> None:
    """Case 7: nothing the profile records is altered or invented."""
    letter = _letter(MULTI_CLAUSE_PROFILE)

    assert "Example Analytics" in letter
    assert "Example Labs" in letter
    assert "I bring 6 years of experience as Data Scientist." in letter
    assert "Kind regards,\nTest Candidate" in letter
    # No employer or skill appears that is not on the profile.
    for company in ("Globex", "Initech", "Acme"):
        assert company not in letter


def test_generated_letter_remains_fully_evidence_supported() -> None:
    """Case 7: no sentence is merely tolerated by the coverage heuristic."""
    profile = MULTI_CLAUSE_PROFILE
    letter = _letter(profile)
    idx = build_index(profile, _extra_evidence(profile))
    job_terms = tokens(PYTHON_SQL_JD) | tokens("Data Scientist") | tokens("Example Analytics")

    accepted = {"SUPPORTED", "NON_FACTUAL", "SUPPORTED_BY_NORMALIZATION"}
    for sentence in _sentences(letter):
        claim = classify_sentence(sentence, idx, job_terms=job_terms)
        assert claim.classification.value in accepted, (
            f"unsupported: {sentence!r} -> {claim.classification.value}"
        )


def test_project_is_not_attributed_to_an_employer() -> None:
    """Projects must never be presented as employer work."""
    letter = _letter(MULTI_CLAUSE_PROFILE)
    if "Fraud Pipeline" in letter:
        assert not re.search(r"At \w+[^.]*Fraud Pipeline", letter), letter
        assert "In the Fraud Pipeline project, I " in letter, letter
