"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings, require_supported_runtime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

settings = get_settings()
require_supported_runtime(settings)

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Evidence-driven career intelligence. Upload a CV, confirm your profile, "
        "add jobs, match, tailor your CV and track applications."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/health", tags=["system"])
def root_health() -> dict:
    return {"status": "ok", "api": settings.api_prefix}


__all__ = ["app"]
