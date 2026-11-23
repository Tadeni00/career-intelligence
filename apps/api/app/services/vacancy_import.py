"""User-confirmed vacancy import from pasted text and/or original job URL.

No server-side fetching. This prevents SSRF, bypassing portal access terms,
or mistakenly treating arbitrary webpage text as a verified live vacancy.
"""
from __future__ import annotations

from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job


class VacancyImportRequest(BaseModel):
    title: str = Field(min_length=2, max_length=255)
    company: str = Field(min_length=2, max_length=255)
    location: str = Field(min_length=2, max_length=255)
    url: str | None = Field(default=None, max_length=2048)
    description: str = Field(min_length=30, max_length=50000)
    remote_status: str | None = Field(default=None, max_length=40)

    @field_validator("title", "company", "location", "description")
    @classmethod
    def nonblank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Field cannot be blank")
        return value

    @field_validator("remote_status")
    @classmethod
    def allowed_arrangement(cls, value: str | None) -> str | None:
        if value not in (None, "ONSITE", "HYBRID", "REMOTE", "UNKNOWN"):
            raise ValueError("Unknown work arrangement")
        return value


def normalized_job_url(raw: str) -> str:
    """Only HTTPS original links, no local/network retrieval or credentials."""
    raw = raw.strip()
    try:
        parsed = urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise HTTPException(422, "Invalid job URL") from exc
    if (parsed.scheme.lower() != "https" or not hostname
            or parsed.username is not None or parsed.password is not None
            or any(ord(ch) < 32 for ch in raw)):
        raise HTTPException(422, "Job URL must use public HTTPS without credentials")
    if port not in (None, 443):
        raise HTTPException(422, "Job URL must use standard HTTPS port")
    # URL is a reference only: never fetched. Disallow user-info & fragments.
    host = hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".localhost"):
        raise HTTPException(422, "Job URL must point to an original public posting")
    filtered = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                if not k.lower().startswith("utm_")]
    return urlunsplit(("https", host, parsed.path or "/", urlencode(filtered), ""))


def import_verified_vacancy(db: Session, payload: VacancyImportRequest) -> tuple[Job, bool]:
    """Save one user-reviewed record, idempotent on identical original URL."""
    url = normalized_job_url(payload.url) if payload.url else None
    if url:
        existing = db.execute(select(Job).where(Job.url == url)).scalars().first()
        if existing:
            # Do not silently overwrite earlier user edits or provider data.
            return existing, False

    job = Job(
        title=payload.title, company=payload.company,
        location=payload.location, url=url,
        description=payload.description,
        source="manual_import", is_discovered=False,
        remote_status=payload.remote_status if payload.remote_status != "UNKNOWN" else None,
        requirements_extracted=False,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job, True
