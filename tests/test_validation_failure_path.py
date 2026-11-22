"""Regression test for the E8 defect: a tailored CV / cover letter that FAILS
validation must be returned with its report, not raise HTTP 500.

The original V1 acceptance suite never covered this path because every test
asserted `validation_issues == []`; the schema declared `validation_issues` as
`list[str]` while the route supplied dicts, so the mismatch was invisible until
at least one issue existed.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from app.schemas import CoverLetterOut, TailoredCVOut, ValidationIssue

NOW = datetime.now(UTC)


def _issue_dict(code: str = "INVENTED_EMPLOYER") -> dict:
    return {
        "severity": "error",
        "code": code,
        "message": "Employer 'Acme Corp' is not on the confirmed profile.",
        "detail": "Acme Corp",
    }


def _cv(**kw) -> TailoredCVOut:
    base = dict(
        id=1, candidate_id=1, job_id=1, source_cv_id=None, version=1,
        filename="x.docx", storage_path="p", summary=None, analysis=None,
        changes_summary=[], validation_status="VALID", validation_issues=[],
        created_at=NOW,
    )
    base.update(kw)
    return TailoredCVOut(**base)


def test_tailored_cv_out_accepts_structured_validation_issues():
    """A non-empty issue list must serialise, not explode."""
    out = _cv(
        changes_summary=["Reordered experience"],
        validation_status="VALIDATION_FAILED",
        validation_issues=[ValidationIssue.model_validate(_issue_dict())],
    )
    assert out.validation_status == "VALIDATION_FAILED"
    assert out.validation_issues[0].code == "INVENTED_EMPLOYER"
    assert out.validation_issues[0].severity == "error"


def test_cover_letter_out_accepts_structured_validation_issues():
    out = CoverLetterOut(
        id=1, candidate_id=1, job_id=1, content="Dear team,",
        validation_status="VALIDATION_FAILED",
        validation_issues=[ValidationIssue.model_validate(_issue_dict("UNSUPPORTED_CLAIM"))],
        created_at=NOW,
    )
    assert out.validation_issues[0].code == "UNSUPPORTED_CLAIM"


def test_empty_issue_list_still_validates():
    out = _cv()
    assert out.validation_issues == []


def test_changes_summary_remains_strings():
    """changes_summary is genuinely list[str]; guard against a future mix-up."""
    out = _cv(changes_summary=["Emphasised Python", "De-emphasised teaching roles"])
    assert all(isinstance(s, str) for s in out.changes_summary)


def test_api_returns_failed_tailored_cv_with_its_report(client, monkeypatch):
    """End-to-end: a VALIDATION_FAILED tailored CV must be HTTP 200 with issues."""
    client.get("/api/v1/candidate")
    job = client.post("/api/v1/jobs", json={
        "title": "Data Scientist", "company": "Testco",
        "description": "Required: Python, SQL.",
    }).json()

    import app.services.generation as generation

    real_validate = generation.validate_tailored_cv

    def failing_validate(content, profile, jd=""):
        from app.models import ValidationStatus
        from app.schemas import ValidationIssue, ValidationReport

        real_validate(content, profile, jd)
        return ValidationReport(
            status=ValidationStatus.VALIDATION_FAILED,
            issues=[ValidationIssue.model_validate(_issue_dict())],
        )

    monkeypatch.setattr(generation, "validate_tailored_cv", failing_validate)

    response = client.post(f"/api/v1/jobs/{job['id']}/tailor-cv")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["validation_status"] == "VALIDATION_FAILED"
    assert len(body["validation_issues"]) == 1
    assert body["validation_issues"][0]["code"] == "INVENTED_EMPLOYER"
    assert json.dumps(body["validation_issues"])  # JSON-serialisable for the UI
