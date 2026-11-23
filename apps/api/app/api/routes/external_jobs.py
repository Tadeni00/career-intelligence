"""External job discovery endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_candidate
from app.api.routes.matches import _to_out
from app.db.session import get_db
from app.models import Job
from app.schemas import JobOut
from app.services import application_provenance
from app.services import cv_profile as profile_service
from app.services.job_discovery import discover_jobs
from app.services.jsearch import (
    JSearchAuthError,
    JSearchError,
    JSearchRateLimitError,
)
from app.services.matching import (
    latest_match,
    latest_match_for_profile,
    resolve_matching_input,
)


def _relevance_out(query: str | None, title: str | None) -> SearchRelevanceOut:
    from app.services.search_relevance import classify_search_relevance

    relevance = classify_search_relevance(query, title)
    return SearchRelevanceOut(label=relevance.label, reason=relevance.reason)


def _freshness_out(posted_at, expires_at) -> FreshnessOut:
    from app.services.freshness import assess_freshness

    freshness = assess_freshness(posted_at, expires_at)
    return FreshnessOut(status=freshness.status, reason=freshness.reason)


def _duplicate_out(job, db) -> DuplicateReviewOut:
    from app.services.duplicates import review_job

    review = review_job(job, db)
    return DuplicateReviewOut(
        status=review.status,
        reason=review.reason,
        related_job_ids=list(review.related_job_ids),
    )

router = APIRouter(prefix="/jobs", tags=["jobs-discovery"])


class JobSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200, description="Search query (e.g., 'software engineer')")
    country: str = Field(default="ng", min_length=2, max_length=2, description="ISO 3166-1 alpha-2 country code")
    location: str | None = Field(default=None, max_length=100, description="Optional location filter (city, region)")
    remote_only: bool = Field(default=False, description="Only return remote jobs")
    max_results: int = Field(default=20, ge=1, le=50, description="Maximum number of results")
    cv_profile_id: int | None = Field(
        default=None,
        description=(
            "Match against this confirmed CV profile instead of the shared "
            "Candidate record. Omit for the unchanged legacy behaviour. Only "
            "the search parameters are sent to the job provider; no CV content "
            "is ever transmitted."
        ),
    )


class ShortlistRequest(BaseModel):
    """Optional body for the discovery shortlist endpoint.

    Omitting ``cv_profile_id`` keeps the existing behaviour exactly: a legacy
    application with no profile and no linked match.
    """

    cv_profile_id: int | None = Field(
        default=None,
        description=(
            "Track this shortlist under the given confirmed CV profile. The "
            "profile's own match is linked; an existing application under a "
            "different profile is a conflict and is never reassigned."
        ),
    )


class SearchRelevanceOut(BaseModel):
    """Query-to-title alignment, computed per request — never persisted."""

    label: str
    reason: str


class FreshnessOut(BaseModel):
    """Presentation-only freshness, derived from posting/expiration dates."""

    status: str
    reason: str


class DuplicateReviewOut(BaseModel):
    """Advisory duplicate-review signal; never an identity determination."""

    status: str
    reason: str
    related_job_ids: list[int] = Field(default_factory=list)


class DiscoveredJobOut(BaseModel):
    job: JobOut
    match: dict | None = None
    shortlisted: bool = False
    search_relevance: SearchRelevanceOut | None = None
    freshness: FreshnessOut | None = None
    duplicate_review: DuplicateReviewOut | None = None


class JobSearchResponse(BaseModel):
    jobs: list[DiscoveredJobOut]
    total: int
    query: str
    country: str


@router.post("/discover", response_model=JobSearchResponse)
def discover_jobs_endpoint(
    payload: JobSearchRequest,
    db: Session = Depends(get_db),
    candidate=Depends(current_candidate),
) -> JobSearchResponse:
    """Discover job vacancies from external sources and match against the candidate profile.

    With ``cv_profile_id`` the vacancies are matched against that confirmed
    profile's evidence and every match created here is stamped with it. Without
    it, the shared Candidate record is used exactly as before. An invalid,
    unowned, unconfirmed or archived profile is rejected outright; there is no
    silent fallback to the shared Candidate.
    """
    # Validate country code (basic validation)
    if len(payload.country) != 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Country must be a 2-letter ISO 3166-1 alpha-2 code (e.g., 'ng', 'us', 'gb')",
        )

    # Eligibility is checked once, up front, through the shared service, so a
    # provider call is never made for a request that cannot be honoured.
    if payload.cv_profile_id is not None:
        profile_service.resolve_confirmed_profile(db, candidate, payload.cv_profile_id)

    try:
        jobs = discover_jobs(
            db=db,
            candidate_id=candidate.id,
            query=payload.query,
            country=payload.country.lower(),
            location=payload.location,
            remote_only=payload.remote_only,
            max_results=payload.max_results,
            cv_profile_id=payload.cv_profile_id,
        )
    except JSearchAuthError:
        # Server-side credential problem; never expose key material.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job provider authentication failed. The service is temporarily unavailable.",
        )
    except JSearchRateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Job provider rate limit reached. Please try again shortly.",
            headers={"Retry-After": str(exc.retry_after)} if exc.retry_after else None,
        )
    except JSearchError as exc:
        # Alternative providers may use JSearchError without its specialized
        # subclasses. Preserve actionable auth/quota statuses for the UI.
        if exc.status_code == 429:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Job provider rate limit reached. Please try again later.",
            ) from exc
        if exc.status_code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Job provider authentication failed. The service is temporarily unavailable.",
            ) from exc
        status_code = exc.status_code if exc.status_code in (502, 504) else status.HTTP_502_BAD_GATEWAY
        raise HTTPException(
            status_code=status_code,
            detail="Job provider request failed. Please try again shortly.",
        ) from exc

    return JobSearchResponse(
        jobs=jobs,
        total=len(jobs),
        query=payload.query,
        country=payload.country.upper(),
    )


@router.get("/discovered/{job_id}", response_model=DiscoveredJobOut)
def get_discovered_job(
    job_id: int,
    db: Session = Depends(get_db),
    candidate=Depends(current_candidate),
    query: str | None = Query(default=None, max_length=200,
                              description="Current search text used for the relevance signal"),
    cv_profile_id: int | None = Query(
        default=None,
        description=(
            "Return only the match this CV profile produced. Omit for the "
            "unchanged legacy lookup."
        ),
    ),
) -> DiscoveredJobOut:
    """Get a discovered job with its match explanation."""
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    if cv_profile_id is not None:
        # Ownership is resolved before lookup, so a profile id cannot reach
        # another candidate's data and a scoped request never returns a
        # historical null-profile result.
        resolve_matching_input(db, candidate, cv_profile_id)
        match = latest_match_for_profile(db, job_id, cv_profile_id)
    else:
        match = latest_match(db, job_id)

    # Serialized through the same boundary the /matches endpoints use.
    # MatchResult keeps its item collections in Text columns, so validating the
    # ORM object directly hands Pydantic a str where MatchOut declares a list
    # and raises; _to_out decodes them into the declared shape.
    match_out = _to_out(match) if match is not None else None

    from app.models import Application as _Application

    shortlisted = (
        db.execute(
            select(_Application).where(
                _Application.candidate_id == candidate.id,
                _Application.job_id == job_id,
            )
        ).scalars().first()
        is not None
    )

    return DiscoveredJobOut(
        job=JobOut.model_validate(job),
        match=match_out.model_dump() if match_out else None,
        shortlisted=shortlisted,
        search_relevance=_relevance_out(query, job.title),
        freshness=_freshness_out(job.posted_at, job.expires_at),
        duplicate_review=_duplicate_out(job, db),
    )


@router.post("/discovered/{job_id}/shortlist", status_code=status.HTTP_201_CREATED)
def shortlist_job(
    job_id: int,
    payload: ShortlistRequest | None = None,
    db: Session = Depends(get_db),
    candidate=Depends(current_candidate),
) -> dict:
    """Shortlist a discovered job by creating an application in INTERESTED state.

    With no body this is the unchanged legacy behaviour: one application, no
    profile, no linked match, and a repeat request is idempotent.

    With ``cv_profile_id`` the profile is validated through the shared
    eligibility service and the application's provenance is set to it, linking
    that profile's own match. An existing application recorded under a different
    profile is a conflict and is never reassigned; a repeat request under the
    same profile stays idempotent. The one-application-per-candidate-per-vacancy
    constraint is unchanged.
    """
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    from app.models import Application, ApplicationStatus

    requested_profile = payload.cv_profile_id if payload else None

    existing = db.execute(
        select(Application).where(
            Application.candidate_id == candidate.id,
            Application.job_id == job_id,
        )
    ).scalars().first()

    if existing is not None:
        # Same profile (or a legacy repeat) is idempotent; anything else is a
        # conflict. Either way the recorded provenance is left untouched.
        application_provenance.shortlist_profile_conflict(
            existing.cv_profile_id, requested_profile
        )
        return {
            "application_id": existing.id,
            "status": existing.status,
            "cv_profile_id": existing.cv_profile_id,
            "message": "Already shortlisted",
        }

    match_id = None
    if requested_profile is not None:
        profile_service.resolve_confirmed_profile(db, candidate, requested_profile)
        profile_match = latest_match_for_profile(db, job_id, requested_profile)
        if profile_match is None:
            # Never attach a legacy match and call it profile-specific.
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"CV profile {requested_profile} has no match for this job. "
                    "Run a discovery search for that profile first."
                ),
            )
        match_id = profile_match.id

    cv_profile_id = application_provenance.resolve_application_profile(
        db,
        candidate,
        requested_profile,
        None,
        match_id,
        None,
        None,
    )

    application = Application(
        candidate_id=candidate.id,
        job_id=job_id,
        match_id=match_id,
        cv_profile_id=cv_profile_id,
        status=ApplicationStatus.INTERESTED.value,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    return {
        "application_id": application.id,
        "status": application.status,
        "cv_profile_id": application.cv_profile_id,
        "message": "Job shortlisted successfully",
    }


__all__ = ["router"]
