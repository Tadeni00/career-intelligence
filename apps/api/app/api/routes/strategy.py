"""Application strategy endpoints (V2)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import current_candidate
from app.db.session import get_db
from app.models import Candidate
from app.schemas import ProfileSummary, StrategyOut
from app.services import cv_profile as profile_service
from app.services import jobs as job_service
from app.services import strategy_store
from app.services.candidate import to_profile_summary

router = APIRouter(tags=["strategy"])


@router.get("/jobs/{job_id}/strategy", response_model=StrategyOut)
def get_strategy(
    job_id: int,
    cv_profile_id: int | None = Query(
        default=None,
        description=(
            "Return the strategy for this CV profile. Omit for the unchanged "
            "legacy lookup over the shared Candidate record."
        ),
    ),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> StrategyOut:
    """Current strategy for a job, rebuilt automatically when it is stale."""
    job = job_service.get_job(db, job_id)
    profile = _resolve_evidence(db, candidate, cv_profile_id)
    match = strategy_store.current_match(db, job_id, cv_profile_id=cv_profile_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This job has not been matched yet for this CV profile. "
                "Run the match first."
            ),
        )
    record, issues, _rebuilt = strategy_store.refresh_if_stale(
        db, profile, job, match, cv_profile_id=cv_profile_id
    )
    return strategy_store.to_out(record, issues)


def _resolve_evidence(
    db: Session, candidate: Candidate, cv_profile_id: int | None
) -> ProfileSummary:
    """Candidate evidence for a strategy: the shared record, or one profile."""
    if cv_profile_id is None:
        return to_profile_summary(candidate)
    _profile, data = profile_service.resolve_confirmed_profile(
        db, candidate, cv_profile_id
    )
    return profile_service.to_profile_summary(data, cv_profile_id)


@router.post("/jobs/{job_id}/strategy", response_model=StrategyOut)
def rebuild_strategy(
    job_id: int,
    cv_profile_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> StrategyOut:
    """Force a fresh strategy version for a job, within one evidence scope."""
    job = job_service.get_job(db, job_id)
    profile = _resolve_evidence(db, candidate, cv_profile_id)
    match = strategy_store.current_match(db, job_id, cv_profile_id=cv_profile_id)
    if match is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This job has not been matched yet for this CV profile. "
                "Run the match first."
            ),
        )
    strategy, issues = strategy_store.build_for_match(db, profile, job, match)
    from app.services import strategy as strategy_service

    record = strategy_store.persist(
        db,
        candidate.id,
        job,
        match,
        strategy,
        strategy_service.evidence_fingerprint(profile, job),
        cv_profile_id=cv_profile_id,
    )
    return strategy_store.to_out(record, issues)


@router.get("/jobs/{job_id}/strategy/history")
def strategy_history(
    job_id: int,
    cv_profile_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> list[dict]:
    """Every stored strategy version for one evidence scope, newest first.

    No history is ever discarded: scoping only decides which chain is shown.

    Ownership is checked, not eligibility: an archived profile's history must
    remain readable, so only ``get_profile`` is used here rather than the
    confirmed-and-active gate.
    """
    job_service.get_job(db, job_id)
    if cv_profile_id is not None:
        profile_service.get_profile(db, candidate, cv_profile_id)
    rows = strategy_store.strategy_history(
        db, candidate.id, job_id, cv_profile_id=cv_profile_id
    )
    return [
        {
            "id": r.id,
            "version": r.version,
            "status": r.status,
            "cv_profile_id": r.cv_profile_id,
            "decision": r.decision,
            "decision_summary": r.decision_summary,
            "created_at": r.created_at,
            "updated_at": r.updated_at,
        }
        for r in rows
    ]


__all__ = ["router"]
