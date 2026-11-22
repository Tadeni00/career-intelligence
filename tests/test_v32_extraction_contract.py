"""V3.2 Workstream B — PARTIAL extraction contract verification.

V3.1 defined four extraction states. V3.2 verifies the intended semantics hold
and, specifically, that PARTIAL is *identifiable* rather than silently
masquerading as SUCCESS.

Required matrix:
    SUCCESS         -> matchable
    PARTIAL         -> identifiable as partial / review state
    FAILED          -> not matchable
    EMPTY_CONFIRMED -> matchable
"""

from __future__ import annotations

import pytest
from app.models import ExtractionStatus, Job, JobRequirement
from app.services import extraction as ex


def _job(status: str | None, *, with_requirements: bool = True,
         error_code: str | None = None) -> Job:
    job = Job(title="Data Scientist", company="Acme", location="Amsterdam",
              description="Required: Python.")
    job.extraction_status = status
    job.extraction_error_code = error_code
    job.requirements = [
        JobRequirement(requirement_type="SKILL", name="Python",
                       importance="REQUIRED")
    ] if with_requirements else []
    return job


# =========================================================================== #
# the required matrix
# =========================================================================== #


def test_success_is_matchable():
    ex.assert_matchable(_job(ExtractionStatus.SUCCESS.value))


def test_partial_is_matchable_but_flagged_for_review():
    """PARTIAL may be scored, but never silently: the state must be visible."""
    from app.api.routes.jobs import _mark_review

    job = _job(ExtractionStatus.PARTIAL.value)
    ex.assert_matchable(job)

    out = _mark_review(
        type("O", (), {
            "extraction_status": job.extraction_status,
            "requires_review": False,
        })()
    )
    assert out.requires_review is True
    assert out.extraction_status == ExtractionStatus.PARTIAL.value


def test_partial_is_not_reported_as_success():
    from app.api.routes.jobs import _mark_review

    class _O:
        extraction_status = ExtractionStatus.PARTIAL.value
        requires_review = False

    out = _mark_review(_O())
    assert out.extraction_status != ExtractionStatus.SUCCESS.value
    assert out.requires_review is True


def test_failed_is_not_matchable():
    job = _job(ExtractionStatus.FAILED.value, with_requirements=False,
               error_code="NO_REQUIREMENTS_FOUND")
    with pytest.raises(ex.ExtractionNotMatchableError):
        ex.assert_matchable(job)


def test_empty_confirmed_is_matchable():
    ex.assert_matchable(
        _job(ExtractionStatus.EMPTY_CONFIRMED.value, with_requirements=False)
    )


@pytest.mark.parametrize("status", [
    ExtractionStatus.SUCCESS.value,
    ExtractionStatus.PARTIAL.value,
    ExtractionStatus.EMPTY_CONFIRMED.value,
])
def test_matchable_states(status):
    ex.assert_matchable(_job(status, with_requirements=(status !=
                                                       ExtractionStatus.EMPTY_CONFIRMED.value)))


# =========================================================================== #
# PARTIAL reaches the API layer as PARTIAL
# =========================================================================== #


def test_partial_extraction_is_visible_through_the_job_api(client, db, candidate):
    job = client.post("/api/v1/jobs", json={
        "title": "Data Scientist", "company": "Acme",
        "description": "Required: Python and SQL.",
    }).json()
    client.post(f"/api/v1/jobs/{job['id']}/extract-requirements")

    # Simulate the PARTIAL outcome the contract can produce.
    from app.models import Job as JobModel

    row = db.get(JobModel, job["id"])
    row.extraction_status = ExtractionStatus.PARTIAL.value
    row.extraction_error_code = "PARTIAL_RECOVERY"
    db.commit()

    detail = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert detail["extraction_status"] == ExtractionStatus.PARTIAL.value
    assert detail["extraction_error_code"] == "PARTIAL_RECOVERY"
    assert detail["requires_review"] is True

    listed = client.get("/api/v1/jobs").json()
    summary = next(j for j in listed if j["id"] == job["id"])
    assert summary["extraction_status"] == ExtractionStatus.PARTIAL.value
    assert summary["requires_review"] is True


def test_failed_extraction_is_visible_through_the_job_api(client, db, candidate):
    job = client.post("/api/v1/jobs", json={
        "title": "Data Analyst", "company": "Globex",
        "description": "Required: Python.",
    }).json()

    from app.models import Job as JobModel

    row = db.get(JobModel, job["id"])
    row.extraction_status = ExtractionStatus.FAILED.value
    row.extraction_error_code = "NO_REQUIREMENTS_FOUND"
    db.commit()

    detail = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert detail["extraction_status"] == ExtractionStatus.FAILED.value
    assert detail["requires_review"] is True

    # ...and a failed job still cannot be matched.
    response = client.post(f"/api/v1/jobs/{job['id']}/match")
    assert response.status_code == 409, response.text
    assert "requirement" in response.text.lower()


def test_success_extraction_is_not_flagged(client, db, candidate):
    job = client.post("/api/v1/jobs", json={
        "title": "Data Scientist", "company": "Initech",
        "description": "Required: Python and SQL.",
    }).json()
    client.post(f"/api/v1/jobs/{job['id']}/extract-requirements")
    detail = client.get(f"/api/v1/jobs/{job['id']}").json()
    assert detail["extraction_status"] == ExtractionStatus.SUCCESS.value
    assert detail["requires_review"] is False


# =========================================================================== #
# partial status resolution (no silent promotion/demotion)
# =========================================================================== #


def test_partial_is_not_silently_promoted_to_success():
    """Recovered elements plus dropped elements must stay PARTIAL."""
    result = ex.classify_raw_payload(
        {"required_skills": ["Python"], "preferred_skills": [],
         "responsibilities": [], "issues": [],
         "experience_requirements": [["bad"]],
         "education_requirements": [], "location_requirements": [],
         "other_requirements": []},
        source="Posting with content.",
    )
    assert result.meta.status == ExtractionStatus.PARTIAL.value
    assert result.meta.dropped_elements


def test_partial_remains_partial_even_with_many_recovered():
    result = ex.classify_raw_payload(
        {"required_skills": ["Python", "SQL", "Airflow"],
         "preferred_skills": [], "responsibilities": [], "issues": [],
         "experience_requirements": [{"name": "5+ years ML"}, "3+ years DS"],
         "education_requirements": [], "location_requirements": [],
         "other_requirements": [["bad"]]},
        source="Posting with content.",
    )
    # Recovered (the bare string) and dropped (the nested list) coexist; the
    # outcome is PARTIAL, never SUCCESS.
    assert result.meta.status == ExtractionStatus.PARTIAL.value
    assert result.meta.recovered_elements >= 1
    assert result.meta.dropped_elements
    assert result.meta.requirement_count >= 5
