"""Remotive geo eligibility, no-key search, safe attribution and routing."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.services.jsearch import JSearchError
from app.services.job_discovery import JobDiscoveryService
from app.services import remotive


def _job(job_id, region, title="Data Scientist", url=None):
    return {
        "id": job_id,
        "url": url or f"https://remotive.com/remote-jobs/data-scientist-{job_id}",
        "title": title,
        "company_name": "Example Employer",
        "candidate_required_location": region,
        "description": "<p>Python and SQL work</p>",
        "publication_date": "2026-11-20T10:00:00",
        "job_type": "full_time",
    }


@pytest.mark.parametrize("region,expected", [
    ("Worldwide", True), ("Africa", True), ("West Africa", True),
    ("Benin", True), ("Benin Republic", True), ("United States", False),
    ("Europe", False), ("Nigeria", False), (None, False),
])
def test_benin_geography_does_not_infer_worldwide_eligibility(region, expected):
    assert remotive.eligible_remote_region(region, "bj") is expected


def test_other_country_not_mislabeled_as_benin():
    assert not remotive.eligible_remote_region("Benin", "ng")
    assert remotive.eligible_remote_region("Nigeria", "ng")
    assert remotive.eligible_remote_region("Worldwide", "zz")


def test_external_apply_url_must_be_remotive():
    assert remotive._to_job(_job(1, "Worldwide", url="https://example.org/apply")) is None
    job = remotive._to_job(_job(2, "Worldwide"))
    assert job is not None
    assert job.source == "remotive"
    assert job.remote_status == "REMOTE"
    assert job.location == "Remote — Worldwide"
    assert job.apply_url.startswith("https://remotive.com/")
    assert job.salary_min is None


def test_remote_search_filters_disallowed_regions_and_uses_cached_feed():
    remotive._CACHE.clear()
    calls = []

    def handler(request):
        calls.append(request.url)
        return httpx.Response(200, json={"jobs": [
            _job(1, "US only"), _job(2, "Worldwide"), _job(3, "Europe"),
            _job(4, "Africa", title="Data Scientist"),
            _job(5, "Benin", title="Frontend Developer"),
        ]})

    original_client = httpx.AsyncClient

    def make_client(*args, **kwargs):
        return original_client(*args, transport=httpx.MockTransport(handler), **kwargs)

    with patch.object(remotive.httpx, "AsyncClient", side_effect=make_client):
        one = asyncio.run(remotive.search_remotive_jobs("Data Scientist", "bj"))
        two = asyncio.run(remotive.search_remotive_jobs("Data Scientist", "bj"))
    assert [x.provider_job_id for x in one] == ["2", "4"]
    assert len(two) == len(one)
    assert len(calls) == 1
    remotive._CACHE.clear()


def test_invalid_provider_data_fails_instead_of_claiming_no_jobs():
    remotive._CACHE.clear()

    def handler(_request):
        return httpx.Response(200, json={"unexpected": []})

    with patch.object(remotive.httpx, "AsyncClient", return_value=httpx.AsyncClient(transport=httpx.MockTransport(handler))):
        with pytest.raises(JSearchError):
            asyncio.run(remotive.search_remotive_jobs("analyst", "bj"))
    remotive._CACHE.clear()


def test_benin_remote_route_skips_paid_jsearch_and_indeed():
    service = JobDiscoveryService(db=None)
    sample = [remotive._to_job(_job(17, "Worldwide"))]
    with (
        patch("app.services.remotive.search_remotive_jobs", return_value=sample) as free,
        patch("app.services.job_discovery.search_jsearch_jobs") as paid,
        patch("app.services.indeed.search_indeed_jobs") as other,
    ):
        results = service._search_jobs(query="data scientist", country="bj", remote_only=True, max_results=10)
    assert results == sample
    assert free.called
    paid.assert_not_called()
    other.assert_not_called()


def test_no_remote_mode_does_not_silently_use_international_remote_only_jobs():
    assert asyncio.run(remotive.search_remotive_jobs("data scientist", "bj", remote_only=False)) == []
