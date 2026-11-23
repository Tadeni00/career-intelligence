"""Read-only preview of user-supplied Greenhouse or Lever public job URLs.

Strict URL parser constructs requests only to documented ATS JSON API hosts.
Never fetch user-supplied hosts, follow redirects, resolve arbitrary URLs,
submit applications, or persist a preview without user confirmation.
"""
from __future__ import annotations

import html
import re
from urllib.parse import urlsplit

import httpx

from app.services.jsearch import JSearchError

_SEGMENT = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
_JOB_ID = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")
_ALLOWED = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.eu.lever.co": "lever_eu",
}
_API_HOSTS = {
    "greenhouse": "boards-api.greenhouse.io",
    "lever": "api.lever.co",
    "lever_eu": "api.eu.lever.co",
}
_MAX_BYTES = 250_000


def identify_job_url(raw_url: str) -> tuple[str, str, str]:
    """Return (provider, site token, job id) for an exact official posting URL."""
    if len(raw_url) > 2048 or not raw_url:
        raise JSearchError("Please provide a supported job URL", 422)
    try:
        url = urlsplit(raw_url.strip())
        host = (url.hostname or "").lower()
        port = url.port
    except ValueError as exc:
        raise JSearchError("Invalid job URL", 422) from exc
    if (url.scheme != "https" or url.username or url.password or
            port not in (None, 443) or host not in _ALLOWED):
        raise JSearchError("Only direct Greenhouse and Lever HTTPS job URLs are supported", 422)
    parts = url.path.strip("/").split("/")
    provider = _ALLOWED[host]
    if provider == "greenhouse":
        if len(parts) != 3 or parts[1] != "jobs" or not parts[2].isdigit():
            raise JSearchError("Provide a direct Greenhouse job URL", 422)
    elif len(parts) != 2:
        raise JSearchError("Provide a direct Lever job URL", 422)
    site = parts[0]
    job_id = parts[-1]
    if not _SEGMENT.fullmatch(site) or not _JOB_ID.fullmatch(job_id):
        raise JSearchError("Unrecognized job URL path", 422)
    return provider, site, job_id


def _text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    # Convert escaped HTML then remove markup. Data is returned as plain text,
    # never rendered as HTML. Limit user-visible output to existing input bounds.
    value = html.unescape(html.unescape(value))
    value = re.sub(r"<(script|style)\b[^>]*>[\s\S]*?</\1\s*>", " ", value, flags=re.I)
    value = re.sub(r"<[^>]*>", " ", value)
    return re.sub(r"\s+", " ", value).strip()[:50000]


def normalize_ats_job(data: object, provider: str, site: str, job_id: str) -> dict:
    """Normalize only explicit, source-provided fields into an unverified draft."""
    if not isinstance(data, dict):
        raise JSearchError("Job provider returned unexpected content", 502)
    if provider == "greenhouse":
        actual_id = data.get("id")
        if str(actual_id) != job_id:
            raise JSearchError("Job identity mismatch from provider", 502)
        title = _text(data.get("title"))
        employer = _text(data.get("company_name"))
        loc = data.get("location")
        location = _text(loc.get("name")) if isinstance(loc, dict) else ""
        description = _text(data.get("content"))
        arrangement = "UNKNOWN"
    else:
        if str(data.get("id", "")) != job_id:
            raise JSearchError("Job identity mismatch from provider", 502)
        title = _text(data.get("text"))
        employer = ""  # Lever's posting payload does not reliably name employer.
        categories = data.get("categories")
        location = _text(categories.get("location")) if isinstance(categories, dict) else ""
        description = _text(data.get("descriptionPlain") or data.get("description"))
        status = str(data.get("workplaceType") or "").lower()
        arrangement = {"remote": "REMOTE", "on-site": "ONSITE", "hybrid": "HYBRID"}.get(status, "UNKNOWN")
    if not title or len(description) < 30:
        raise JSearchError("Posting lacks usable title or job description", 422)
    host = _API_HOSTS[provider]
    return {
        "title": title[:255],
        "company": employer[:255],
        "location": location[:255],
        "description": description,
        "remote_status": arrangement,
        "source": f"{provider} public job API ({host})",
        "warnings": [
            "Review title, employer, workplace, work arrangement, and application deadline before saving.",
            "Imported preview is not evidence that the vacancy is still open or available in Benin.",
        ],
    }


async def preview_public_job_url(raw_url: str) -> dict:
    provider, site, job_id = identify_job_url(raw_url)
    api_host = _API_HOSTS[provider]
    if provider == "greenhouse":
        path = f"/v1/boards/{site}/jobs/{job_id}"
    else:
        path = f"/v0/postings/{site}/{job_id}"
    try:
        async with httpx.AsyncClient(
            base_url=f"https://{api_host}",
            timeout=httpx.Timeout(10),
            follow_redirects=False,
            trust_env=False,
        ) as client:
            resp = await client.get(path, headers={"Accept": "application/json"})
    except httpx.TimeoutException as exc:
        raise JSearchError("Job provider timed out", 504) from exc
    except httpx.HTTPError as exc:
        raise JSearchError("Job provider unavailable", 502) from exc
    if resp.status_code == 404:
        raise JSearchError("The posting was not found at its public source", 404)
    if resp.status_code == 429:
        raise JSearchError("Job provider rate limit reached", 429)
    if resp.status_code != 200:
        raise JSearchError("Job provider could not return a valid posting", 502)
    if len(resp.content) > _MAX_BYTES:
        raise JSearchError("Job provider response is too large", 502)
    try:
        body = resp.json()
    except ValueError as exc:
        raise JSearchError("Job provider returned invalid JSON", 502) from exc
    return normalize_ats_job(body, provider, site, job_id)
