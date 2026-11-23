"""Read-only live job-source coverage probe, for GitHub Actions diagnostics.

No CVs, secrets, employer/job titles, raw descriptions, original URLs or
response bodies are logged. A failed network request is *unknown*, not zero.
This script never persists jobs or accesses the application database.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_RESPONSE_BYTES = 8 * 1024 * 1024
DEV_API = "https://devglobaljobs.com/api/v1/jobs?country=bj&limit=100"
REMOTIVE_API = "https://remotive.com/api/remote-jobs"


def retrieve_json(url: str, timeout: int = 15) -> object:
    """Fetch only a hard-coded provider endpoint with strict response bounds."""
    if url not in (DEV_API, REMOTIVE_API):
        raise ValueError("Provider URL is not allowlisted")
    request = Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "CareerIntelligenceCoverageAudit/1.0 (read-only)",
    })
    with urlopen(request, timeout=timeout) as response:
        data = response.read(MAX_RESPONSE_BYTES + 1)
        if len(data) > MAX_RESPONSE_BYTES:
            raise ValueError("provider response exceeds bounded audit size")
        return json.loads(data)


def _rows(body: object) -> list | None:
    if isinstance(body, list):
        return body
    if not isinstance(body, dict):
        return None
    rows = body.get("jobs", body.get("data"))
    if isinstance(rows, dict):
        rows = rows.get("jobs")
    return rows if isinstance(rows, list) else None


def dev_global_summary(body: object) -> dict:
    """Compare documented response with current conservative Benin adapter."""
    rows = _rows(body)
    if rows is None:
        return {"schema": "incompatible", "records": None}
    # A source must expose Benin country + employer/title/location and a
    # source-owned HTTPS job page before the app may accept a local job.
    allowed_countries = {
        "bj", "benin", "bénin", "benin republic",
        "republic of benin", "république du bénin",
    }
    usable = 0
    missing_fields = 0
    unexpected_country = 0
    unexpected_link = 0
    for row in rows:
        if not isinstance(row, dict):
            missing_fields += 1
            continue
        country = row.get("country") or row.get("country_code") or row.get("countryCode")
        if not isinstance(country, str) or country.strip().casefold() not in allowed_countries:
            unexpected_country += 1
            continue
        title = row.get("title")
        employer = row.get("company") or row.get("company_name") or row.get("organization")
        location = row.get("location") or row.get("city")
        link = row.get("url") or row.get("jobUrl") or row.get("job_url")
        if not all(isinstance(value, str) and value.strip()
                   for value in (title, employer, location, link)):
            missing_fields += 1
            continue
        from urllib.parse import urlsplit
        url = urlsplit(link)
        if url.scheme != "https" or url.hostname not in ("devglobaljobs.com", "www.devglobaljobs.com"):
            unexpected_link += 1
            continue
        if row.get("remote") is True or str(row.get("workArrangement") or "").lower() in ("remote", "fully remote"):
            continue
        usable += 1
    return {
        "schema": "list", "records": len(rows), "candidate_benin_local": usable,
        "missing_fields": missing_fields, "unexpected_country": unexpected_country,
        "unexpected_link": unexpected_link,
        "note": "Bounded sample, not number of live vacancies in Benin",
    }


def remotive_summary(body: object) -> dict:
    rows = _rows(body)
    if rows is None:
        return {"schema": "incompatible", "records": None}
    eligible = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        location = row.get("candidate_required_location")
        if not isinstance(location, str):
            continue
        import re
        parts = [v.strip(" .()") for v in re.split(r"[,;/|]|\bor\b", location.casefold())]
        if any(v in {
            "worldwide", "anywhere", "global", "anywhere in the world",
            "benin", "bénin", "bj", "benin republic", "république du bénin",
            "africa", "west africa", "western africa",
        } for v in parts):
            eligible += 1
    return {
        "schema": "list", "records": len(rows),
        "potentially_benin_eligible_remote": eligible,
        "note": "Location-only sample; keyword match, job validity and work authorization unverified",
    }


def run_probe(fetch=retrieve_json) -> dict:
    result = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "type": "read_only_source_contract_and_coverage_sample",
        "providers": {},
    }
    for name, url, summarize in [
        ("devglobaljobs", DEV_API, dev_global_summary),
        ("remotive", REMOTIVE_API, remotive_summary),
    ]:
        try:
            result["providers"][name] = {
                "status": "responded",
                **summarize(fetch(url)),
            }
        except (HTTPError, URLError, TimeoutError, ValueError, OSError, json.JSONDecodeError) as exc:
            result["providers"][name] = {
                "status": "unavailable_or_unparseable",
                "error_type": type(exc).__name__,
                "records": None,
                "note": "Unknown coverage; do not interpret as zero vacancies",
            }
    return result


if __name__ == "__main__":
    print(json.dumps(run_probe(), indent=2, ensure_ascii=False))
    # Informational only; CI's mandatory unit tests remain deterministic.
    sys.exit(0)
