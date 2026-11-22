"""IndeedProvider unit tests: normalization of an Indeed API page, error paths.

Live Indeed.com Indeed API is rate-limited for our key on this account
(429s observed); these tests cover the client with a mocked Indeed API
response, which is the deterministic path.
"""

from __future__ import annotations

import pytest

from app.services.indeed import IndeedProvider, IndeedProviderError

INDEED_PAGE = {
    "results": [
        {
            "job_id": "indeed:123456789",
            "job_title": "Senior Software Engineer",
            "employer_name": "TechLogix",
            "job_location": "Cotonou, Benin Republic",
            "job_description": "We need a senior engineer.",
            "job_apply_link": "https://indeed.com/x/apply/123",
            "job_posted_at_datetime_utc": "2026-10-01T10:00:00Z",
            "job_min_salary": 1500000,
            "job_max_salary": 2000000,
            "job_is_remote": True,
        },
        {
            # Missing fields -> dropped, not preserved
            "job_title": "Incomplete entry",
        },
    ]
}


class TestIndeedProviderNormalization:
    def test_normalizes_indeed_page(self):
        provider = IndeedProvider(api_key="test-key")
        jobs = provider._normalize_page(INDEED_PAGE)
        assert len(jobs) == 1
        job = jobs[0]
        assert job.provider_job_id == "indeed:123456789"
        assert job.title == "Senior Software Engineer"
        assert job.company == "TechLogix"
        assert job.location == "Cotonou, Benin Republic"
        assert job.apply_url == "https://indeed.com/x/apply/123"
        assert job.salary_min == 1500000.0
        assert job.remote_status == "REMOTE"
        assert job.source == "indeed"
        assert job.posted_at is not None

    def test_nested_shape_supported(self):
        provider = IndeedProvider(api_key="test-key")
        data = {"searchResults": list(INDEED_PAGE["results"])}
        jobs = provider._normalize_page(data)
        assert len(jobs) == 1

    def test_empty_page_returns_empty(self):
        provider = IndeedProvider(api_key="test-key")
        assert provider._normalize_page({"results": []}) == []
        assert provider._normalize_page({}) == []


class TestIndeedProviderErrors:
    def test_429_mapped_to_provider_error(self, monkeypatch):
        import httpx

        provider = IndeedProvider(api_key="test-key")

        resp = httpx.Response(429, json={"message": "Too many requests"})

        async def fake_get(*args, **kwargs):
            return resp

        monkeypatch.setattr(provider._client, "get", fake_get)

        import asyncio

        with pytest.raises(IndeedProviderError) as exc_info:
            asyncio.run(provider.search_jobs(query="x", country="bj"))
        assert exc_info.value.status_code == 429

    def test_invalid_json_raises_provider_error(self, monkeypatch):
        import httpx

        provider = IndeedProvider(api_key="test-key")
        resp = httpx.Response(200, content=b"<html>not json</html>")

        async def fake_get(*args, **kwargs):
            return resp

        monkeypatch.setattr(provider._client, "get", fake_get)

        import asyncio

        with pytest.raises(IndeedProviderError):
            asyncio.run(provider.search_jobs(query="x", country="bj"))
