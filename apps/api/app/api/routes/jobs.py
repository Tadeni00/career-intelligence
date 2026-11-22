"""Job endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import current_candidate
from app.db.session import get_db
from app.models import ExtractionStatus, Job
from app.schemas import (
    JobCreate,
    JobOut,
    JobRequirementOut,
    JobSummaryOut,
    JobUpdate,
)
from app.services import jobs as job_service
from app.services import matching as matching_service

router = APIRouter(prefix="/jobs", tags=["jobs"])

_SORTS = {"newest": "newest", "match": "match", "oldest": "oldest"}


def _mark_review(job_out):
    """V3.2: a PARTIAL extraction is identifiable and flagged for review.

    FAILED means the job cannot be matched at all; EMPTY_CONFIRMED is a
    deliberate, documented state. Only a partial or failed extraction leaves the
    requirement set untrustworthy enough to warrant review.
    """
    job_out.requires_review = job_out.extraction_status in (
        ExtractionStatus.PARTIAL.value,
        ExtractionStatus.FAILED.value,
    )
    return job_out


def _summary_with_match(db: Session, job: Job) -> JobSummaryOut:
    summary = _mark_review(JobSummaryOut.model_validate(job))
    match = matching_service.latest_match(db, job.id)
    if match is not None:
        summary.latest_match = {
            "id": match.id,
            "job_id": match.job_id,
            "overall_score": match.overall_score,
            "recommendation": match.recommendation,
            "confidence": match.confidence,
            "created_at": match.created_at,
        }
    return summary


@router.get("", response_model=list[JobSummaryOut])
def list_jobs(
    recommendation: str | None = Query(
        default=None, description="Filter by latest match recommendation."
    ),
    sort: str = Query(default="newest"),
    db: Session = Depends(get_db),
    candidate=Depends(current_candidate),
) -> list[JobSummaryOut]:
    jobs = db.execute(
        select(Job)
        .options(selectinload(Job.requirements))
        .order_by(Job.created_at.desc(), Job.id.desc())
    ).scalars().all()

    summaries = [_summary_with_match(db, job) for job in jobs]
    if recommendation:
        wanted = recommendation.upper()
        summaries = [
            s
            for s in summaries
            if s.latest_match and s.latest_match["recommendation"] == wanted
        ]

    if sort == _SORTS["match"]:
        summaries.sort(
            key=lambda s: (
                s.latest_match["overall_score"] if s.latest_match else -1.0,
                s.id,
            ),
            reverse=True,
        )
    elif sort == _SORTS["oldest"]:
        summaries.reverse()
    return summaries


@router.post("", response_model=JobOut, status_code=status.HTTP_201_CREATED)
def create_job(payload: JobCreate, db: Session = Depends(get_db)) -> JobOut:
    job = job_service.create_job(db, payload)
    job.requirements = job.requirements
    return _mark_review(JobOut.model_validate(job))


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = job_service.get_job(db, job_id)
    return _mark_review(JobOut.model_validate(job))


@router.put("/{job_id}", response_model=JobOut)
def update_job(job_id: int, payload: JobUpdate, db: Session = Depends(get_db)) -> JobOut:
    job = job_service.get_job(db, job_id)
    job_service.update_job(db, job, payload)
    return _mark_review(JobOut.model_validate(job))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_job(job_id: int, db: Session = Depends(get_db)) -> None:
    job = job_service.get_job(db, job_id)
    db.delete(job)
    db.commit()


@router.post("/{job_id}/extract-requirements", response_model=JobOut)
def extract_requirements(job_id: int, db: Session = Depends(get_db)) -> JobOut:
    job = job_service.get_job(db, job_id)
    job, _extracted = job_service.extract_requirements(db, job)
    return _mark_review(JobOut.model_validate(job))


@router.get("/{job_id}/requirements", response_model=list[JobRequirementOut])
def list_requirements(job_id: int, db: Session = Depends(get_db)) -> list[JobRequirementOut]:
    job = job_service.get_job(db, job_id)
    return [JobRequirementOut.model_validate(req) for req in job.requirements]


__all__ = ["router"]
