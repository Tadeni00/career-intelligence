"""API router assembly."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import (
    applications,
    candidate,
    cv_profiles,
    cvs,
    dashboard,
    jobs,
    matches,
    materials,
    strategy,
    external_jobs,
)

api_router = APIRouter()
api_router.include_router(dashboard.router)
api_router.include_router(candidate.router)
api_router.include_router(cvs.router)
api_router.include_router(cv_profiles.router)
api_router.include_router(jobs.router)
api_router.include_router(matches.router)
api_router.include_router(strategy.router)
api_router.include_router(materials.router)
api_router.include_router(applications.router)
api_router.include_router(external_jobs.router)

__all__ = ["api_router"]
