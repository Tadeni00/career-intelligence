"""Application tracking endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_candidate
from app.db.session import get_db
from app.models import (
    Application,
    ApplicationStatus,
    Candidate,
    CoverLetter,
    TailoredCV,
)
from app.schemas import ApplicationCreate, ApplicationOut, ApplicationUpdate
from app.services import application_provenance
from app.services import cv_profile as profile_service
from app.services import jobs as job_service
from app.services import matching as matching_service

router = APIRouter(prefix="/applications", tags=["applications"])


def _to_out(record: Application) -> ApplicationOut:
    return ApplicationOut.model_validate(record)


@router.get("", response_model=list[ApplicationOut])
def list_applications(
    status_filter: str | None = None,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> list[ApplicationOut]:
    stmt = (
        select(Application)
        .where(Application.candidate_id == candidate.id)
        .options(
            selectinload(Application.job),
            selectinload(Application.match),
        )
        .order_by(Application.updated_at.desc(), Application.id.desc())
    )
    records = db.execute(stmt).scalars().all()
    if status_filter:
        wanted = status_filter.upper()
        records = [r for r in records if r.status == wanted]
    return [_to_out(record) for record in records]


@router.post("", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
def create_application(
    payload: ApplicationCreate,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> ApplicationOut:
    job = job_service.get_job(db, payload.job_id)

    existing = db.execute(
        select(Application).where(
            Application.candidate_id == candidate.id, Application.job_id == job.id
        )
    ).scalars().first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"An application for job {job.id} already exists "
                f"(status {existing.status}, cv_profile_id "
                f"{existing.cv_profile_id}). Update it instead."
            ),
        )

    _validate_links(db, payload.tailored_cv_id, payload.cover_letter_id, candidate)

    match_id = payload.match_id
    if match_id is None:
        # With an explicit profile, resolve the match in that profile's scope so
        # a profile-aware application never silently links a legacy match.
        if payload.cv_profile_id is not None:
            profile_service.resolve_confirmed_profile(
                db, candidate, payload.cv_profile_id
            )
            match = matching_service.latest_match_for_profile(
                db, job.id, payload.cv_profile_id
            )
        else:
            match = matching_service.latest_match(db, job.id)
        match_id = match.id if match else None

    cv_profile_id = application_provenance.resolve_application_profile(
        db,
        candidate,
        payload.cv_profile_id,
        None,
        match_id,
        payload.tailored_cv_id,
        payload.cover_letter_id,
    )

    record = Application(
        candidate_id=candidate.id,
        job_id=job.id,
        match_id=match_id,
        tailored_cv_id=payload.tailored_cv_id,
        cover_letter_id=payload.cover_letter_id,
        cv_profile_id=cv_profile_id,
        status=payload.status.value,
        notes=payload.notes,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    record.job = job
    return _to_out(record)


def _validate_links(
    db: Session,
    tailored_cv_id: int | None,
    cover_letter_id: int | None,
    candidate: Candidate,
) -> None:
    if tailored_cv_id is not None:
        record = db.get(TailoredCV, tailored_cv_id)
        if record is None or record.candidate_id != candidate.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tailored CV {tailored_cv_id} not found.",
            )
    if cover_letter_id is not None:
        record = db.get(CoverLetter, cover_letter_id)
        if record is None or record.candidate_id != candidate.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cover letter {cover_letter_id} not found.",
            )


@router.put("/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: int,
    payload: ApplicationUpdate,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> ApplicationOut:
    record = db.get(Application, application_id)
    if record is None or record.candidate_id != candidate.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found.",
        )

    data = payload.model_dump(exclude_unset=True)
    _validate_links(db, data.get("tailored_cv_id"), data.get("cover_letter_id"), candidate)

    requested_profile = data.pop("cv_profile_id", None)
    # Consistency is re-checked on every update, because attaching an artefact
    # from another profile is exactly as much a reassignment attempt as naming
    # one in the body.
    record.cv_profile_id = application_provenance.resolve_application_profile(
        db,
        candidate,
        requested_profile,
        record.cv_profile_id,
        data.get("match_id", record.match_id),
        data.get("tailored_cv_id", record.tailored_cv_id),
        data.get("cover_letter_id", record.cover_letter_id),
    )

    new_status = data.pop("status", None)
    if new_status is not None:
        record.status = ApplicationStatus(new_status).value
        if record.status in {ApplicationStatus.APPLIED.value, ApplicationStatus.INTERVIEW.value} and not record.applied_at:
            from datetime import UTC, datetime

            record.applied_at = datetime.now(UTC)
    for key, value in data.items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return _to_out(record)


@router.get("/{application_id}", response_model=ApplicationOut)
def get_application(
    application_id: int,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> ApplicationOut:
    record = db.get(Application, application_id)
    if record is None or record.candidate_id != candidate.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found.",
        )
    return _to_out(record)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_application(
    application_id: int,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> Response:
    record = db.get(Application, application_id)
    if record is None or record.candidate_id != candidate.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Application {application_id} not found.",
        )
    db.delete(record)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
