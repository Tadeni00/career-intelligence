"""No-key Remotive remote vacancy discovery with conservative geography matching.

Remotive source must be credited and all apply links point to Remotive.
See https://remotive.com/remote-jobs/api for terms and call frequency.
"""
from __future__ import annotations

import re
from datetime import datetime
from html import unescape
from urllib.parse import urlparse

import httpx

from app.services.jsearch import JSearchError, JSearchJob

REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
# Remotive advises a few calls per day and blocks excessive requests.
# Use a small process-local cache; personal local installation, no shared service.
_CACHE_SECONDS = 6 * 60 * 60
_CACHE: dict[str, tuple[float, list[dict]]] = {}

COUNTRY_NAMES = {
    "bj": "benin", "ng": "nigeria", "gh": "ghana", "tg": "togo",
    "ci": "ivory coast", "sn": "senegal", "ke": "kenya", "za": "south africa",
    "us": "united states", "gb": "united kingdom", "ca": "canada",
    "au": "australia", "de": "germany", "fr": "france",
    "nl": "netherlands", "br": "brazil", "pl": "poland",
    "ru": "russia", "sg": "singapore", "mx": "mexico",
    "it": "italy", "at": "austria",
}
AFRICA = {"bj", "ng", "gh", "tg", "ci", "sn", "ke", "za"}
WEST_AFRICA = {"bj", "ng", "gh", "tg", "ci", "sn"}


def eligible_remote_region(required_location: str | None, country: str) -> bool:
    """Only obvious matches; ambiguous or unstated restrictions aren't eligibility proof."""
    if not required_location or not required_location.strip():
        return False
    required = required_location.casefold()
    parts = re.split(r"[,;/|]|\bor\b", required)
    name = COUNTRY_NAMES.get(country.lower())
    for part in parts:
        part = part.strip(" .()")
        if part in {"worldwide", "anywhere", "global", "anywhere in the world"}:
            return True
        if name and (part == name or part == country.lower()):
            return True
        if country.lower() == "bj" and part in {"benin republic", "république du bénin"}:
            return True
        if country.lower() in AFRICA and part == "africa":
            return True
        if country.lower() in WEST_AFRICA and part in {"west africa", "western africa"}:
            return True
    return False


def _to_job(item: object) -> JSearchJob | None:
    if not isinstance(item, dict):
        return None
    job_id, title, company, url = (item.get(key) for key in ("id", "title", "company_name", "url"))
    if not job_id or not title or not company or not isinstance(url, str):
        return None
    uri = urlparse(url)
    if uri.scheme != "https" or uri.hostname not in {"remotive.com", "www.remotive.com"}:
        return None
    posted = None
    if isinstance(item.get("publication_date"), str):
        try:
            posted = datetime.fromisoformat(item["publication_date"].replace("Z", "+00:00"))
        except ValueError:
            pass
    # Never guess numeric salaries from free-form text or silently remove restrictions.
    restrictions = str(item.get("candidate_required_location") or "").strip()
    html_description = str(item.get("description") or "")
    description = re.sub(r"<[^>]+>", " ", html_description)
    description = unescape(re.sub(r"\s+", " ", description)).strip()
    return JSearchJob(
        provider_job_id=str(job_id), title=unescape(str(title)).strip(),
        company=unescape(str(company)).strip(),
        location=f"Remote — {restrictions}",
        description=description[:25000],
        apply_url=url, posted_at=posted,
        salary_min=None, salary_max=None, salary_currency=None,
        employment_type=str(item.get("job_type") or "") or None,
        remote_status="REMOTE", source="remotive",
    )


async def search_remotive_jobs(
    query: str, country: str, max_results: int = 20, remote_only: bool = True,
) -> list[JSearchJob]:
    """Read free remote jobs; no candidate CV sent and no API key required.

    The provider search is keyword-based, so first fetch a bounded broad set
    and filter title/description locally. This preserves geography metadata and
    avoids falsely claiming local Benin vacancies. Cache limits request volume.
    """
    import time

    if not remote_only:
        return []
    now = time.monotonic()
    cached = _CACHE.get("feed")
    if cached and now - cached[0] < _CACHE_SECONDS:
        rows = cached[1]
    else:
        try:
            async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
                response = await client.get(REMOTIVE_URL)
        except httpx.TimeoutException as exc:
            raise JSearchError("Remote job source timed out", 504) from exc
        except httpx.HTTPError as exc:
            raise JSearchError("Remote job source temporarily unavailable", 502) from exc
        if response.status_code == 429:
            raise JSearchError("Remote job source rate-limited requests", 429)
        if response.status_code != 200:
            raise JSearchError("Remote job source temporarily unavailable", 502)
        try:
            data = response.json()
        except ValueError as exc:
            raise JSearchError("Remote job source returned malformed data", 502) from exc
        if not isinstance(data, dict) or not isinstance(data.get("jobs"), list):
            raise JSearchError("Remote job source returned unexpected data", 502)
        rows = data["jobs"][:1000]
        _CACHE["feed"] = (now, rows)

    terms = [token for token in re.findall(r"[\w+#.]+", query.casefold()) if len(token) > 1]
    matches: list[JSearchJob] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        if not eligible_remote_region(item.get("candidate_required_location"), country):
            continue
        text = (str(item.get("title") or "") + " " + str(item.get("description") or "")).casefold()
        if terms and not all(term in text for term in terms):
            continue
        job = _to_job(item)
        if job:
            matches.append(job)
        if len(matches) >= max_results:
            break
    return matches
