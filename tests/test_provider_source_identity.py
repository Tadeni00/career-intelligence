"""Provider provenance regression: an Indeed ID must never masquerade as JSearch."""

from app.services.job_discovery import JobDiscoveryService
from app.services.jsearch import JSearchJob


def _job(source: str) -> JSearchJob:
    return JSearchJob(
        provider_job_id="shared-provider-id",
        title="Data Analyst",
        company="Example Employer",
        location="Remote",
        description="Data analysis role.",
        apply_url="https://example.com/jobs/123",
        posted_at=None,
        salary_min=None,
        salary_max=None,
        salary_currency=None,
        employment_type=None,
        remote_status="REMOTE",
        source=source,
    )


def test_fallback_provider_persisted_without_false_jsearch_attribution(db):
    service = JobDiscoveryService(db)
    indeed = service._create_job_from_jsearch(_job("indeed"), "data analyst", "bj")
    assert indeed.source == "indeed"
    assert indeed.source_id == "shared-provider-id"
    assert indeed.external_id == "indeed:shared-provider-id"
    assert service._find_existing_job("shared-provider-id", "indeed").id == indeed.id
    assert service._find_existing_job("shared-provider-id", "jsearch") is None

    jsearch = service._create_job_from_jsearch(_job("jsearch"), "data analyst", "ng")
    assert jsearch.source == "jsearch"
    assert jsearch.external_id == "jsearch:shared-provider-id"
    assert jsearch.id != indeed.id
    assert service._find_existing_job("shared-provider-id", "jsearch").id == jsearch.id
    assert service._find_existing_job("shared-provider-id", "indeed").id == indeed.id
