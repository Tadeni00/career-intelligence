"""Regression tests for job-relevant experience selection in cover letters.

The defect: ``analyze_cv_for_job`` marked an experience relevant when it shared
a single token with the job *title*. The title "Data Analyst" contributes the
token "data", which on the real profile matched seven of nine roles -- while the
candidate held none of that posting's skills. Relevance was therefore neither
evidence-anchored nor ranked, and selection followed profile order alone, so an
unrelated more recent role could displace a clearly relevant earlier one.

The correction adds ``_ranked_experience``: experience is scored on the posting's
own extracted requirements, generic words are removed via the evidence module's
existing GENERIC_TOKENS list, a skill named only in the posting contributes
nothing (it is not evidence the candidate has it), and ties fall back to profile
position so ordering is reproducible.

These tests drive the real selection and the real generator. No network, no
database, no AI provider configuration.
"""

from __future__ import annotations

import re

from app.ai.offline_provider import OfflineProvider
from app.schemas import ProfileSummary
from app.services.validation import validate_cover_letter

ML_JD = """\
Machine Learning Engineer.

Required: Machine Learning, Python, and 5+ years of experience building models.
You will deploy and evaluate models in production.
"""

GENERIC_JD = """\
Data Engineer.

Required: data engineer skills and 3+ years of experience working with a team.
You will support the business and work across the product.
"""

RARE_SKILL_JD = """\
Platform Engineer.

Required: Kubernetes, Terraform, and 5+ years of experience running infrastructure.
"""


def _exp(cid, company, title, description):
    return {
        "id": cid,
        "company": company,
        "title": title,
        "start_date": "2021",
        "end_date": None,
        "is_current": True,
        "description": description,
    }


def _profile(experiences, skills):
    return ProfileSummary(
        id=1,
        name="Test Candidate",
        professional_title="Machine Learning Engineer",
        location="Lagos, Nigeria",
        years_of_experience=6,
        skills=[{"id": i + 1, "name": s} for i, s in enumerate(skills)],
        experience=experiences,
    )


# First entry is the most recent; the old selector walked this order blindly.
MIXED_PROFILE = _profile(
    experiences=[
        # 0: recent, but only generic vocabulary.
        _exp(1, "Generic Corp", "Data Support Specialist",
             "Worked with the engineering team to support the business and "
             "process data for reporting across the product."),
        # 1: clearly relevant, but earlier in the profile.
        _exp(2, "Relevant Labs", "Machine Learning Engineer",
             "Built and deployed machine learning models for fraud detection, "
             "including Python pipelines and model evaluation."),
        # 2: relevant, weaker wording.
        _exp(3, "Side Project Ltd", "Data Scientist",
             "Applied machine learning to a small classification dataset."),
    ],
    skills=["Python", "Machine Learning"],
)

TIE_PROFILE = _profile(
    experiences=[
        _exp(1, "First Co", "Data Scientist", "Used machine learning on dataset one."),
        _exp(2, "Second Co", "Data Scientist", "Used machine learning on dataset two."),
        _exp(3, "Third Co", "Data Scientist", "Used machine learning on dataset three."),
    ],
    skills=["Machine Learning"],
)

DUPLICATE_PROFILE = _profile(
    experiences=[
        _exp(1, "Analytics Ltd", "Data Scientist",
             "Built data pipelines in Python and SQL for production reporting."),
        _exp(2, "Analytics Ltd (contract)", "Data Scientist",
             "Built data pipelines in Python and SQL for production reporting."),
        _exp(3, "Other Ltd", "Analyst",
             "Delivered machine learning models in production with Python."),
    ],
    skills=["Python", "SQL", "Machine Learning"],
)

NO_EVIDENCE_PROFILE = _profile(
    experiences=[_exp(1, "Unrelated Co", "Office Manager",
                      "Managed administration and office supplies.")],
    skills=[],
)


def _letter_employers(profile: ProfileSummary, jd: str, title: str) -> list[str]:
    """Employers the generated letter actually credits, in order.

    This goes through the real ``generate_cover_letter`` path rather than the
    ranking helper, so a regression that stops using the selector is caught.
    """
    letter = OfflineProvider().generate_cover_letter(
        profile=profile, job_description=jd, job_title=title, company="Example Corp"
    )
    return [m.strip() for m in re.findall(r"\bAt\s+(.+?)\s+I\s", letter)]


def _claims(text: str, term: str) -> bool:
    """True when the body asserts the candidate possesses/used ``term``.

    Heuristic: looks for a first-person possession or usage verb immediately
    governing the term. It cannot see every way a claim could be phrased.
    """
    pattern = (
        r"\bI (?:bring|use|used|have|has|worked|built|developed|deployed|"
        r"maintain|maintained|hold|holds)\b[^.]{0,60}\b" + re.escape(term) + r"\b"
    )
    return bool(re.search(pattern, text, re.I))


def _evidence_text(letter: str) -> str:
    """Only the paragraphs that assert completed work.

    The greeting, the opening line, the gap disclosure (which legitimately
    names skills the candidate does *not* have), the closing and the sign-off
    are excluded.
    """
    keep = []
    for para in letter.split("\n\n"):
        if "thinner on" in para:
            continue
        if para.startswith(("Dear ", "I am applying", "Kind regards")):
            continue
        if "welcome the opportunity" in para or "Thank you for your time" in para:
            continue
        keep.append(para)
    return " ".join(keep)


# ------------------------------------------ 1. specific beats generic-token overlap


def test_specific_relevance_outranks_generic_token_overlap() -> None:
    """Case 1: a directly relevant role wins over one matching only stopwords."""
    credited = _letter_employers(MIXED_PROFILE, ML_JD, "Machine Learning Engineer")
    assert credited[0] == "Relevant Labs", credited
    assert "Generic Corp" not in credited, credited


def test_generic_posting_does_not_manufacture_relevance() -> None:
    """Case 1: a title made of generic words must not make anything relevant."""
    provider = OfflineProvider()
    profile = MIXED_PROFILE
    analysis = provider.analyze_cv_for_job(profile, GENERIC_JD, "Data Engineer", "Example Corp")
    terms = provider._job_requirement_terms(GENERIC_JD, "Data Engineer")

    # Nothing generic survived into the requirement vocabulary.
    for generic in ("data", "engineer", "team", "support", "business", "product"):
        assert generic not in terms, (generic, sorted(terms))


# ------------------------ 2. job-description skills are not candidate evidence


def test_job_only_skill_does_not_become_candidate_evidence() -> None:
    """Case 2: Kubernetes is in the posting, not on the profile.

    The posting's skills may still be *named in the gap disclosure* - that is
    the honest behaviour - but must never be asserted as something the candidate
    brings or has used.
    """
    provider = OfflineProvider()
    profile = _profile(
        experiences=[_exp(1, "Infra Co", "Platform Engineer",
                          "Ran infrastructure and deployment tooling in Python.")],
        skills=["Python"],
    )
    analysis = provider.analyze_cv_for_job(profile, RARE_SKILL_JD,
                                           "Platform Engineer", "Example Corp")
    assert "Kubernetes" not in analysis.relevant_skills
    assert "Terraform" not in analysis.relevant_skills

    letter = provider.generate_cover_letter(
        profile=profile, job_description=RARE_SKILL_JD,
        job_title="Platform Engineer", company="Example Corp",
    )
    body = _evidence_text(letter)
    for absent in ("Kubernetes", "Terraform"):
        assert absent not in body, body
        assert not _claims(body, absent), body


def test_confirmed_skill_does_contribute_to_relevance() -> None:
    """Case 2: a skill the candidate holds and the job wants counts."""
    provider = OfflineProvider()
    analysis = provider.analyze_cv_for_job(MIXED_PROFILE, ML_JD,
                                           "Machine Learning Engineer", "Example Corp")
    assert "Machine Learning" in analysis.relevant_skills


# ------------------ 3. relevance beats recency; 4. ties are deterministic


def test_unrelated_recent_experience_does_not_displace_relevant_earlier() -> None:
    """Case 3: Generic Corp is first in the profile but must not be credited."""
    credited = _letter_employers(MIXED_PROFILE, ML_JD, "Machine Learning Engineer")
    assert credited[0] == "Relevant Labs", credited
    assert "Generic Corp" not in credited, credited


def test_ties_are_resolved_deterministically_by_profile_order() -> None:
    """Case 4: equal scores keep profile order, repeatably."""
    first = _letter_employers(TIE_PROFILE, ML_JD, "Machine Learning Engineer")
    assert first == ["First Co", "Second Co", "Third Co"], first
    for _ in range(4):
        assert _letter_employers(TIE_PROFILE, ML_JD, "Machine Learning Engineer") == first


# ------------------------------------- 5. duplicate descriptions not both selected


def test_substantially_overlapping_evidence_is_not_needless() -> None:
    """Case 5: two records describing one body of work yield one entry."""
    credited = _letter_employers(DUPLICATE_PROFILE, ML_JD, "Machine Learning Engineer")
    # The contract record duplicates the original description and is dropped.
    assert "Analytics Ltd (contract)" not in credited, credited
    assert credited.count("Analytics Ltd") == 1, credited
    # The stronger, distinct record is preferred.
    assert credited[0] == "Other Ltd", credited


# ------------------------------------ 6. no evidence -> no invented claims


def test_candidate_without_relevant_experience_gets_no_body_claims() -> None:
    """Case 6: an unrelated profile yields an honest, short letter.

    The role name may appear (the letter is addressed to it) and the posting's
    skills may appear in the gap disclosure, but no experience sentence may
    claim machine-learning work the profile never records.
    """
    provider = OfflineProvider()
    letter = provider.generate_cover_letter(
        profile=NO_EVIDENCE_PROFILE, job_description=ML_JD,
        job_title="Machine Learning Engineer", company="Example Corp",
    )
    body = _evidence_text(letter)
    assert not _claims(body, "machine learning"), body
    assert "Python" not in body, body
    assert "I am applying for the Machine Learning Engineer role." in letter
    assert "Dear Example Corp hiring team," in letter
    # The only body content is the one confirmed experience on record.
    assert "managed administration and office supplies" in body, body


# --------------------------------- 7. safeguards still work end to end


def test_generated_letter_remains_evidence_supported() -> None:
    """Case 7: real generation + validation for a mixed profile."""
    provider = OfflineProvider()
    letter = provider.generate_cover_letter(
        profile=MIXED_PROFILE, job_description=ML_JD,
        job_title="Machine Learning Engineer", company="Example Corp",
    )
    report = validate_cover_letter(
        letter, MIXED_PROFILE, "Machine Learning Engineer", "Example Corp",
        job_description=ML_JD,
    )
    assert report.status.value == "VALID", [(i.code, i.detail) for i in report.issues]


def test_selection_does_not_weaken_unsupported_claim_detection() -> None:
    """Case 7: an invented employer is still rejected after the change."""
    provider = OfflineProvider()
    letter = provider.generate_cover_letter(
        profile=MIXED_PROFILE, job_description=ML_JD,
        job_title="Machine Learning Engineer", company="Example Corp",
    )
    tampered = letter.replace(
        "Kind regards,",
        "At Globex Corporation I owned the platform roadmap.\n\nKind regards,",
    )
    issues = validate_cover_letter(
        tampered, MIXED_PROFILE, "Machine Learning Engineer", "Example Corp",
        job_description=ML_JD,
    ).issues
    assert any(i.code == "INVENTED_EMPLOYER" for i in issues), [i.code for i in issues]


def test_experience_order_is_unchanged_by_the_analysis_sharing() -> None:
    """The shared analysis used by CV tailoring is not re-ranked.

    ``analyze_cv_for_job`` is also consumed by tailored-CV generation, so the
    correction is deliberately confined to the cover-letter selector. The shared
    field must still be a subsequence of profile order.
    """
    provider = OfflineProvider()
    analysis = provider.analyze_cv_for_job(MIXED_PROFILE, ML_JD,
                                           "Machine Learning Engineer", "Example Corp")
    profile_order = [
        f"{e.title} @ {e.company}" for e in MIXED_PROFILE.experience
    ]
    relevant = list(analysis.relevant_experience)

    positions = [profile_order.index(r) for r in relevant]
    assert positions == sorted(positions), (relevant, profile_order)
