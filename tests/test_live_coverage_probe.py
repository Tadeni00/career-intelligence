"""Live coverage probe is read-only, bounded, and honest about failures."""
from urllib.error import URLError

import pytest

from scripts.live_coverage_probe import (
    DEV_API, REMOTIVE_API, dev_global_summary,
    remotive_summary, retrieve_json, run_probe,
)


def local_job(**kwargs):
    record = {
        "id": "1", "title": "Data Analyst",
        "company": "Example Company",
        "country": "Benin", "location": "Cotonou, Benin",
        "url": "https://devglobaljobs.com/jobs/detail/1",
        "remote": False,
    }
    record.update(kwargs)
    return record


def test_free_feed_reports_usable_and_missing_local_records_without_content():
    data = {"jobs": [
        local_job(),
        local_job(id="2", country="Nigeria"),
        local_job(id="3", url="https://untrusted.example/job"),
        local_job(id="4", company=""),
    ]}
    summary = dev_global_summary(data)
    assert summary["records"] == 4
    assert summary["candidate_benin_local"] == 1
    assert summary["unexpected_country"] == 1
    assert summary["unexpected_link"] == 1
    assert summary["missing_fields"] == 1
    assert "Example Company" not in str(summary)


def test_remote_summary_does_not_mislabel_geographically_restricted_roles():
    result = remotive_summary({"jobs": [
        {"candidate_required_location": "Worldwide"},
        {"candidate_required_location": "US only"},
        {"candidate_required_location": "West Africa"},
        {"candidate_required_location": ""},
    ]})
    assert result["records"] == 4
    assert result["potentially_benin_eligible_remote"] == 2


def test_schema_incompatibility_is_flagged_not_zero():
    assert dev_global_summary({"unexpected": []})["schema"] == "incompatible"
    assert dev_global_summary({"unexpected": []})["records"] is None
    assert remotive_summary({"bad": {}})["records"] is None


def test_network_failure_is_unknown_not_empty():
    def fail(url):
        raise URLError("network unavailable")
    result = run_probe(fail)
    assert result["providers"]["devglobaljobs"]["status"] == "unavailable_or_unparseable"
    assert result["providers"]["devglobaljobs"]["records"] is None
    assert result["providers"]["remotive"]["records"] is None


def test_audit_uses_only_preapproved_readonly_urls():
    calls = []
    def fetch(url):
        calls.append(url)
        return {"jobs": []}
    result = run_probe(fetch)
    assert calls == [DEV_API, REMOTIVE_API]
    assert all(v["status"] == "responded" for v in result["providers"].values())


def test_fetch_helper_rejects_arbitrary_host_before_network():
    with pytest.raises(ValueError):
        retrieve_json("http://127.0.0.1:8000/private")
