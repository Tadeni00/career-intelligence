"""Only official ATS job APIs may be called for an explicit user preview."""
import asyncio
from unittest.mock import patch

import httpx
import pytest

from app.services.ats_job_preview import (
    identify_job_url, normalize_ats_job, preview_public_job_url,
)
from app.services.jsearch import JSearchError


@pytest.mark.parametrize(("url", "expected"), [
    ("https://boards.greenhouse.io/example/jobs/12345?utm_source=web",
     ("greenhouse", "example", "12345")),
    ("https://job-boards.greenhouse.io/example/jobs/45",
     ("greenhouse", "example", "45")),
    ("https://jobs.lever.co/company/abc-123", ("lever", "company", "abc-123")),
    ("https://jobs.eu.lever.co/company/abc-123", ("lever_eu", "company", "abc-123")),
])
def test_recognized_official_url(url, expected):
    assert identify_job_url(url) == expected


@pytest.mark.parametrize("url", [
    "http://boards.greenhouse.io/company/jobs/1",
    "https://boards.greenhouse.io.evil.test/company/jobs/1",
    "https://evil.test/company/jobs/1",
    "https://user:pass@jobs.lever.co/company/abc",
    "https://jobs.lever.co/company/../../secrets",
    "https://jobs.lever.co/company/",
    "https://jobs.lever.co.company.test/company/abc",
    "https://boards.greenhouse.io/company/jobs/not-numeric",
    "https://boards.greenhouse.io/company/jobs/1/extra",
    "https://jobs.lever.co:8080/company/abc",
    "https://localhost/company/abc",
])
def test_untrusted_or_ambiguous_url_is_rejected_without_fetching(url):
    with pytest.raises(JSearchError) as exc:
        identify_job_url(url)
    assert exc.value.status_code == 422


def greenhouse():
    return {
        "id": 12345,
        "title": "Data Scientist",
        "company_name": "Example Research",
        "location": {"name": "Cotonou, Bénin"},
        "content": "<p>Python, SQL and statistical modelling for operational reporting.</p>",
    }


def lever():
    return {
        "id": "abc-123",
        "text": "Machine Learning Engineer",
        "categories": {"location": "Porto-Novo"},
        "descriptionPlain": "Build and test machine learning pipelines with reliable evaluation.",
        "workplaceType": "on-site",
    }


def test_greenhouse_preview_preserves_known_fields():
    draft = normalize_ats_job(greenhouse(), "greenhouse", "example", "12345")
    assert draft["company"] == "Example Research"
    assert draft["location"] == "Cotonou, Bénin"
    assert draft["description"].startswith("Python, SQL")
    assert draft["remote_status"] == "UNKNOWN"


def test_lever_preview_does_not_guess_company():
    draft = normalize_ats_job(lever(), "lever", "company", "abc-123")
    assert draft["company"] == ""
    assert draft["location"] == "Porto-Novo"
    assert draft["remote_status"] == "ONSITE"


@pytest.mark.parametrize("provider,site,job_id,payload", [
    ("greenhouse", "example", "12345", {"id": 999, "title": "Wrong"}),
    ("lever", "company", "abc-123", {"id": "wrong", "text": "Wrong"}),
])
def test_mismatched_job_identity_rejected(provider, site, job_id, payload):
    with pytest.raises(JSearchError):
        normalize_ats_job(payload, provider, site, job_id)


def test_official_api_host_is_constructed_from_allowlist_and_no_redirects():
    seen = []
    original = httpx.AsyncClient

    def handler(request):
        seen.append(request)
        return httpx.Response(200, json=greenhouse())

    def make_client(*args, **kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return original(*args, transport=httpx.MockTransport(handler), **kwargs)

    with patch("app.services.ats_job_preview.httpx.AsyncClient", side_effect=make_client):
        draft = asyncio.run(preview_public_job_url(
            "https://boards.greenhouse.io/example/jobs/12345?utm_source=test"
        ))
    assert len(seen) == 1
    assert str(seen[0].url) == "https://boards-api.greenhouse.io/v1/boards/example/jobs/12345"
    assert draft["title"] == "Data Scientist"


def test_ats_preview_endpoint_never_saves(client, db, monkeypatch):
    from app.api.routes import jobs as routes
    from app.models import Job

    async def fake_preview(_url):
        return normalize_ats_job(greenhouse(), "greenhouse", "example", "12345")
    monkeypatch.setattr(routes, "preview_public_job_url", fake_preview)
    assert db.query(Job).count() == 0
    response = client.post("/api/v1/jobs/import/preview", json={
        "url": "https://boards.greenhouse.io/example/jobs/12345"
    })
    assert response.status_code == 200, response.text
    assert response.json()["company"] == "Example Research"
    assert db.query(Job).count() == 0


def test_provider_redirect_does_not_get_followed():
    original = httpx.AsyncClient
    def handler(_request):
        return httpx.Response(302, headers={"Location": "http://127.0.0.1/private"})
    def make_client(*args, **kwargs):
        return original(*args, transport=httpx.MockTransport(handler), **kwargs)
    with patch("app.services.ats_job_preview.httpx.AsyncClient", side_effect=make_client):
        with pytest.raises(JSearchError) as exc:
            asyncio.run(preview_public_job_url("https://jobs.lever.co/company/abc-123"))
    assert exc.value.status_code == 502
