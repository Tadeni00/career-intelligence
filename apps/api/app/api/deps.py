"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Candidate, CVDocument, TailoredCV
from app.schemas import ProfileSummary
from app.services import candidate as candidate_service


def current_candidate(db: Session = Depends(get_db)) -> Candidate:
    """V1 is single-user; this resolves the one profile."""
    return candidate_service.get_or_create_candidate(db)


def profile_summary(
    db: Session = Depends(get_db), candidate: Candidate = Depends(current_candidate)
) -> ProfileSummary:
    loaded = candidate_service.load_candidate(db, candidate.id)
    return candidate_service.to_profile_summary(loaded)


def _fetch(db: Session, model, record_id: int, label: str):
    record = db.get(model, record_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} {record_id} not found."
        )
    return record


def owned_cv(db: Session, cv_id: int) -> CVDocument:
    return _fetch(db, CVDocument, cv_id, "CV")


def owned_tailored_cv(db: Session, cv_id: int) -> TailoredCV:
    return _fetch(db, TailoredCV, cv_id, "Tailored CV")


__all__ = ["current_candidate", "owned_cv", "owned_tailored_cv", "profile_summary"]
