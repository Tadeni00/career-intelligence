"""User-confirmed local vacancy import: safe URL references, idempotency, no fetch."""
import pytest

from app.services.vacancy_import import normalized_job_url


@pytest.mark.parametrize(("url","expected"), [
    ("https://jobs.example.org/role/1#details", "https://jobs.example.org/role/1"),
    ("https://jobs.example.org/role/1?utm_source=feed&ref=job", "https://jobs.example.org/role/1?ref=job"),
    ("https://JOBS.EXAMPLE.ORG", "https://jobs.example.org/"),
])
def test_normalize_original_url(url, expected):
    assert normalized_job_url(url) == expected


@pytest.mark.parametrize("url", [
    "http://jobs.example.org/job", "https://u:p@jobs.example.org/job",
    "file:///etc/passwd", "https://localhost/jobs/1",
    "https://127.0.0.1/jobs/1", "https://jobs.example.org:8080/job",
    "not a URL", "javascript:alert(1)",
])
def test_invalid_job_url_is_rejected(url):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        normalized_job_url(url)
    assert exc.value.status_code == 422


def payload(**changes):
    values = {
        "title": "Data Analyst",
        "company": "Example Employer",
        "location": "Cotonou, Benin",
        "url": "https://jobs.example.org/roles/123?utm_campaign=search",
        "description": "We are looking for an analyst with Python and SQL experience.",
        "remote_status": "ONSITE",
    }
    values.update(changes)
    return values


def test_import_api_saves_record_and_never_fetches_link(client, monkeypatch):
    import httpx

    def forbidden_fetch(*_args, **_kwargs):
        raise AssertionError("Importing must not fetch external pages")
    monkeypatch.setattr(httpx, "get", forbidden_fetch)
    r = client.post("/api/v1/jobs/import", json=payload())
    assert r.status_code == 200, r.text
    assert r.json()["created"] is True
    job_id = r.json()["job_id"]
    got = client.get(f"/api/v1/jobs/{job_id}")
    assert got.status_code == 200
    data = got.json()
    assert data["source"] == "manual_import"
    assert data["is_discovered"] is False
    assert data["url"] == "https://jobs.example.org/roles/123"
    assert data["description"] == payload()["description"]
    assert data["requirements_extracted"] is False


def test_repeated_original_link_returns_existing_job_without_overwriting(client):
    first = client.post("/api/v1/jobs/import", json=payload())
    second = client.post("/api/v1/jobs/import", json=payload(
        title="Different title", url="https://jobs.example.org/roles/123",
    ))
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["created"] is False
    assert second.json()["job_id"] == first.json()["job_id"]
    got = client.get(f"/api/v1/jobs/{first.json()['job_id']}")
    assert got.json()["title"] == "Data Analyst"


@pytest.mark.parametrize("changes", [
    {"title": " "}, {"company": ""}, {"location": " "},
    {"description": "Too short"},
    {"remote_status": "TELEPORT"},
    {"url": "http://example.com/jobs/123"},
])
def test_incomplete_import_is_rejected(client, changes):
    response = client.post("/api/v1/jobs/import", json=payload(**changes))
    assert response.status_code == 422
