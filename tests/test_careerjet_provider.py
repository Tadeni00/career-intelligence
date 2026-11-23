"""Opt-in Careerjet publisher fallback: no unapproved calls or invented identity."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pytest

from app.services.careerjet import (
    CareerjetCredentials, _normalize, search_careerjet_benin_jobs,
)
from app.services.job_discovery import JobDiscoveryService
from app.services.jsearch import JSearchError, JSearchJob


def credentials(**kwargs):
    fields = dict(
        publisher_key="test-secret", user_ip="8.8.8.8",
        user_agent="Mozilla/5.0 Test Browser", referer="https://publisher.example/jobs",
    )
    fields.update(kwargs)
    return CareerjetCredentials(**fields)


def sample(**kwargs):
    values = dict(
        job_id="cj-42", title="Analyste de données", company="Test Organisation",
        description="<p>Python et SQL</p>", locations="Cotonou",
        url="https://jobviewtrack.com/v2/example",
        date="Fri, 20 Nov 2026 12:00:00 GMT",
        salary_min=1000, salary_max=2000, salary_currency_code="XOF",
    )
    values.update(kwargs)
    return values


def empty_settings(**kwargs):
    fields = dict(careerjet_publisher_key="", careerjet_user_ip="",
                  careerjet_user_agent="", careerjet_referer="")
    fields.update(kwargs)
    return SimpleNamespace(**fields)


def test_missing_or_partial_publisher_config_never_activates():
    assert CareerjetCredentials.from_settings(empty_settings()) is None
    assert CareerjetCredentials.from_settings(empty_settings(careerjet_publisher_key="abc")) is None


@pytest.mark.parametrize("field,value", [
    ("user_ip", "127.0.0.1"), ("user_ip", "172.17.0.1"),
    ("user_ip", "not-an-address"), ("referer", "http://publisher.example/jobs"),
    ("referer", "https://user:pass@publisher.example/jobs"),
    ("user_agent", "fake"),
])
def test_false_requester_provenance_is_rejected(field, value):
    with pytest.raises(JSearchError) as err:
        credentials(**{field: value}).validate()
    assert err.value.status_code == 503


def test_normalization_preserves_source_and_avoids_unverified_salary():
    job = _normalize(sample())
    assert job is not None
    assert job.source == "careerjet"
    assert job.provider_job_id == "cj-42"
    assert job.location == "Cotonou"
    assert job.salary_min is None and job.salary_max is None
    assert job.salary_currency is None
    assert job.apply_url.startswith("https://jobviewtrack.com/")
    assert job.posted_at is not None


@pytest.mark.parametrize("change", [
    {"url": "http://jobviewtrack.com/jobs/x"},
    {"url": "https://evil.example/jobs"},
    {"url": "https://jobviewtrack.com.evil.example/jobs"},
    {"locations": "Remote"},
    {"company": ""}, {"locations": ""},
])
def test_bad_links_and_unverified_location_are_dropped(change):
    assert _normalize(sample(**change)) is None


def test_search_uses_exact_publisher_contract_and_limits_to_page_one():
    observed = []
    def handler(request):
        observed.append(request)
        return httpx.Response(200, json={"type": "JOBS", "jobs": [sample()]})
    original = httpx.AsyncClient
    def make_client(*args, **kwargs):
        return original(*args, transport=httpx.MockTransport(handler), **kwargs)
    with patch("app.services.careerjet.httpx.AsyncClient", side_effect=make_client):
        jobs = asyncio.run(search_careerjet_benin_jobs("analyste", "Cotonou", 10, credentials()))
    assert len(jobs) == 1
    assert jobs[0].source == "careerjet"
    req = observed[0]
    assert req.url.host == "search.api.careerjet.net"
    assert req.url.params["locale_code"] == "fr_BJ"
    assert req.url.params["keywords"] == "analyste"
    assert req.url.params["location"] == "Cotonou"
    assert req.url.params["user_ip"] == "8.8.8.8"
    assert req.url.params["user_agent"] == "Mozilla/5.0 Test Browser"
    assert req.url.params["page_size"] == "10"
    assert req.headers["referer"] == "https://publisher.example/jobs"
    assert req.headers["authorization"].startswith("Basic ")


@pytest.mark.parametrize("status,body,expected", [
    (429, {}, 429), (403, {}, 503), (502, {}, 502),
    (200, {"type": "LOCATIONS", "locations": []}, 422),
    (200, {"type": "JOBS"}, 502),
])
def test_errors_are_not_misrepresented_as_no_vacancies(status, body, expected):
    original = httpx.AsyncClient
    def make_client(*args, **kwargs):
        return original(*args, transport=httpx.MockTransport(
            lambda _request: httpx.Response(status, json=body)), **kwargs)
    with patch("app.services.careerjet.httpx.AsyncClient", side_effect=make_client):
        with pytest.raises(JSearchError) as e:
            asyncio.run(search_careerjet_benin_jobs("analyst", None, 5, credentials()))
    assert e.value.status_code == expected
    assert "test-secret" not in str(e.value)


def test_benin_queries_both_sources_even_when_keyless_has_jobs():
    """A single keyless result must not mask unique Careerjet listings."""
    svc = JobDiscoveryService(db=None)
    primary = JSearchJob(
        provider_job_id="one", title="Data Scientist", company="Test Employer",
        location="Cotonou", description="", apply_url="https://devglobaljobs.com/jobs/one",
        posted_at=None, salary_min=None, salary_max=None, salary_currency=None,
        employment_type=None, remote_status=None, source="devglobaljobs",
    )
    second = JSearchJob(
        provider_job_id="two", title="Data Engineer", company="Another Employer",
        location="Porto-Novo", description="", apply_url="https://jobviewtrack.com/jobs/two",
        posted_at=None, salary_min=None, salary_max=None, salary_currency=None,
        employment_type=None, remote_status=None, source="careerjet",
    )
    configured = empty_settings(
        careerjet_publisher_key="abc", careerjet_user_ip="8.8.8.8",
        careerjet_user_agent="Mozilla/5.0 Test Browser",
        careerjet_referer="https://publisher.example/jobs",
    )
    with (
        patch("app.services.benin_local.search_benin_local_jobs", return_value=[primary]) as free,
        patch("app.core.config.get_settings", return_value=configured),
        patch("app.services.careerjet.search_careerjet_benin_jobs", return_value=[second]) as publisher,
    ):
        jobs = svc._search_jobs("analyst", "bj", 10, location="Cotonou")
        assert jobs == [primary, second]
        free.assert_called_once()
        publisher.assert_called_once()
        assert publisher.call_args.kwargs["location"] == "Cotonou"


def test_benin_without_publisher_credentials_only_queries_keyless_source():
    svc = JobDiscoveryService(db=None)
    job = JSearchJob(
        provider_job_id="one", title="Data Scientist", company="Test Employer",
        location="Cotonou", description="", apply_url="https://devglobaljobs.com/jobs/one",
        posted_at=None, salary_min=None, salary_max=None, salary_currency=None,
        employment_type=None, remote_status=None, source="devglobaljobs",
    )
    with (
        patch("app.services.benin_local.search_benin_local_jobs", return_value=[job]),
        patch("app.core.config.get_settings", return_value=empty_settings()),
        patch("app.services.careerjet.search_careerjet_benin_jobs") as publisher,
    ):
        assert svc._search_jobs("analyst", "bj", 10) == [job]
        publisher.assert_not_called()


def test_benin_publisher_is_queried_when_free_source_returns_zero():
    svc = JobDiscoveryService(db=None)
    settings = empty_settings(
        careerjet_publisher_key="abc", careerjet_user_ip="8.8.8.8",
        careerjet_user_agent="Mozilla/5.0 Test Browser",
        careerjet_referer="https://publisher.example/jobs",
    )
    with (
        patch("app.services.benin_local.search_benin_local_jobs", return_value=[]),
        patch("app.core.config.get_settings", return_value=settings),
        patch("app.services.careerjet.search_careerjet_benin_jobs", return_value=[]) as publisher,
    ):
        assert svc._search_jobs("analyst", "bj", 10) == []
        publisher.assert_called_once()
