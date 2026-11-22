"""Regression tests for live discovery failures observed 2026-10-15.

A real JSearch response carries ~200-character base64 provider ids. Those used
to exceed ``jobs.source_id`` (VARCHAR(128)) at INSERT, and the failed flush
then poisoned the session, so every later job in the same request failed too
and the whole search returned ``total: 0`` despite the provider answering.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest
from app.db.session import SessionLocal
from app.models import Candidate, CandidateSkill, Education, Experience, Job, Skill
from app.services.job_discovery import JobDiscoveryService
from app.services.jsearch import JSearchJob

LONG_PROVIDER_ID = "U0VKUEM" + "x" * 200  # ~207 chars, shaped like a live id

GOOD_DESCRIPTION = (
    "We are looking for a Senior Data Scientist with Python and SQL experience. "
    "Required: 5+ years of experience in machine learning."
)


@pytest.fixture
def db_session():
    """Provide a database session for testing."""
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def discovery_candidate(db_session) -> Candidate:
    """Candidate with enough evidence for matching to score."""
    db_session.add_all([
        Skill(id=1, name="Python", category="Programming"),
        Skill(id=2, name="SQL", category="Data"),
    ])
    db_session.flush()
    candidate = Candidate(
        id=1,
        name="Test Candidate",
        professional_title="Data Scientist",
        email="test@example.com",
        location="Lagos, Nigeria",
        years_of_experience=6.0,
        skills=[
            CandidateSkill(candidate_id=1, skill_id=1, proficiency="Expert", years_experience=5.0),
            CandidateSkill(candidate_id=1, skill_id=2, proficiency="Advanced", years_experience=4.0),
        ],
        experience=[
            Experience(
                company="TechCorp",
                title="Senior Data Scientist",
                start_date="2020-01",
                end_date=None,
                description="Built ML models using Python and SQL.",
                is_current=True,
            ),
        ],
        education=[
            Education(institution="University of Lagos", degree="MSc Computer Science"),
        ],
    )
    db_session.add(candidate)
    db_session.commit()
    return candidate


def _job(provider_job_id: str, title: str) -> JSearchJob:
    return JSearchJob(
        provider_job_id=provider_job_id,
        title=title,
        company="TechCorp Nigeria",
        location="Lagos, Nigeria",
        description=GOOD_DESCRIPTION,
        apply_url="https://jsearch.example.com/apply/123",
        posted_at=datetime(2024, 1, 15, 10, 0, 0),
        salary_min=80000.0,
        salary_max=120000.0,
        salary_currency="USD",
        employment_type="FULLTIME",
        remote_status="REMOTE",
    )


def test_long_provider_id_persists_in_full(db_session, discovery_candidate):
    """A ~200-char provider id must round-trip, not truncate at INSERT."""
    db_session.add(discovery_candidate)
    db_session.commit()

    service = JobDiscoveryService(db_session)
    with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
        mock_search.return_value = [_job(LONG_PROVIDER_ID, "Senior Data Scientist")]

        results = service.discover_jobs(candidate_id=1, query="data", country="ng")

    assert len(results) == 1
    stored = db_session.query(Job).filter_by(source_id=LONG_PROVIDER_ID).one()
    assert stored.external_id == f"jsearch:{LONG_PROVIDER_ID}"


def test_one_bad_job_does_not_zero_the_search(db_session, discovery_candidate):
    """A job that fails to persist is skipped; later jobs still process.

    The failing job is first on purpose: before the per-job rollback, its
    failed flush poisoned the session and the good job failed too.
    """
    db_session.add(discovery_candidate)
    db_session.commit()

    service = JobDiscoveryService(db_session)
    with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
        mock_search.return_value = [
            _job("bad_job_1", "T" * 300),  # exceeds jobs.title VARCHAR(255)
            _job(LONG_PROVIDER_ID, "Senior Data Scientist"),
        ]

        results = service.discover_jobs(candidate_id=1, query="data", country="ng")

    assert len(results) == 1
    assert results[0]["job"]["title"] == "Senior Data Scientist"
