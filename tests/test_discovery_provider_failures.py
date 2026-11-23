"""Provider failures must remain actionable without exposing provider internals."""

import pytest

from app.api.routes import external_jobs
from app.services.jsearch import JSearchError


@pytest.mark.parametrize(
    ("provider_status", "expected_status", "expected_detail"),
    [
        (429, 429, "rate limit"),
        (401, 503, "authentication"),
        (403, 503, "authentication"),
        (502, 502, "request failed"),
        (504, 504, "request failed"),
    ],
)
def test_discovery_provider_failures_are_safe_and_distinct(
    client, monkeypatch, provider_status, expected_status, expected_detail
):
    def unavailable(**_kwargs):
        raise JSearchError("sensitive upstream diagnostics", provider_status)

    monkeypatch.setattr(external_jobs, "discover_jobs", unavailable)
    response = client.post(
        "/api/v1/jobs/discover",
        json={"query": "data analyst", "country": "bj", "max_results": 5},
    )
    assert response.status_code == expected_status
    assert expected_detail in response.json()["detail"].lower()
    assert "sensitive upstream diagnostics" not in response.text
