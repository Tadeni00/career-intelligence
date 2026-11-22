"""Job persistence and requirement extraction."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.core.config import get_settings
from app.models import ExtractionStatus, Importance, Job, JobRequirement
from app.schemas import ExtractedJobRequirements, JobCreate, JobUpdate
from app.services import extraction as extraction_service

logger = logging.getLogger(__name__)


def create_job(db: Session, payload: JobCreate) -> Job:
    job = Job(
        title=payload.title,
        company=payload.company,
        location=payload.location,
        url=payload.url,
        source=payload.source or "manual",
        description=payload.description,
        employment_type=payload.employment_type,
        remote_status=payload.remote_status,
        salary_min=payload.salary_min,
        salary_max=payload.salary_max,
        posted_at=payload.posted_at,
    )
    db.add(job)
    db.flush()
    for requirement in payload.requirements or []:
        db.add(
            JobRequirement(
                job_id=job.id,
                requirement_type=requirement.requirement_type.value,
                name=requirement.name,
                description=requirement.description,
                importance=requirement.importance.value,
                years_required=requirement.years_required,
            )
        )
    db.commit()
    db.refresh(job)
    return job


def update_job(db: Session, job: Job, payload: JobUpdate) -> Job:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(job, key, value)
    db.commit()
    db.refresh(job)
    return job


def get_job(db: Session, job_id: int) -> Job:
    job = db.execute(select(Job).where(Job.id == job_id)).scalars().first()
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found."
        )
    return job


def extract_requirements(db: Session, job: Job) -> tuple[Job, ExtractedJobRequirements]:
    """Extract requirements from the description. The description is never modified."""
    if not (job.description or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This job has no description to extract requirements from.",
        )

    provider = get_ai_provider()
    # V3.1: run through the extraction contract. A failure is recorded on the job
    # and surfaced; it is never persisted as "this job has no requirements".
    result = extraction_service.extract_requirements(
        provider,
        job.description or "",
        model=get_settings().ai_model,
    )
    meta = result.meta
    job.extraction_status = meta.status
    job.extraction_error_code = meta.error_code

    if meta.status == ExtractionStatus.FAILED.value:
        # Preserve any previously extracted requirements: a failed re-extraction
        # must not destroy the evidence already on the job.
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"Requirement extraction failed: {meta.error_code}. "
                f"{meta.error_detail or ''} Previously stored requirements "
                "(if any) were left untouched."
            ),
        )

    extracted = result.requirements

    # Replace previously extracted requirements only.
    for existing in list(job.requirements):
        db.delete(existing)
    db.flush()

    from app.services.validation import classify_requirement

    def _imp(name: str, description: str | None, importance: str) -> str:
        """Classification hygiene: boilerplate becomes SOFT_SIGNAL, never REQUIRED."""
        return classify_requirement(name, description or "", importance)

    for skill in extracted.required_skills:
        db.add(
            JobRequirement(
                job_id=job.id,
                requirement_type="SKILL",
                name=skill,
                description=f"Required: {skill}",
                importance=Importance.REQUIRED.value,
            )
        )
    for skill in extracted.preferred_skills:
        db.add(
            JobRequirement(
                job_id=job.id,
                requirement_type="SKILL",
                name=skill,
                description=f"Preferred: {skill}",
                importance=Importance.PREFERRED.value,
            )
        )
    for requirement in extracted.experience_requirements:
        db.add(
            JobRequirement(
                job_id=job.id,
                requirement_type="EXPERIENCE",
                name=requirement.name[:255],
                description=requirement.description,
                importance=_imp(requirement.name, requirement.description,
                                requirement.importance.value),
                years_required=requirement.years_required,
            )
        )
    for requirement in extracted.education_requirements:
        db.add(
            JobRequirement(
                job_id=job.id,
                requirement_type="EDUCATION",
                name=requirement.name[:255],
                description=requirement.description,
                importance=_imp(requirement.name, requirement.description,
                                requirement.importance.value),
            )
        )
    for requirement in extracted.location_requirements:
        db.add(
            JobRequirement(
                job_id=job.id,
                requirement_type="LOCATION",
                name=requirement.name[:255],
                description=requirement.description,
                importance=_imp(requirement.name, requirement.description,
                                requirement.importance.value),
            )
        )
    for requirement in extracted.other_requirements:
        db.add(
            JobRequirement(
                job_id=job.id,
                requirement_type="OTHER",
                name=requirement.name[:255],
                description=requirement.description,
                importance=_imp(requirement.name, requirement.description,
                                requirement.importance.value),
            )
        )

    job.requirements_extracted = True
    db.commit()
    db.refresh(job)
    logger.info(
        "requirement extraction %s job=%s count=%d recovered=%d dropped=%s",
        meta.status, job.id, meta.requirement_count, meta.recovered_elements,
        meta.dropped_elements[:3],
    )
    return job, extracted


__all__ = ["create_job", "extract_requirements", "get_job", "update_job"]
