"""CV upload, extraction and confirmation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.core.config import get_settings
from app.core.storage import (
    build_storage_path,
    sanitise_filename,
    validate_content_type,
    validate_extension,
    validate_size,
)
from app.models import Candidate, CVDocument, CVExtraction, CVStatus
from app.schemas import CVConfirmRequest, ExtractedCV
from app.services import candidate as candidate_service
from app.services.documents import DocumentExtractionError, extract_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StoredUpload:
    """A validated, written upload. Carries no database state.

    Shared by the legacy CVDocument flow and the CV-profile flow so both apply
    identical filename, type, size and containment rules.
    """

    filename: str
    stored_filename: str
    file_type: str
    storage_path: str
    content_hash: str


def persist_upload(upload: UploadFile) -> StoredUpload:
    """Validate and write an upload to storage. Records nothing in the database."""
    settings = get_settings()
    filename = sanitise_filename(upload.filename)
    file_type = validate_extension(filename, settings.allowed_upload_extensions)
    validate_content_type(upload.content_type, settings.allowed_upload_mime_types)

    data = upload.file.read(settings.max_upload_bytes + 1)
    validate_size(len(data), settings.max_upload_bytes)

    stored_filename, path, content_hash = build_storage_path(
        settings.uploads_dir, file_type, filename
    )
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(data)

    return StoredUpload(
        filename=filename,
        stored_filename=stored_filename,
        file_type=file_type,
        storage_path=path,
        content_hash=content_hash,
    )


def store_upload(db: Session, candidate: Candidate, upload: UploadFile) -> CVDocument:
    stored = persist_upload(upload)

    master_exists = db.execute(
        select(CVDocument.id).where(
            CVDocument.candidate_id == candidate.id, CVDocument.is_master.is_(True)
        )
    ).first()
    document = CVDocument(
        candidate_id=candidate.id,
        filename=stored.filename,
        stored_filename=stored.stored_filename,
        file_type=stored.file_type,
        storage_path=stored.storage_path,
        content_hash=stored.content_hash,
        is_master=master_exists is None,
        status=CVStatus.UPLOADED.value,
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document


def run_extraction(db: Session, document: CVDocument) -> CVExtraction:
    """Extract text + structured data. Never mutates the candidate profile."""
    document.status = CVStatus.EXTRACTING.value
    db.commit()

    try:
        with open(document.storage_path, "rb") as handle:
            data = handle.read()
        text = extract_text(data, document.file_type)
    except DocumentExtractionError as exc:
        document.status = CVStatus.FAILED.value
        document.error_message = str(exc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    provider = get_ai_provider()
    extracted = provider.extract_cv(text)

    extraction = CVExtraction(
        cv_id=document.id,
        raw_text=text,
        data=extracted.model_dump_json(),
        issues=json.dumps(extracted.issues),
    )
    db.add(extraction)
    document.extracted_at = datetime.now(UTC)
    document.status = (
        CVStatus.REVIEW_REQUIRED.value if extracted.issues else CVStatus.EXTRACTED.value
    )
    db.commit()
    db.refresh(extraction)
    return extraction


def latest_extraction(db: Session, cv_id: int) -> CVExtraction | None:
    return db.execute(
        select(CVExtraction)
        .where(CVExtraction.cv_id == cv_id)
        .order_by(CVExtraction.created_at.desc(), CVExtraction.id.desc())
    ).scalars().first()


def confirm_extraction(
    db: Session, document: CVDocument, extraction: CVExtraction, request: CVConfirmRequest
) -> Candidate:
    """Apply confirmed extraction content to the candidate profile.

    With ``overwrite_existing=False`` (the default) existing records are left
    untouched and only new entries are appended.
    """
    data = ExtractedCV.model_validate_json(extraction.data)
    candidate = candidate_service.load_candidate(db, document.candidate_id)

    if request.overwrite_existing:
        candidate.name = data.name or candidate.name
        candidate.professional_title = data.professional_title or candidate.professional_title
        candidate.email = data.email or candidate.email
        candidate.phone = data.phone or candidate.phone
        candidate.location = data.location or candidate.location
        candidate.summary = data.summary or candidate.summary

    document.status = CVStatus.READY.value

    # Append extracted content that is not already recorded.
    from app.schemas import (
        CandidateSkillCreate,
        EducationCreate,
        ExperienceCreate,
        ProjectCreate,
    )

    existing_companies = {(e.company.strip().lower(), e.title.strip().lower()) for e in candidate.experience}
    for item in data.experience:
        key = (item.company.strip().lower(), item.title.strip().lower())
        if key in existing_companies:
            continue
        candidate_service.add_experience(
            db,
            candidate,
            ExperienceCreate(
                company=item.company,
                title=item.title,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description
                or " ".join(item.responsibilities + item.achievements)
                or None,
                is_current=item.is_current,
            ),
        )

    existing_institutions = {e.institution.strip().lower() for e in candidate.education}
    for item in data.education:
        if item.institution.strip().lower() in existing_institutions:
            continue
        candidate_service.add_education(
            db,
            candidate,
            EducationCreate(
                institution=item.institution,
                degree=item.degree,
                field=item.field,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description,
            ),
        )

    existing_projects = {p.name.strip().lower() for p in candidate.projects}
    for item in data.projects:
        if item.name.strip().lower() in existing_projects:
            continue
        candidate_service.add_project(
            db,
            candidate,
            ProjectCreate(
                name=item.name,
                description=item.description,
                technologies=item.technologies,
            ),
        )

    for skill in data.skills:
        if any(
            s.skill.name.strip().lower() == skill.name.strip().lower()
            for s in candidate.skills
            if s.skill
        ):
            continue
        candidate_service.add_skill(
            db, candidate, CandidateSkillCreate(name=skill.name, category=skill.category)
        )

    extraction.confirmed = True
    extraction.confirmed_at = datetime.now(UTC)
    document.confirmed_at = datetime.now(UTC)
    db.commit()
    return candidate_service.load_candidate(db, document.candidate_id)


def master_cv(db: Session, candidate_id: int) -> CVDocument | None:
    return db.execute(
        select(CVDocument)
        .where(CVDocument.candidate_id == candidate_id, CVDocument.is_master.is_(True))
        .order_by(CVDocument.id.desc())
    ).scalars().first()


__all__ = [
    "confirm_extraction",
    "latest_extraction",
    "master_cv",
    "run_extraction",
    "store_upload",
]
