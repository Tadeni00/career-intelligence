"""Tailored CV and cover letter endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_candidate, owned_tailored_cv, profile_summary
from app.db.session import get_db
from app.models import Candidate, CoverLetter, Job, TailoredCV
from app.schemas import (
    CoverLetterOut,
    CVAnalysis,
    DocumentProfileRequest,
    ProfileSummary,
    TailoredCVOut,
    ValidationIssue,
)
from app.services import cv as cv_service
from app.services import cv_profile as profile_service
from app.services import generation as generation_service
from app.services import jobs as job_service

router = APIRouter(tags=["application materials"])


def _analysis(raw: str | None) -> CVAnalysis | None:
    if not raw:
        return None
    try:
        return CVAnalysis.model_validate_json(raw)
    except Exception:  # noqa: BLE001 - stored data may predate schema changes
        return None


def _issues(raw: str | None) -> list[ValidationIssue]:
    data = generation_service.parse_issues(raw)
    out: list[ValidationIssue] = []
    for item in data:
        try:
            out.append(ValidationIssue.model_validate(item))
        except Exception:  # noqa: BLE001
            continue
    return out


def _letter_out(record: CoverLetter) -> CoverLetterOut:
    return CoverLetterOut(
        id=record.id,
        candidate_id=record.candidate_id,
        job_id=record.job_id,
        content=record.content,
        cv_profile_id=record.cv_profile_id,
        validation_status=record.validation_status,
        validation_issues=[i.model_dump() for i in _issues(record.validation_issues)],
        created_at=record.created_at,
    )


def _cv_out(record: TailoredCV) -> TailoredCVOut:
    return TailoredCVOut(
        id=record.id,
        candidate_id=record.candidate_id,
        job_id=record.job_id,
        source_cv_id=record.source_cv_id,
        cv_profile_id=record.cv_profile_id,
        version=record.version,
        filename=record.filename,
        storage_path=record.storage_path,
        summary=record.summary,
        analysis=_analysis(record.analysis),
        changes_summary=generation_service.parse_issues(record.changes_summary)
        if record.changes_summary
        and record.changes_summary.strip().startswith("[")
        else [],
        validation_status=record.validation_status,
        validation_issues=[i.model_dump() for i in _issues(record.validation_issues)],
        created_at=record.created_at,
    )


@router.post("/jobs/{job_id}/analyze-cv", response_model=CVAnalysis)
def analyse_cv(
    job_id: int,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
    profile: ProfileSummary = Depends(profile_summary),
) -> CVAnalysis:
    job = job_service.get_job(db, job_id)
    return generation_service.analyse_for_job(db, candidate, job, profile)


@router.post("/jobs/{job_id}/tailor-cv", response_model=TailoredCVOut)
def tailor_cv(
    job_id: int,
    payload: DocumentProfileRequest | None = None,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
    profile: ProfileSummary = Depends(profile_summary),
) -> TailoredCVOut:
    """Generate a tailored CV, optionally from an explicitly selected profile.

    With no ``cv_profile_id`` this is the unchanged legacy path: the shared
    Candidate evidence and a null profile identifier. With one, that confirmed
    profile's evidence is used instead and recorded on the document. A profile
    that is missing, unowned, unconfirmed or archived is rejected; there is no
    fallback to the shared Candidate.
    """
    job = job_service.get_job(db, job_id)
    cv_profile_id, source_cv_id = _resolve_document_source(db, candidate, payload)
    if cv_profile_id is None:
        effective_profile = profile
    else:
        effective_profile = _profile_summary_for(db, candidate, cv_profile_id)

    record = generation_service.generate_tailored_cv(
        db,
        candidate,
        job,
        effective_profile,
        source_cv_id=source_cv_id,
        cv_profile_id=cv_profile_id,
    )
    return _cv_out(record)


def _resolve_document_source(
    db: Session,
    candidate: Candidate,
    payload: DocumentProfileRequest | None,
) -> tuple[int | None, int | None]:
    """Return (cv_profile_id, source_cv_id) for a generation request."""
    requested = payload.cv_profile_id if payload else None
    if requested is not None:
        # Validate ownership and state now, so an invalid id never silently
        # produces a legacy document.
        profile_service.resolve_confirmed_profile(db, candidate, requested)
        return requested, None
    master = cv_service.master_cv(db, candidate.id)
    return None, master.id if master else None


def _profile_summary_for(
    db: Session, candidate: Candidate, cv_profile_id: int
) -> ProfileSummary:
    """Candidate evidence for generation, taken only from the selected profile."""
    _profile, data = profile_service.resolve_confirmed_profile(
        db, candidate, cv_profile_id
    )
    return profile_service.to_profile_summary(data, cv_profile_id)


@router.get("/tailored-cvs", response_model=list[TailoredCVOut])
def list_tailored_cvs(
    job_id: int | None = None,
    cv_profile_id: int | None = Query(
        default=None,
        description=(
            "Return only documents generated from this CV profile. Omit for "
            "the unchanged legacy listing."
        ),
    ),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> list[TailoredCVOut]:
    stmt = select(TailoredCV).where(TailoredCV.candidate_id == candidate.id)
    if job_id is not None:
        stmt = stmt.where(TailoredCV.job_id == job_id)
    if cv_profile_id is not None:
        profile_service.resolve_confirmed_profile(db, candidate, cv_profile_id)
        stmt = stmt.where(TailoredCV.cv_profile_id == cv_profile_id)
    records = db.execute(
        stmt.order_by(TailoredCV.created_at.desc(), TailoredCV.id.desc())
    ).scalars().all()
    return [_cv_out(record) for record in records]


@router.get("/tailored-cvs/{cv_id}", response_model=TailoredCVOut)
def get_tailored_cv(cv_id: int, db: Session = Depends(get_db)) -> TailoredCVOut:
    return _cv_out(owned_tailored_cv(db, cv_id))


@router.get("/tailored-cvs/{cv_id}/download")
def download_tailored_cv(cv_id: int, db: Session = Depends(get_db)) -> Response:
    record = owned_tailored_cv(db, cv_id)
    path = generation_service.read_generated(record.storage_path)
    return Response(
        content=path.read_bytes(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{record.filename}"'},
    )


@router.get("/tailored-cvs/{cv_id}/content")
def tailored_cv_content(cv_id: int, db: Session = Depends(get_db)) -> dict:
    """Structured content, used by the UI to preview and compare with the master CV."""
    record = owned_tailored_cv(db, cv_id)
    content = json.loads(record.content_json) if record.content_json else {}
    master = cv_service.master_cv(db, record.candidate_id)
    master_text = None
    if master is not None:
        from app.services.documents import extract_text_from_path

        try:
            master_text = extract_text_from_path(master.storage_path, master.file_type)
        except Exception:  # noqa: BLE001 - preview is best-effort
            master_text = None
    return {
        "id": record.id,
        "job_id": record.job_id,
        "version": record.version,
        "content": content,
        "changes_summary": generation_service.parse_issues(record.changes_summary),
        "validation_status": record.validation_status,
        "validation_issues": [i.model_dump() for i in _issues(record.validation_issues)],
        "master_cv": {"id": master.id, "filename": master.filename, "text": master_text}
        if master
        else None,
    }


@router.post("/tailored-cvs/{cv_id}/regenerate", response_model=TailoredCVOut)
def regenerate_cv(
    cv_id: int,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
    profile: ProfileSummary = Depends(profile_summary),
) -> TailoredCVOut:
    """Regenerate a document, keeping the evidence it was originally built from.

    A profile-aware document regenerates from that same profile and keeps its
    profile identifier; a legacy document stays legacy.
    """
    record = owned_tailored_cv(db, cv_id)
    job = db.get(Job, record.job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job no longer exists.")
    effective_profile = (
        profile
        if record.cv_profile_id is None
        else _profile_summary_for(db, candidate, record.cv_profile_id)
    )
    new_record = generation_service.regenerate_tailored_cv(
        db, record, candidate, job, effective_profile
    )
    return _cv_out(new_record)


@router.post("/jobs/{job_id}/cover-letter", response_model=CoverLetterOut)
def create_cover_letter(
    job_id: int,
    payload: DocumentProfileRequest | None = None,
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
    profile: ProfileSummary = Depends(profile_summary),
) -> CoverLetterOut:
    """Generate a cover letter, optionally from an explicitly selected profile."""
    job = job_service.get_job(db, job_id)
    cv_profile_id, _source_cv_id = _resolve_document_source(db, candidate, payload)
    effective_profile = (
        profile
        if cv_profile_id is None
        else _profile_summary_for(db, candidate, cv_profile_id)
    )
    record = generation_service.generate_cover_letter(
        db, candidate, job, effective_profile, cv_profile_id=cv_profile_id
    )
    return _letter_out(record)


@router.get("/cover-letters", response_model=list[CoverLetterOut])
def list_cover_letters(
    job_id: int | None = None,
    cv_profile_id: int | None = Query(
        default=None,
        description="Return only letters generated from this CV profile.",
    ),
    db: Session = Depends(get_db),
    candidate: Candidate = Depends(current_candidate),
) -> list[CoverLetterOut]:
    stmt = select(CoverLetter).where(CoverLetter.candidate_id == candidate.id)
    if job_id is not None:
        stmt = stmt.where(CoverLetter.job_id == job_id)
    if cv_profile_id is not None:
        profile_service.resolve_confirmed_profile(db, candidate, cv_profile_id)
        stmt = stmt.where(CoverLetter.cv_profile_id == cv_profile_id)
    records = db.execute(
        stmt.order_by(CoverLetter.created_at.desc(), CoverLetter.id.desc())
    ).scalars().all()
    return [_letter_out(r) for r in records]


@router.get("/cover-letters/{letter_id}", response_model=CoverLetterOut)
def get_cover_letter(letter_id: int, db: Session = Depends(get_db)) -> CoverLetterOut:
    record = db.get(CoverLetter, letter_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cover letter {letter_id} not found.",
        )
    return _letter_out(record)


@router.get("/cover-letters/{letter_id}/download")
def download_cover_letter(letter_id: int, db: Session = Depends(get_db)) -> Response:
    record = db.get(CoverLetter, letter_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cover letter {letter_id} not found.",
        )
    job = db.get(Job, record.job_id)
    safe_company = job.company if job else "company"
    safe_company = "".join(ch for ch in (safe_company or "") if ch.isalnum() or ch in " -_")
    filename = f"{safe_company.strip().replace(' ', '-') or 'company'}-cover-letter.txt"
    return Response(
        content=record.content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


__all__ = ["router"]
