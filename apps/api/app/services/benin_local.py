"""Benin-local vacancies through the permissioned Dev Global Jobs API.

Terms: https://devglobaljobs.com/developers — free for non-commercial use,
requires visible "Powered by Dev Global Jobs" attribution and links to its
job page. No CV or personally identifying information is submitted.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from app.services.jsearch import JSearchError, JSearchJob

API_URL = "https://devglobaljobs.com/api/v1/jobs"
PROVIDER_URL = "https://devglobaljobs.com"
SOURCE = "devglobaljobs"
MAX_RESULTS = 50


def _verified_benin(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return value.casefold().strip() in {
        "bj", "benin", "bénin", "benin republic", "république du bénin",
        "republic of benin",
    }


def _is_remote(record: dict) -> bool:
    # Do not present a known remote-only vacancy as physically in Benin.
    flag = record.get("remote")
    if flag is True or (isinstance(flag, str) and flag.lower() in {"true", "yes", "1"}):
        return True
    arrangement = str(record.get("workArrangement") or record.get("work_arrangement")
                      or record.get("remote_status") or "").strip().casefold()
    return arrangement in {"remote", "remote only", "fully remote"}


def _safe_job(record: object) -> JSearchJob | None:
    if not isinstance(record, dict):
        return None
    title = record.get("title")
    employer = record.get("company") or record.get("company_name") or record.get("organization")
    link = record.get("url") or record.get("jobUrl") or record.get("job_url")
    location = record.get("location") or record.get("city")
    country = record.get("country") or record.get("country_code") or record.get("countryCode")
    if not all(isinstance(v, str) and v.strip() for v in (title, employer, link, location)):
        return None
    if not _verified_benin(country) or _is_remote(record):
        return None
    # Preserve the vendor's own page and attribution; never convert a third
    # party or unknown URL into an application destination.
    url = urlparse(link)
    if url.scheme != "https" or url.hostname not in {"devglobaljobs.com", "www.devglobaljobs.com"}:
        return None
    # Require explicit local place evidence; 'Remote' is not a location.
    loc = location.strip()
    if loc.casefold() in {"remote", "worldwide", "anywhere"}:
        return None
    key = record.get("id") or record.get("slug") or link
    posted = None
    raw_date = record.get("postedAt") or record.get("posted_at") or record.get("posted")
    if isinstance(raw_date, str):
        try:
            posted = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=UTC)
        except ValueError:
            pass
    description = str(record.get("description") or record.get("summary") or "")
    description = re.sub(r"<[^>]*>", " ", description)
    description = re.sub(r"\s+", " ", description).strip()
    return JSearchJob(
        provider_job_id=str(key), title=title.strip(), company=employer.strip(),
        location=loc, description=description[:25000],
        apply_url=link, posted_at=posted,
        salary_min=None, salary_max=None, salary_currency=None,
        employment_type=str(record.get("employment_type") or record.get("type") or "") or None,
        remote_status="HYBRID" if str(record.get("workArrangement") or "").casefold() == "hybrid" else None,
        source=SOURCE,
    )


async def search_benin_local_jobs(
    query: str,
    location: str | None = None,
    max_results: int = 20,
) -> list[JSearchJob]:
    """Search without API keys, rate-bounded and explicitly non-commercial.

    Returns only rows with an explicit Benin country field, local location,
    and a vendor-owned destination. Unknown geographic claims are excluded.
    """
    params: dict[str, str | int] = {
        "country": "bj",
        "search": query.strip(),
        "limit": min(MAX_RESULTS, max(1, max_results)),
    }
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(API_URL, params=params)
    except httpx.TimeoutException as exc:
        raise JSearchError("Benin job feed timed out", 504) from exc
    except httpx.HTTPError as exc:
        raise JSearchError("Benin job feed unavailable", 502) from exc
    if response.status_code == 429:
        raise JSearchError("Benin job feed rate limit reached", 429)
    if response.status_code != 200:
        raise JSearchError("Benin job feed unavailable", 502)
    try:
        payload = response.json()
    except ValueError as exc:
        raise JSearchError("Invalid Benin job feed response", 502) from exc

    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, dict):
        rows = payload.get("jobs")
        if rows is None:
            rows = payload.get("data")
        if isinstance(rows, dict):
            rows = rows.get("jobs")
    else:
        rows = None
    if not isinstance(rows, list):
        raise JSearchError("Unexpected Benin job feed response", 502)

    sought = (location or "").strip().casefold()
    results: list[JSearchJob] = []
    for record in rows[:MAX_RESULTS]:
        job = _safe_job(record)
        if job is None:
            continue
        if sought and sought not in job.location.casefold():
            continue
        results.append(job)
        if len(results) >= max_results:
            break
    return results
