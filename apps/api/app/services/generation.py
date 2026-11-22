"""Tailored CV and cover letter generation."""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.ai.base import AIProviderError
from app.core.config import get_settings
from app.core.storage import sanitise_filename
from app.models import Candidate, CoverLetter, Job, TailoredCV
from app.schemas import CVAnalysis, ProfileSummary
from app.services.documents import render_tailored_cv_docx
from app.services.validation import validate_cover_letter, validate_tailored_cv

logger = logging.getLogger(__name__)


def analyse_for_job(
    db: Session, candidate: Candidate, job: Job, profile: ProfileSummary
) -> CVAnalysis:
    provider = get_ai_provider()
    try:
        return provider.analyze_cv_for_job(
            profile=profile,
            job_description=job.description or "",
            job_title=job.title,
            company=job.company,
        )
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"CV analysis failed: {exc}",
        ) from exc


def strategy_constraints(
    db: Session,
    job: Job,
    profile: ProfileSummary | None = None,
    cv_profile_id: int | None = None,
) -> str:
    """Structured do-not-claim / emphasis constraints from the V2 strategy.

    These are prompt constraints only. Per spec section 13 the deterministic
    validator remains the authority; the prompt is not a safety mechanism.

    ``profile`` is the candidate evidence the caller is generating from. It is
    used directly rather than re-derived from the Candidate row, which is what
    keeps a profile-aware document free of shared-Candidate evidence. When
    ``cv_profile_id`` is supplied the strategy is built from that profile's own
    match, not the legacy one.
    """
    from app.services import strategy_store

    if cv_profile_id is not None:
        from app.services import matching as matching_service

        match = matching_service.latest_match_for_profile(db, job.id, cv_profile_id)
    else:
        match = strategy_store.current_match(db, job.id)
    if match is None:
        return ""

    if profile is None:
        from app.services.candidate import to_profile_summary

        candidate = db.get(Candidate, match.candidate_id)
        if candidate is None:
            return ""
        profile = to_profile_summary(candidate)

    record, _issues, _rebuilt = strategy_store.refresh_if_stale(
        db, profile, job, match, cv_profile_id=cv_profile_id
    )
    strategy = strategy_store.to_strategy(record)

    lines: list[str] = []
    if strategy.evidence_emphasis:
        top = ", ".join(
            f"{e.evidence_ids[0]}" for e in strategy.evidence_emphasis[:5]
            if e.evidence_ids
        )
        if top:
            lines.append(f"Prioritise this confirmed evidence: {top}.")
    if strategy.claim_restrictions:
        subjects = ", ".join(r.subject for r in strategy.claim_restrictions[:10])
        lines.append(
            "Do NOT claim or imply any of the following, because they are not "
            f"established in the candidate's confirmed evidence: {subjects}."
        )
    return " ".join(lines)


def next_version(db: Session, candidate_id: int, job_id: int) -> int:
    current = db.execute(
        select(func.max(TailoredCV.version)).where(
            TailoredCV.candidate_id == candidate_id, TailoredCV.job_id == job_id
        )
    ).scalar()
    return int(current or 0) + 1


def generate_tailored_cv(
    db: Session,
    candidate: Candidate,
    job: Job,
    profile: ProfileSummary,
    source_cv_id: int | None = None,
    cv_profile_id: int | None = None,
) -> TailoredCV:
    """Generate a tailored CV from ``profile`` and record where it came from.

    ``cv_profile_id`` is provenance only: the caller has already resolved the
    profile and built ``profile`` from it, and the two must agree. It is stamped
    on the row so the document stays attributable to that profile, and NULL
    keeps the legacy meaning of "generated from the shared Candidate record".
    """
    settings = get_settings()
    provider = get_ai_provider()

    analysis = analyse_for_job(db, candidate, job, profile)
    constraints = strategy_constraints(db, job, profile, cv_profile_id)
    try:
        content = provider.tailor_cv(
            profile=profile,
            job_description=job.description or "",
            job_title=job.title,
            analysis=analysis,
            constraints=constraints,
        )
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"CV tailoring failed: {exc}",
        ) from exc

    report = validate_tailored_cv(content, profile, job.description or "")

    version = next_version(db, candidate.id, job.id)
    stem = sanitise_filename(f"{job.company or 'company'}-{job.title}")
    filename = f"{stem}-cv-v{version}.docx"
    stored_name = f"{uuid.uuid4().hex}.docx"
    path = settings.generated_dir / stored_name
    docx_bytes = render_tailored_cv_docx(content, profile.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(docx_bytes)

    record = TailoredCV(
        candidate_id=candidate.id,
        job_id=job.id,
        source_cv_id=source_cv_id,
        cv_profile_id=cv_profile_id,
        version=version,
        filename=filename,
        storage_path=str(path),
        summary=content.summary,
        analysis=analysis.model_dump_json(),
        changes_summary=json.dumps(content.changes_summary),
        validation_status=report.status.value,
        validation_issues=json.dumps([i.model_dump() for i in report.issues]),
        content_json=content.model_dump_json(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def regenerate_tailored_cv(
    db: Session, record: TailoredCV, candidate: Candidate, job: Job, profile: ProfileSummary
) -> TailoredCV:
    """Regenerate from ``profile``, carrying the original document's provenance.

    A regeneration of a profile-aware document stays profile-aware; it is never
    silently downgraded to the shared Candidate record.
    """
    return generate_tailored_cv(
        db,
        candidate,
        job,
        profile,
        source_cv_id=record.source_cv_id,
        cv_profile_id=record.cv_profile_id,
    )


def generate_cover_letter(
    db: Session,
    candidate: Candidate,
    job: Job,
    profile: ProfileSummary,
    cv_profile_id: int | None = None,
) -> CoverLetter:
    """Generate a cover letter from ``profile`` and record where it came from.

    Same provenance contract as :func:`generate_tailored_cv`.
    """
    provider = get_ai_provider()
    constraints = strategy_constraints(db, job, profile, cv_profile_id)
    try:
        content = provider.generate_cover_letter(
            profile=profile,
            job_description=job.description or "",
            job_title=job.title,
            company=job.company,
            constraints=constraints,
        )
    except AIProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cover letter generation failed: {exc}",
        ) from exc

    report = validate_cover_letter(
        content,
        profile,
        job.title,
        job.company,
        job_description=job.description or "",
    )
    record = CoverLetter(
        candidate_id=candidate.id,
        job_id=job.id,
        cv_profile_id=cv_profile_id,
        content=content,
        validation_status=report.status.value,
        validation_issues=json.dumps([i.model_dump() for i in report.issues]),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def parse_issues(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def read_generated(path: str) -> Path:
    """Resolve a generated document path, refusing anything outside storage."""
    settings = get_settings()
    resolved = Path(path).resolve()
    root = settings.generated_dir.resolve()
    if root not in resolved.parents:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    if not resolved.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found."
        )
    return resolved


__all__ = [
    "analyse_for_job",
    "generate_cover_letter",
    "generate_tailored_cv",
    "parse_issues",
    "read_generated",
    "regenerate_tailored_cv",
]
