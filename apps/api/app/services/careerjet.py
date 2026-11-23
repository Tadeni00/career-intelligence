"""Opt-in Optioncarriere/Careerjet publisher search for Benin.

Official API: https://www.optioncarriere.bj/partners/api/python
Requires approved publisher key, registered referral URL, the *real* user's
public IP and user-agent. Never fabricate or infer those from a Docker proxy.
Not a substitute for the separately licensed high-volume Job Data API.
"""
from __future__ import annotations

import hashlib
import html
import ipaddress
import re
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx

from app.services.jsearch import JSearchError, JSearchJob

SEARCH_URL = "https://search.api.careerjet.net/v4/query"
SOURCE = "careerjet"
MAX_PAGE_SIZE = 50


@dataclass(frozen=True)
class CareerjetCredentials:
    publisher_key: str
    user_ip: str
    user_agent: str
    referer: str

    @classmethod
    def from_settings(cls, settings) -> CareerjetCredentials | None:
        values = (
            settings.careerjet_publisher_key,
            settings.careerjet_user_ip,
            settings.careerjet_user_agent,
            settings.careerjet_referer,
        )
        if not all(isinstance(v, str) and v.strip() for v in values):
            # A partial configuration is intentionally *not* sent upstream.
            return None
        return cls(*(str(v).strip() for v in values))

    def validate(self) -> None:
        try:
            address = ipaddress.ip_address(self.user_ip)
        except ValueError as exc:
            raise JSearchError("Careerjet publisher requester IP configuration is invalid", 503) from exc
        if not address.is_global:
            raise JSearchError("Careerjet publisher requester IP must be a real public IP", 503)
        uri = urlparse(self.referer)
        if uri.scheme != "https" or not uri.hostname or uri.username or uri.password:
            raise JSearchError("Careerjet publisher referral URL must be a registered HTTPS page", 503)
        if len(self.user_agent) < 6 or len(self.user_agent) > 500:
            raise JSearchError("Careerjet requester browser user-agent is invalid", 503)


def _date(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return parsedate_to_datetime(value)
    except (ValueError, TypeError, IndexError):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None


def _number(value: object) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    return float(value)


def _normalize(row: object) -> JSearchJob | None:
    if not isinstance(row, dict):
        return None
    title, company = row.get("title"), row.get("company")
    location = row.get("locations")
    url = row.get("url")
    if not all(isinstance(v, str) and v.strip() for v in (title, company, location, url)):
        return None
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return None
    # Careerjet provides referral URLs on jobviewtrack.com and its own domains.
    if hostname not in {"jobviewtrack.com", "www.jobviewtrack.com", "optioncarriere.bj", "www.optioncarriere.bj"} and not (hostname == "careerjet.com" or hostname.endswith(".careerjet.com")):
        return None
    # Omit postings explicitly marked remote. Other arrangements stay unknown:
    # a non-remote source does NOT prove an on-site job.
    if re.search(r"\b(remote|télétravail|teletravail)\b", location, re.I):
        return None
    identifier = row.get("job_id")
    if not isinstance(identifier, str) or not identifier.strip():
        identifier = hashlib.sha256(url.encode("utf-8")).hexdigest()
    desc = html.unescape(re.sub(r"<[^>]+>", " ", str(row.get("description") or "")))
    return JSearchJob(
        provider_job_id=identifier, source=SOURCE,
        title=html.unescape(title).strip(), company=html.unescape(company).strip(),
        location=html.unescape(location).strip(),
        description=re.sub(r"\s+", " ", desc).strip()[:25000],
        apply_url=url, posted_at=_date(row.get("date")),
        # Existing database does not persist salary currency/period:
        # preserve no numeric salary rather than making a misleading claim.
        salary_min=None, salary_max=None, salary_currency=None,
        employment_type=None, remote_status=None,
    )


async def search_careerjet_benin_jobs(
    query: str, location: str | None, max_results: int,
    credentials: CareerjetCredentials,
) -> list[JSearchJob]:
    """Search only Benin locale with honest requester metadata and bounded cost."""
    credentials.validate()
    params: dict[str, str | int] = {
        "locale_code": "fr_BJ", "keywords": query.strip(),
        "user_ip": credentials.user_ip, "user_agent": credentials.user_agent,
        "page_size": max(1, min(MAX_PAGE_SIZE, max_results)), "page": 1,
    }
    if location and location.strip():
        params["location"] = location.strip()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(
                SEARCH_URL, params=params,
                auth=httpx.BasicAuth(credentials.publisher_key, ""),
                headers={"Referer": credentials.referer, "Accept": "application/json"},
            )
    except httpx.TimeoutException as exc:
        raise JSearchError("Careerjet publisher search timed out", 504) from exc
    except httpx.HTTPError as exc:
        raise JSearchError("Careerjet publisher search unavailable", 502) from exc
    if response.status_code in (401, 403):
        raise JSearchError("Careerjet publisher access or requester metadata not accepted", 503)
    if response.status_code == 429:
        raise JSearchError("Careerjet publisher rate limit reached", 429)
    if response.status_code != 200:
        raise JSearchError("Careerjet publisher search failed", 502)
    try:
        body = response.json()
    except ValueError as exc:
        raise JSearchError("Careerjet publisher response was invalid JSON", 502) from exc
    if not isinstance(body, dict):
        raise JSearchError("Careerjet publisher response format invalid", 502)
    if body.get("type") == "LOCATIONS":
        # Ambiguous or unresolved location is not a zero-jobs result.
        raise JSearchError("Careerjet needs a more specific city or location", 422)
    if body.get("type") != "JOBS" or not isinstance(body.get("jobs"), list):
        raise JSearchError("Careerjet publisher response format invalid", 502)
    jobs: list[JSearchJob] = []
    for entry in body["jobs"][:MAX_PAGE_SIZE]:
        normalized = _normalize(entry)
        if normalized is not None:
            jobs.append(normalized)
    return jobs[:max_results]
