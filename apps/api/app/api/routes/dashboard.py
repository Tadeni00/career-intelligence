"""Health and dashboard endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.ai import get_ai_provider
from app.api.deps import current_candidate
from app.core.config import get_settings
from app.db.session import get_db
from app.models import Application, ApplicationStatus, Candidate, Job, MatchResult
from app.schemas import (
    ApplicationOut,
    DashboardEntry,
    DashboardOut,
    DashboardStats,
    HealthOut,
)
from app.services import candidate as candidate_service

router = APIRouter(tags=["system"])

_RECOMMENDATIONS = ("APPLY", "APPLY_WITH_TAILORING", "STRETCH", "SKIP")


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    settings = get_settings()
    database_state = "ok"
    try:
        db.execute(select(func.now()))
    except Exception:  # noqa: BLE001
        database_state = "unavailable"
    return HealthOut(
        status="ok" if database_state == "ok" else "degraded",
        environment=settings.environment,
        ai_provider=get_ai_provider().name,
        database=database_state,
    )


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    db: Session = Depends(get_db), candidate: Candidate = Depends(current_candidate)
) -> DashboardOut:
    jobs = db.execute(select(func.count()).select_from(Job)).scalar_one()
    matches = db.execute(
        select(MatchResult)
        .where(MatchResult.candidate_id == candidate.id)
        .options(selectinload(MatchResult.job))
        .order_by(MatchResult.created_at.desc(), MatchResult.id.desc())
    ).scalars().all()

    latest_per_job: dict[int, MatchResult] = {}
    for match in matches:
        latest_per_job.setdefault(match.job_id, match)

    counts = {name: 0 for name in _RECOMMENDATIONS}
    for match in latest_per_job.values():
        if match.recommendation in counts:
            counts[match.recommendation] += 1

    applications = db.execute(
        select(Application)
        .where(Application.candidate_id == candidate.id)
        .options(selectinload(Application.job))
        .order_by(Application.updated_at.desc(), Application.id.desc())
    ).scalars().all()
    app_status_by_job = {a.job_id: a.status for a in applications}

    opportunities: list[DashboardEntry] = []
    for job_id, match in latest_per_job.items():
        job = match.job
        opportunities.append(
            DashboardEntry(
                job_id=job_id,
                title=job.title if job else f"Job {job_id}",
                company=job.company if job else None,
                location=job.location if job else None,
                overall_score=round(match.overall_score, 1),
                recommendation=match.recommendation,
                match_id=match.id,
                application_status=app_status_by_job.get(job_id),
            )
        )
    opportunities.sort(key=lambda entry: entry.overall_score, reverse=True)

    stats = DashboardStats(
        jobs=jobs,
        strong_matches=counts["APPLY"],
        apply=counts["APPLY"],
        apply_with_tailoring=counts["APPLY_WITH_TAILORING"],
        stretch=counts["STRETCH"],
        skip=counts["SKIP"],
        applications=len(applications),
        interviews=sum(1 for a in applications if a.status == ApplicationStatus.INTERVIEW.value),
        offers=sum(1 for a in applications if a.status == ApplicationStatus.OFFER.value),
    )

    profile = candidate_service.to_profile_summary(
        candidate_service.load_candidate(db, candidate.id)
    )
    warnings: list[str] = []
    if not profile.skills:
        warnings.append("Add skills to your profile — matching depends on them.")
    if not profile.experience:
        warnings.append("Add work experience to improve match accuracy.")
    if not profile.education:
        warnings.append("Add education so education requirements can be checked.")

    return DashboardOut(
        stats=stats,
        opportunities=opportunities[:10],
        recent_applications=[ApplicationOut.model_validate(a) for a in applications[:5]],
        profile_complete=not warnings,
        warnings=warnings,
    )


__all__ = ["router"]
