"""Keyless Benin job ingestion uses only explicitly local, attributed records."""
import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.services.benin_local import _safe_job, search_benin_local_jobs
from app.services.job_discovery import JobDiscoveryService
from app.services.jsearch import JSearchError


def example(**changes):
    job = {
        "id": "job-1",
        "title": "Data Analyst",
        "company": "Sample Benin Employer",
        "country": "Benin",
        "location": "Cotonou, Bénin",
        "url": "https://devglobaljobs.com/jobs/example-job-1",
        "remote": False,
        "description": "SQL and Python; local office role.",
        "posted": "2026-11-22T12:00:00Z",
    }
    job.update(changes)
    return job


@pytest.mark.parametrize("country", ["bj", "BJ", "Benin", "Bénin", "Benin Republic"])
def test_benin_country_fields_are_accepted(country):
    assert _safe_job(example(country=country)) is not None


@pytest.mark.parametrize("change", [
    {"country": "Nigeria"}, {"country": None}, {"location": "Remote"},
    {"remote": True}, {"remote": "yes"}, {"url": "https://other-site.example/job"},
    {"url": "http://devglobaljobs.com/job/1"}, {"company": ""},
])
def test_unsafe_or_nonlocal_listings_are_excluded(change):
    assert _safe_job(example(**change)) is None


def test_provider_shape_and_provenance():
    job = _safe_job(example())
    assert job is not None
    assert job.source == "devglobaljobs"
    assert job.apply_url == "https://devglobaljobs.com/jobs/example-job-1"
    assert job.remote_status is None
    assert job.salary_min is None and job.salary_max is None
    assert job.description.startswith("SQL")


def test_benin_search_uses_keyword_country_and_city():
    called = []

    def handler(request):
        called.append(request)
        return httpx.Response(200, json={"jobs": [
            example(id="1", location="Cotonou"),
            example(id="2", location="Porto-Novo"),
            example(id="3", country="Nigeria"),
            example(id="4", remote=True),
        ]})
    original = httpx.AsyncClient

    def client(*args, **kwargs):
        return original(*args, transport=httpx.MockTransport(handler), **kwargs)

    with patch("app.services.benin_local.httpx.AsyncClient", side_effect=client):
        jobs = asyncio.run(search_benin_local_jobs("data analyst", location="Cotonou", max_results=5))
    assert [j.provider_job_id for j in jobs] == ["1"]
    assert len(called) == 1
    assert called[0].url.params["country"] == "bj"
    assert called[0].url.params["search"] == "data analyst"
    assert called[0].url.params["limit"] == "5"


def test_invalid_provider_response_is_error_not_fake_zero():
    original = httpx.AsyncClient

    def client(*args, **kwargs):
        return original(*args, transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"unexpected": []})
        ), **kwargs)
    with patch("app.services.benin_local.httpx.AsyncClient", side_effect=client):
        with pytest.raises(JSearchError) as err:
            asyncio.run(search_benin_local_jobs("analyst"))
    assert err.value.status_code == 502


def test_benin_routes_without_rapidapi_and_preserves_remote_branch():
    svc = JobDiscoveryService(db=None)
    example_job = _safe_job(example())
    with (
        patch("app.services.benin_local.search_benin_local_jobs", return_value=[example_job]) as local,
        patch("app.services.remotive.search_remotive_jobs", return_value=[]) as remote,
        patch("app.services.job_discovery.search_jsearch_jobs") as paid,
        patch("app.services.indeed.search_indeed_jobs") as indeed,
    ):
        jobs = svc._search_jobs("data analyst", "bj", remote_only=False, location="Cotonou")
        assert jobs == [example_job]
        local.assert_called_once_with(query="data analyst", location="Cotonou", max_results=20)
        remote.assert_called_once_with(query="data analyst", country="bj", max_results=20, remote_only=True)
        paid.assert_not_called()
        indeed.assert_not_called()
        svc._search_jobs("data analyst", "bj", remote_only=True)
        assert remote.called
