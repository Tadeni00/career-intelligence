"""CV upload, extraction, review and confirmation."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import current_candidate, owned_cv
from app.db.session import get_db
from app.models import Candidate, CVDocument, CVExtraction, CVStatus
from app.schemas import (
    CVConfirmRequest,
    CVExtractionOut,
    CVOut,
    ExtractedCV,
    ProfileSummary,
)
from app.services import candidate as candidate_service
from app.services import cv as cv_service

router = APIRouter(prefix="/cvs", tags=["cvs"])


def _to_out(document: CVDocument, preview: str | None = None) -> CVOut:
    return CVOut(
        id=document.id,
        candidate_id=document.candidate_id,
        filename=document.filename,
        file_type=document.file_type,
        is_master=document.is_master,
        status=document.status,
        error_message=document.error_message,
        uploaded_at=document.uploaded_at,
        extracted_at=document.extracted_at,
        confirmed_at=document.confirmed_at,
        text_preview=preview,
    )


def _extraction_out(extraction: CVExtraction) -> CVExtractionOut:
    try:
        issues = json.loads(extraction.issues) if extraction.issues else []
    except json.JSONDecodeError:
        issues = []
    return CVExtractionOut(
        id=extraction.id,
        cv_id=extraction.cv_id,
        confirmed=extraction.confirmed,
        created_at=extraction.created_at,
        confirmed_at=extraction.confirmed_at,
        data=ExtractedCV.model_validate_json(extraction.data),
        issues=issues if isinstance(issues, list) else [],
        text_length=len(extraction.raw_text or ""),
    )


@router.post("/upload", response_model=CVOut, status_code=status.HTTP_201_CREATED)
def upload_cv(
    file: UploadFile = File(...),
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> CVOut:
    document = cv_service.store_upload(db, candidate, file)
    return _to_out(document)


@router.get("", response_model=list[CVOut])
def list_cvs(
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> list[CVOut]:
    documents = db.execute(
        select(CVDocument)
        .where(CVDocument.candidate_id == candidate.id)
        .order_by(CVDocument.uploaded_at.desc(), CVDocument.id.desc())
    ).scalars().all()
    return [_to_out(document) for document in documents]


@router.get("/{cv_id}", response_model=CVOut)
def get_cv(cv_id: int, db: Session = Depends(get_db)) -> CVOut:
    return _to_out(owned_cv(db, cv_id))


@router.post("/{cv_id}/extract", response_model=CVExtractionOut)
def extract_cv(cv_id: int, db: Session = Depends(get_db)) -> CVExtractionOut:
    document = owned_cv(db, cv_id)
    if document.status == CVStatus.READY.value:
        latest = cv_service.latest_extraction(db, cv_id)
        if latest is not None:
            return _extraction_out(latest)
    extraction = cv_service.run_extraction(db, document)
    return _extraction_out(extraction)


@router.get("/{cv_id}/extraction", response_model=CVExtractionOut)
def get_extraction(cv_id: int, db: Session = Depends(get_db)) -> CVExtractionOut:
    owned_cv(db, cv_id)
    extraction = cv_service.latest_extraction(db, cv_id)
    if extraction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="This CV has not been extracted yet.",
        )
    return _extraction_out(extraction)


@router.post("/{cv_id}/confirm", response_model=ProfileSummary)
def confirm_cv(
    cv_id: int,
    payload: CVConfirmRequest,
    db: Session = Depends(get_db),
) -> ProfileSummary:
    document = owned_cv(db, cv_id)
    extraction = (
        db.get(CVExtraction, payload.extraction_id)
        if payload.extraction_id
        else cv_service.latest_extraction(db, cv_id)
    )
    if extraction is None or extraction.cv_id != cv_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No extraction found for this CV. Run extraction first.",
        )
    candidate = cv_service.confirm_extraction(db, document, extraction, payload)
    return candidate_service.to_profile_summary(candidate)


@router.post("/{cv_id}/make-master", response_model=CVOut)
def make_master(cv_id: int, db: Session = Depends(get_db)) -> CVOut:
    document = owned_cv(db, cv_id)
    others = db.execute(
        select(CVDocument).where(
            CVDocument.candidate_id == document.candidate_id,
            CVDocument.is_master.is_(True),
            CVDocument.id != document.id,
        )
    ).scalars().all()
    for other in others:
        other.is_master = False
    document.is_master = True
    db.commit()
    db.refresh(document)
    return _to_out(document)


__all__ = ["router"]
