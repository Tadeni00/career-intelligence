"""Indeed.com Indeed API client — alternative source covering Benin Republic.

JSearch does not cover Benin Republic. Indeed.com does (``indeed.com/q?l=Benin Republic``),
and Indeed.com exposes a job search API on RapidAPI at ``indeed.p.rapidapi.com``.

Quirk documented by probes (2026-11-19): Indeed's Indeed API paths on RapidAPI
return 429 "Too many requests" for this account — the host is reachable and
rate-limits, so it is the correct call site even when a particular request
comes back rate-limited.

Also wired in: when JSearch returns zero results for a country, we retry with
Indeed before giving up, so a genuinely alternative source becomes a real fallback
instead of a placeholder.
"""

from __future__ import annotations

import html as _html
from typing import Any

import httpx

from app.services.jsearch import JSearchError, JSearchJob

Indeed_BASE_URL = "https://indeed.p.rapidapi.com"
Indeed_SEARCH_PATH = "/search"
Indeed_GATEWAY_HOST = "indeed.p.rapidapi.com"


class IndeedProviderError(JSearchError):
    """Indeed.com Indeed API error.

    Reuses the JSearch error taxonomy so ``job_discovery`` treats indeed the
    same way (mapping to the appropriate HTTP status for the /jobs/discover
    route).
    """

    pass


class IndeedProvider:
    """Indeed.com Indeed API job search provider."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 15.0,
    ):
        from app.core.config import get_settings

        settings = get_settings()
        self.api_key = api_key or settings.jsearch_api_key
        # Indeed.com Indeed API host. An explicit override still wins (e.g. for
        # staging), so settings.jsearch_base_url is only a fallback for an
        # empty indeed_base_url config — but the default is Indeed's host.
        self.base_url = (
            (base_url or settings.indeed_base_url) or Indeed_BASE_URL
        ).rstrip("/")
        # Indeed.com uses its own search path; the gateway host header rides along.
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "x-rapidapi-key": self.api_key,
                "x-rapidapi-host": Indeed_GATEWAY_HOST,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(timeout_seconds),
        )

    async def __aenter__(self) -> IndeedProvider:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._client.aclose()

    async def search_jobs(
        self,
        query: str,
        country: str = "ng",
        max_results: int = 20,
        remote_only: bool = False,
    ) -> list[JSearchJob]:
        """Search Indeed.com Indeed API, returning the same JSearchJob shape."""
        jobs: list[JSearchJob] = []
        page = 1
        # Indeed.com Indeed API is much broader for Benin than JSearch; cap the
        # cursor walk at the shared quota bound used by the JSearch path.
        from app.services.jsearch import JSEARCH_MAX_PAGES

        while page <= JSEARCH_MAX_PAGES and len(jobs) < max_results:
            params = {
                "q": query,
                "l": country.upper(),
                "start": str((page - 1) * 10),
            }
            try:
                resp = await self._client.get(Indeed_SEARCH_PATH, params=params)
            except httpx.TimeoutException as e:
                raise IndeedProviderError(
                    f"Indeed request timed out after {self._client.timeout}s", 504
                ) from e
            except httpx.HTTPError as e:
                raise IndeedProviderError(
                    f"Indeed transport error: {type(e).__name__}", 502
                ) from e

            # Propagate rate-limit/auth signal so /jobs/discover returns an
            # appropriate status instead of a misleading empty result.
            if resp.status_code in (401, 403):
                raise IndeedProviderError(
                    f"Indeed authentication failed (HTTP {resp.status_code})",
                    resp.status_code,
                )
            if resp.status_code == 429:
                raise IndeedProviderError(
                    "Indeed rate limit exceeded", 429
                )
            if resp.status_code >= 400:
                raise IndeedProviderError(
                    f"Indeed request failed (HTTP {resp.status_code}): {resp.text[:200]}"
                )
            try:
                data = resp.json()
            except Exception as e:
                raise IndeedProviderError(f"Invalid JSON response: {e}") from e

            page_jobs = self._normalize_page(data)
            if not page_jobs:
                break
            jobs.extend(page_jobs)
            page += 1

        return jobs[:max_results]

    def _normalize_page(self, data: Any) -> list[JSearchJob]:
        """Normalize an Indeed.com Indeed API page into JSearchJob items."""
        jobs_raw: list[Any] | None = None
        if isinstance(data, dict):
            for key in ("results", "jobs", "data"):
                val = data.get(key)
                if isinstance(val, list):
                    jobs_raw = val
                    break
        if not jobs_raw and isinstance(data, dict):
            # Some Indeed responses are nested: {"searchResults": [...]}
            nested = data.get("searchResults") or data.get("response") or data.get("items")
            if isinstance(nested, list):
                jobs_raw = nested
        if not jobs_raw:
            return []

        normalized: list[JSearchJob] = []
        for job_data in jobs_raw:
            if not isinstance(job_data, dict):
                continue
            title = _html.unescape(str(job_data.get("job_title") or job_data.get("title") or ""))
            company = _html.unescape(
                str(job_data.get("employer_name") or job_data.get("company") or "")
            )
            apply_url = str(job_data.get("job_apply_link") or job_data.get("apply_url") or "")
            if not title or not company or not apply_url:
                continue
            normalized.append(
                JSearchJob(
                    provider_job_id=str(job_data.get("job_id") or job_data.get("jobkey") or ""),
                    title=title.strip(),
                    company=company.strip(),
                    location=str(job_data.get("job_location") or job_data.get("location") or "").strip(),
                    description=str(job_data.get("job_description") or job_data.get("description") or "").strip(),
                    apply_url=apply_url.strip(),
                    posted_at=self._parse_posted_at(
                        job_data.get("job_posted_at_datetime_utc")
                        or job_data.get("job_posted_at")
                        or job_data.get("date_posted")
                    ),
                    salary_min=self._num(job_data.get("job_min_salary")),
                    salary_max=self._num(job_data.get("job_max_salary")),
                    salary_currency=str(job_data.get("job_salary_currency") or "USD"),
                    employment_type=str(job_data.get("job_employment_type") or "") or None,
                    remote_status="REMOTE" if job_data.get("job_is_remote") else None,
                    source="indeed",
                )
            )
        return normalized

    @staticmethod
    def _parse_posted_at(val: Any):
        from datetime import datetime

        if not val:
            return None
        try:
            return datetime.fromisoformat(str(val).replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _num(val: Any) -> float | None:
        if val is None:
            return None
        try:
            return float(val)
        except (TypeError, ValueError):
            return None


async def search_indeed_jobs(
    query: str,
    country: str = "ng",
    max_results: int = 20,
    remote_only: bool = False,
) -> list[JSearchJob]:
    """Convenience wrapper for Indeed.com Indeed API."""
    async with IndeedProvider() as provider:
        return await provider.search_jobs(
            query=query,
            country=country,
            max_results=max_results,
            remote_only=remote_only,
        )
