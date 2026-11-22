"""JSearch job search provider.

Client for the JSearch API via the RapidAPI gateway. Verified live 2026-10-13:
base ``https://jsearch.p.rapidapi.com``, path ``/search-v2``, auth via
``X-RapidAPI-Key``/``X-RapidAPI-Host`` headers, response envelope
``{"status", "request_id", "parameters", "data": {"jobs": [...], "cursor": ...}}``.
Handles authentication, request/response normalization, error handling, and
rate limiting. The API key is read from settings (env) and never logged.
"""

from __future__ import annotations

import html as _html
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx

from app.core.config import get_settings

# Verified RapidAPI gateway contract (smoke-tested 2026-10-13).
JSEARCH_GATEWAY_BASE_URL = "https://jsearch.p.rapidapi.com"
JSEARCH_GATEWAY_HOST = "jsearch.p.rapidapi.com"
JSEARCH_SEARCH_PATH = "/search-v2"
JSEARCH_DETAILS_PATH = "/job-details"

# JSearch returns roughly this many results per page.
JSEARCH_PAGE_SIZE = 10
# Hard cap on pages per search call so one request cannot burn quota.
JSEARCH_MAX_PAGES = 5


@dataclass
class JSearchJob:
    """Normalized job from JSearch API."""

    provider_job_id: str
    title: str
    company: str
    location: str
    description: str
    apply_url: str
    posted_at: datetime | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    employment_type: str | None
    remote_status: str | None
    source: str = "jsearch"


class JSearchError(Exception):
    """Base exception for JSearch errors."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class JSearchAuthError(JSearchError):
    """Authentication failed (401/403)."""

    def __init__(self, message: str = "JSearch authentication failed"):
        super().__init__(message, 401)


class JSearchRateLimitError(JSearchError):
    """Rate limit exceeded (429)."""

    def __init__(self, message: str = "JSearch rate limit exceeded", retry_after: int | None = None):
        super().__init__(message, 429)
        self.retry_after = retry_after


class JSearchProviderError(JSearchError):
    """Provider error (5xx)."""

    def __init__(self, message: str = "JSearch provider error", status_code: int | None = None):
        super().__init__(message, status_code)


class JSearchClient:
    """Client for the JSearch API via the RapidAPI gateway."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float = 15.0,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.jsearch_api_key
        # Default to the verified RapidAPI gateway; env may override it.
        self.base_url = (base_url or settings.jsearch_base_url or JSEARCH_GATEWAY_BASE_URL).rstrip("/")
        self.timeout_seconds = timeout_seconds

        if not self.api_key:
            raise JSearchError("JSearch API key not configured")

        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "X-RapidAPI-Key": self.api_key,
                "X-RapidAPI-Host": JSEARCH_GATEWAY_HOST,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(self.timeout_seconds),
        )

    async def __aenter__(self) -> "JSearchClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self._client.aclose()

    def _handle_response(self, response: httpx.Response) -> dict[str, Any]:
        """Handle HTTP response, raise appropriate exceptions.

        Provider bodies are truncated before they ever reach an error message
        so nothing sensitive or unbounded propagates to API responses or logs.
        """
        if response.status_code == 401 or response.status_code == 403:
            raise JSearchAuthError("JSearch authentication failed (invalid or missing API key)")
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_after_int = int(retry_after) if retry_after and retry_after.isdigit() else None
            raise JSearchRateLimitError("JSearch rate limit exceeded", retry_after=retry_after_int)
        if 500 <= response.status_code < 600:
            raise JSearchProviderError(
                f"JSearch provider error (HTTP {response.status_code}): {response.text[:200]}",
                response.status_code,
            )
        if response.status_code >= 400:
            raise JSearchError(
                f"JSearch request failed (HTTP {response.status_code}): {response.text[:200]}",
                response.status_code,
            )

        try:
            data = response.json()
        except Exception as e:
            raise JSearchError(f"Invalid JSON response: {e}")
        if not isinstance(data, dict):
            raise JSearchError("Unexpected JSearch response shape (not an object)")
        return data

    @staticmethod
    def _response_items(data: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract the job list from the ``data`` envelope.

        Live shape: ``{"jobs": [...], "cursor": ...}``. Tolerant of a bare
        list for forward/backward compatibility.
        """
        payload = data.get("data")
        if isinstance(payload, dict):
            jobs = payload.get("jobs")
        elif isinstance(payload, list):
            jobs = payload
        else:
            jobs = None
        if not isinstance(jobs, list):
            return []
        return [j for j in jobs if isinstance(j, dict)]

    async def search_jobs(
        self,
        query: str,
        country: str = "us",
        page: int = 1,
        num_pages: int = 1,
        language: str = "en",
        date_posted: str = "all",
        remote_only: bool = False,
    ) -> list[JSearchJob]:
        """Search for jobs using the JSearch API.

        Args:
            query: Free-form search query (e.g., "software engineer")
            country: ISO 3166-1 alpha-2 country code (e.g., "ng" for Nigeria)
            page: Page number (default: 1)
            num_pages: Number of pages to fetch (default: 1)
            language: Language code (default: "en")
            date_posted: Filter by posting date ("all", "today", "3days", "week", "month")
            remote_only: Only return remote jobs

        Returns:
            List of normalized JSearchJob objects
        """
        params = {
            "query": query,
            "country": country.lower(),
            "page": str(page),
            "num_pages": str(num_pages),
            "language": language,
            "date_posted": date_posted,
        }

        try:
            response = await self._client.get(JSEARCH_SEARCH_PATH, params=params)
        except httpx.TimeoutException as e:
            raise JSearchError(f"JSearch request timed out after {self.timeout_seconds:g}s", 504) from e
        except httpx.HTTPError as e:
            raise JSearchError(f"JSearch transport error: {type(e).__name__}", 502) from e
        data = self._handle_response(response)

        jobs = []
        for job_data in self._response_items(data):
            job = self._normalize_job(job_data)
            if job is None:
                continue
            if remote_only and not job_data.get("job_is_remote"):
                continue
            jobs.append(job)

        return jobs

    async def get_job_details(self, job_id: str) -> JSearchJob | None:
        """Get detailed information for a specific job."""
        try:
            response = await self._client.get(JSEARCH_DETAILS_PATH, params={"job_id": job_id})
        except httpx.TimeoutException as e:
            raise JSearchError(f"JSearch request timed out after {self.timeout_seconds:g}s", 504) from e
        except httpx.HTTPError as e:
            raise JSearchError(f"JSearch transport error: {type(e).__name__}", 502) from e
        data = self._handle_response(response)

        items = self._response_items(data)
        if not items:
            return None

        return self._normalize_job(items[0])

    def _parse_posted_at(self, posted_at: str | None) -> datetime | None:
        """Parse posted_at string to datetime."""
        if not posted_at:
            return None
        try:
            # JSearch returns ISO format: "2024-01-15T10:30:00Z"
            return datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
        except Exception:
            return None

    def _normalize_job(self, job_data: dict[str, Any]) -> JSearchJob | None:
        """Normalize JSearch job data to internal representation."""
        try:
            job_id = str(job_data.get("job_id") or "")
            if not job_id:
                return None

            # Titles/descriptions arrive with HTML entities (e.g. &#8211;).
            title = _html.unescape(str(job_data.get("job_title") or job_data.get("title") or ""))
            company = str(job_data.get("employer_name") or job_data.get("company") or "")
            location = str(job_data.get("job_location") or "")
            if not location:
                # Fall back to structured city/state/country fields.
                parts = [
                    str(job_data.get("job_city") or "").strip(),
                    str(job_data.get("job_state") or "").strip(),
                    str(job_data.get("job_country") or "").strip(),
                ]
                location = ", ".join(p for p in parts if p)
            description = str(job_data.get("job_description") or job_data.get("description") or "")
            apply_url = str(job_data.get("job_apply_link") or job_data.get("apply_url") or "")

            # Parse posted date
            posted_at_str = job_data.get("job_posted_at_datetime_utc") or job_data.get("job_posted_at") or job_data.get("date_posted")
            posted_at = self._parse_posted_at(posted_at_str)

            # Salary
            salary_min = job_data.get("job_min_salary")
            salary_max = job_data.get("job_max_salary")
            salary_currency = job_data.get("job_salary_currency") or "USD"

            # Employment type
            employment_type = job_data.get("job_employment_type")

            # Remote status
            is_remote = job_data.get("job_is_remote")
            remote_status = "REMOTE" if is_remote else None

            # Validate required fields
            if not title or not company or not apply_url:
                return None

            # Validate URL
            if not self._is_valid_url(apply_url):
                return None

            return JSearchJob(
                provider_job_id=job_id,
                title=title.strip(),
                company=company.strip(),
                location=location.strip() if location else "",
                description=description.strip() if description else "",
                apply_url=apply_url.strip(),
                posted_at=posted_at,
                salary_min=float(salary_min) if salary_min is not None else None,
                salary_max=float(salary_max) if salary_max is not None else None,
                salary_currency=salary_currency,
                employment_type=employment_type,
                remote_status=remote_status,
            )
        except Exception:
            return None

    def _is_valid_url(self, url: str) -> bool:
        """Validate that a string is a valid HTTP/HTTPS URL."""
        try:
            parsed = httpx.URL(url)
            return parsed.scheme in ("http", "https") and bool(parsed.host)
        except Exception:
            return False


async def search_jsearch_jobs(
    query: str,
    country: str = "ng",
    page: int = 1,
    num_pages: int = 1,
    remote_only: bool = False,
) -> list[JSearchJob]:
    """Convenience function to search JSearch jobs."""
    async with JSearchClient() as client:
        return await client.search_jobs(
            query=query,
            country=country,
            page=page,
            num_pages=num_pages,
            remote_only=remote_only,
        )