"""Match endpoints."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_candidate
from app.db.session import get_db
from app.models import Candidate, Job, MatchResult
from app.schemas import JobMatchRequest, JobSummaryOut, MatchItemOut, MatchOut
from app.services import jobs as job_service
from app.services import matching as matching_service
from app.services.extraction import ExtractionNotMatchableError

logger = logging.getLogger(__name__)

router = APIRouter(tags=["matches"])


def _items(raw: object) -> list[MatchItemOut]:
    """Decode one persisted match-item collection into response objects.

    ``MatchResult`` keeps these four collections in ``Text`` columns, so the
    normal input is a JSON string and validating the ORM object directly would
    hand Pydantic a ``str`` where ``MatchOut`` declares a list.

    A value that has already been decoded to a list is used as-is rather than
    decoded a second time. Anything that is not a JSON array of well-formed
    items contributes nothing: a malformed legacy value must never fabricate
    match evidence, and it must never take down the response. Every omission is
    logged, so nothing is discarded silently.
    """
    if raw is None or raw == "":
        return []

    if isinstance(raw, list):
        data: object = raw
    elif isinstance(raw, str):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Stored match-item collection is not valid JSON; omitted.")
            return []
    else:
        logger.warning("Stored match-item collection is not text; omitted.")
        return []

    if not isinstance(data, list):
        logger.warning("Stored match-item collection is not a JSON array; omitted.")
        return []

    items: list[MatchItemOut] = []
    for entry in data:
        try:
            items.append(MatchItemOut.model_validate(entry))
        except ValidationError:
            logger.warning("Stored match item %r is malformed; omitted.", entry)
    return items


def _to_out(match: MatchResult, job: Job | None = None) -> MatchOut:
    payload = {
        "id": match.id,
        "candidate_id": match.candidate_id,
        "job_id": match.job_id,
        "technical_score": match.technical_score,
        "experience_score": match.experience_score,
        "education_score": match.education_score,
        "location_score": match.location_score,
        "other_score": match.other_score,
        "overall_score": match.overall_score,
        "recommendation": match.recommendation,
        "confidence": match.confidence,
        "matched_items": _items(match.matched_items),
        "gap_items": _items(match.gap_items),
        "blocker_items": _items(match.blocker_items),
        "unknown_items": _items(match.unknown_items),
        "explanation": match.explanation,
        "cv_profile_id": match.cv_profile_id,
        "created_at": match.created_at,
    }
    if job is not None:
        payload["job"] = JobSummaryOut.model_validate(job)
    return MatchOut.model_validate(payload)


@router.post("/jobs/{job_id}/match", response_model=MatchOut)
def match_job(
    job_id: int,
    payload: JobMatchRequest | None = None,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> MatchOut:
    """Score a job against the selected candidate evidence.

    With no body, or a body without ``cv_profile_id``, this is the unchanged
    legacy behaviour: the shared Candidate record is scored and the stored
    result carries a null profile identifier.

    With ``cv_profile_id``, that confirmed profile is scored instead and the
    result is stamped with its id. A profile that does not exist, belongs to
    another candidate, or is not confirmed is rejected; none of those cases
    falls back to the shared Candidate record.
    """
    job = job_service.get_job(db, job_id)
    try:
        match = matching_service.run_match(
            db, candidate, job, cv_profile_id=payload.cv_profile_id if payload else None
        )
    except ExtractionNotMatchableError as exc:
        # V3.2: a failed or unconfirmed extraction propagates as an explicit
        # conflict, never as a score and never as a 500.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    return _to_out(match, job)


@router.get("/matches", response_model=list[MatchOut])
def list_matches(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> list[MatchOut]:
    rows = db.execute(
        select(MatchResult)
        .where(MatchResult.candidate_id == candidate.id)
        .options(selectinload(MatchResult.job))
        .order_by(MatchResult.created_at.desc(), MatchResult.id.desc())
        .limit(limit)
    ).scalars().all()
    return [_to_out(match) for match in rows]


@router.get("/jobs/{job_id}/match", response_model=MatchOut)
def latest_match_for_job(
    job_id: int,
    cv_profile_id: int | None = Query(
        default=None,
        description=(
            "Return only the result this CV profile produced. Omit for the "
            "unchanged legacy lookup, which returns the most recent result for "
            "the job regardless of profile."
        ),
    ),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> MatchOut:
    job = job_service.get_job(db, job_id)
    if cv_profile_id is not None:
        # Resolve ownership first, so another candidate's profile is a 404.
        matching_service.resolve_matching_input(db, candidate, cv_profile_id)
        match = matching_service.latest_match_for_profile(db, job_id, cv_profile_id)
        if match is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"CV profile {cv_profile_id} has not been matched against "
                    "this job yet."
                ),
            )
        return _to_out(match, job)

    match = matching_service.latest_match(db, job_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This job has not been matched yet.",
        )
    return _to_out(match, job)


@router.get("/matches/{match_id}", response_model=MatchOut)
def get_match(
    match_id: int,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> MatchOut:
    match = db.get(MatchResult, match_id)
    if match is None or match.candidate_id != candidate.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Match {match_id} not found."
        )
    return _to_out(match, db.get(Job, match.job_id))


__all__ = ["router"]
