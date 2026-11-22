"""CV profile management.

Every operation resolves its profile through the owning candidate, so a profile
id only ever addresses the current candidate's own profiles. These endpoints
create, list, read, extract and confirm profiles; they never update the shared
``Candidate`` row and never select a profile for matching.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import current_candidate
from app.db.session import get_db
from app.models import Candidate, CVProfile
from app.schemas import CVProfileConfirmRequest, CVProfileOut
from app.services import cv_profile as profile_service

router = APIRouter(prefix="/cv-profiles", tags=["cv-profiles"])


def _to_out(profile: CVProfile) -> CVProfileOut:
    return CVProfileOut(
        id=profile.id,
        candidate_id=profile.candidate_id,
        cv_id=profile.cv_id,
        label=profile.label,
        status=profile.status,
        error_message=profile.error_message,
        extracted=profile_service.read_extracted(profile),
        extracted_issues=profile_service.read_issues(profile),
        confirmed=profile_service.read_confirmed(profile),
        text_length=len(profile.extracted_text or ""),
        archived_at=profile.archived_at,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
        extracted_at=profile.extracted_at,
        confirmed_at=profile.confirmed_at,
    )


@router.post("", response_model=CVProfileOut, status_code=status.HTTP_201_CREATED)
def create_cv_profile(
    file: UploadFile = File(...),
    label: str | None = Form(default=None),
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> CVProfileOut:
    """Upload a CV and open an independent profile for it."""
    profile = profile_service.create_profile(db, candidate, file, label=label)
    return _to_out(profile)


@router.get("", response_model=list[CVProfileOut])
def list_cv_profiles(
    include_archived: bool = False,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> list[CVProfileOut]:
    """List this candidate's profiles. Archived ones are hidden by default."""
    return [
        _to_out(p)
        for p in profile_service.list_profiles(
            db, candidate, include_archived=include_archived
        )
    ]


@router.get("/{profile_id}", response_model=CVProfileOut)
def get_cv_profile(
    profile_id: int,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> CVProfileOut:
    return _to_out(profile_service.get_profile(db, candidate, profile_id))


@router.post("/{profile_id}/extract", response_model=CVProfileOut)
def extract_cv_profile(
    profile_id: int,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> CVProfileOut:
    """Extract this profile's own text and structure."""
    profile = profile_service.get_profile(db, candidate, profile_id)
    return _to_out(profile_service.extract_profile(db, profile))


@router.post("/{profile_id}/confirm", response_model=CVProfileOut)
def confirm_cv_profile(
    profile_id: int,
    payload: CVProfileConfirmRequest,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> CVProfileOut:
    """Confirm this profile's candidate information, optionally correcting it."""
    profile = profile_service.get_profile(db, candidate, profile_id)
    return _to_out(profile_service.confirm_profile(db, profile, payload))


@router.post("/{profile_id}/archive", response_model=CVProfileOut)
def archive_cv_profile(
    profile_id: int,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> CVProfileOut:
    """Retire a profile without touching the history that cites it.

    Archiving is the only lifecycle operation. There is deliberately no delete
    endpoint: the foreign keys from matches, tailored CVs and cover letters
    RESTRICT, so a hard delete could either erase that history or relabel it as
    legacy. Archiving stops new use and keeps every existing record
    attributable and readable.
    """
    return _to_out(profile_service.archive_profile(db, candidate, profile_id))


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_cv_profile(
    profile_id: int,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> None:
    """Hard-delete a profile, but only if nothing references it.

    Returns 409 with a breakdown of what still references the profile.
    Archive the profile instead if it has history that must be kept.
    """
    profile_service.delete_profile(db, candidate, profile_id)


__all__ = ["router"]
