"""Application Strategy service: persistence, refresh and staleness (V2).

Thin orchestration over :mod:`app.services.strategy`. It owns no decision
logic; the deterministic strategy module does.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.ai.base import AIProviderError
from app.models import ApplicationStrategy as ApplicationStrategyRecord
from app.models import Job, MatchResult, StrategyStatus
from app.schemas import ApplicationStrategy, ProfileSummary, StrategyOut, ValidationIssue
from app.services import matching as matching_service
from app.services import strategy as strategy_service


def _loads(raw: str | None) -> list[dict]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _dumps(items) -> str:
    """Serialise Pydantic items or plain dicts to a JSON array."""
    payload = [i.model_dump() if hasattr(i, "model_dump") else i for i in items or []]
    return json.dumps(payload)


def _match_outcome(match: MatchResult):
    """Rebuild a MatchOutcome from the persisted MatchResult row.

    The strategy must consume the *stored* decision, not recompute it, so the
    frozen recommendation is exactly what the candidate saw.
    """
    from matching import MatchItem, MatchOutcome

    def items(raw: str | None) -> list[MatchItem]:
        return [
            MatchItem(
                category=i.get("category", "OTHER"),
                name=i.get("name", ""),
                detail=i.get("detail", ""),
                importance=i.get("importance", "UNKNOWN"),
            )
            for i in _loads(raw)
        ]

    return MatchOutcome(
        technical_score=match.technical_score,
        experience_score=match.experience_score,
        education_score=match.education_score,
        location_score=match.location_score,
        other_score=match.other_score,
        overall_score=match.overall_score,
        recommendation=match.recommendation,
        confidence=match.confidence,
        matched=items(match.matched_items),
        gaps=items(match.gap_items),
        blockers=items(match.blocker_items),
        unknowns=items(match.unknown_items),
        explanation=match.explanation or "",
    )


def build_for_match(
    db: Session, profile: ProfileSummary, job: Job, match: MatchResult
) -> tuple[ApplicationStrategy, list[ValidationIssue]]:
    """Build + validate a strategy for an existing match result."""
    outcome = _match_outcome(match)
    strategy = strategy_service.build_strategy(profile, job, outcome)

    # The model may only phrase the summary; every list stays deterministic.
    if not strategy.decision_summary:
        context = strategy_service.strategy_context(strategy, match.overall_score)
        try:
            narrative = get_ai_provider().compose_strategy_narrative(context)
            strategy.decision_summary = narrative.decision_summary
        except AIProviderError:
            # A narrative is a convenience. The deterministic explanation stands.
            strategy.decision_summary = outcome.explanation

    issues = strategy_service.validate_strategy(strategy, profile)
    return strategy, issues


def persist(
    db: Session,
    candidate_id: int,
    job: Job,
    match: MatchResult,
    strategy: ApplicationStrategy,
    fingerprint: str,
    cv_profile_id: int | None = None,
) -> ApplicationStrategyRecord:
    """Store a new strategy version, marking previous versions STALE.

    History is scoped by ``cv_profile_id``: only a previous version built from
    the *same* evidence is marked STALE, and the version counter is per scope.
    Two profiles therefore hold independent strategy chains instead of flipping
    each other between CURRENT and STALE, and neither destroys the other's
    history. Omitting the argument is the legacy behaviour, unchanged, because
    every pre-existing row is in the null scope.
    """
    latest = latest_for_job(db, candidate_id, job.id, cv_profile_id=cv_profile_id)
    version = 1
    if latest is not None:
        version = latest.version + 1
        latest.status = StrategyStatus.STALE.value

    record = ApplicationStrategyRecord(
        candidate_id=candidate_id,
        job_id=job.id,
        match_id=match.id,
        cv_profile_id=cv_profile_id,
        version=version,
        status=StrategyStatus.CURRENT.value,
        decision=strategy.decision,
        decision_summary=strategy.decision_summary,
        strengths=_dumps(strategy.strengths),
        gaps=_dumps(strategy.gaps),
        blockers=_dumps(strategy.blockers),
        transferable_evidence=_dumps(strategy.transferable_evidence),
        evidence_emphasis=_dumps(strategy.evidence_emphasis),
        claim_restrictions=_dumps(strategy.claim_restrictions),
        actions=_dumps(strategy.actions),
        review_notes=_dumps(strategy.review_notes),
        evidence_fingerprint=fingerprint,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def refresh_if_stale(
    db: Session,
    profile: ProfileSummary,
    job: Job,
    match: MatchResult,
    cv_profile_id: int | None = None,
) -> tuple[ApplicationStrategyRecord, list[ValidationIssue], bool]:
    """Return the current strategy for this evidence scope, rebuilding when stale.

    The lookup is scoped by ``cv_profile_id``, so a profile-aware request reads
    and writes only that profile's chain and can never be handed another
    profile's strategy, nor can a legacy request be handed a profile-specific
    one. The fingerprint is computed from the ``profile`` actually passed in,
    which is the profile-derived summary on the profile-aware path, so it
    already reflects the right matching input.
    """
    candidate_id = match.candidate_id
    record = latest_for_job(db, candidate_id, job.id, cv_profile_id=cv_profile_id)
    fingerprint = strategy_service.evidence_fingerprint(profile, job)

    if record is None:
        strategy, issues = build_for_match(db, profile, job, match)
        record = persist(
            db, candidate_id, job, match, strategy, fingerprint,
            cv_profile_id=cv_profile_id,
        )
        return record, issues, True

    current = (
        record.evidence_fingerprint == fingerprint
        and record.match_id == match.id
        and record.cv_profile_id == cv_profile_id
    )
    if not current:
        strategy, issues = build_for_match(db, profile, job, match)
        record = persist(
            db, candidate_id, job, match, strategy, fingerprint,
            cv_profile_id=cv_profile_id,
        )
        return record, issues, True

    # Stored strategy: re-validate defensively against current evidence.
    strategy = to_strategy(record)
    return record, strategy_service.validate_strategy(strategy, profile), False


def latest_for_job(
    db: Session, candidate_id: int, job_id: int, cv_profile_id: int | None = None
) -> ApplicationStrategyRecord | None:
    """Newest strategy version for a job within one evidence scope.

    ``cv_profile_id=None`` means the shared Candidate record, matching
    :func:`app.services.matching.latest_match`. Every strategy that existed
    before profiles were introduced is in that scope, so legacy lookups return
    exactly the row they returned before.
    """
    stmt = select(ApplicationStrategyRecord).where(
        ApplicationStrategyRecord.candidate_id == candidate_id,
        ApplicationStrategyRecord.job_id == job_id,
    )
    if cv_profile_id is None:
        stmt = stmt.where(ApplicationStrategyRecord.cv_profile_id.is_(None))
    else:
        stmt = stmt.where(
            ApplicationStrategyRecord.cv_profile_id == cv_profile_id
        )
    return db.execute(
        stmt.order_by(
            ApplicationStrategyRecord.version.desc(),
            ApplicationStrategyRecord.id.desc(),
        )
    ).scalars().first()


def strategy_history(
    db: Session, candidate_id: int, job_id: int, cv_profile_id: int | None = None
) -> list[ApplicationStrategyRecord]:
    """Every stored strategy version for a job within one scope, newest first.

    History is never discarded to fit a new provenance field; scoping only
    decides which chain a reader is shown.
    """
    stmt = select(ApplicationStrategyRecord).where(
        ApplicationStrategyRecord.candidate_id == candidate_id,
        ApplicationStrategyRecord.job_id == job_id,
    )
    if cv_profile_id is None:
        stmt = stmt.where(ApplicationStrategyRecord.cv_profile_id.is_(None))
    else:
        stmt = stmt.where(ApplicationStrategyRecord.cv_profile_id == cv_profile_id)
    return list(
        db.execute(
            stmt.order_by(
                ApplicationStrategyRecord.version.desc(),
                ApplicationStrategyRecord.id.desc(),
            )
        ).scalars().all()
    )


def to_strategy(record: ApplicationStrategyRecord) -> ApplicationStrategy:
    return ApplicationStrategy(
        decision=record.decision,
        decision_summary=record.decision_summary or "",
        strengths=_loads(record.strengths),
        gaps=_loads(record.gaps),
        blockers=_loads(record.blockers),
        transferable_evidence=_loads(record.transferable_evidence),
        evidence_emphasis=_loads(record.evidence_emphasis),
        claim_restrictions=_loads(record.claim_restrictions),
        actions=_loads(record.actions),
        review_notes=_loads(record.review_notes),
    )


def to_out(
    record: ApplicationStrategyRecord, issues: list[ValidationIssue] | None = None
) -> StrategyOut:
    payload: dict[str, Any] = {
        "id": record.id,
        "candidate_id": record.candidate_id,
        "job_id": record.job_id,
        "match_id": record.match_id,
        "cv_profile_id": record.cv_profile_id,
        "version": record.version,
        "status": record.status,
        "evidence_fingerprint": record.evidence_fingerprint,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }
    strategy = to_strategy(record)
    payload.update(strategy.model_dump())
    out = StrategyOut.model_validate(payload)
    if issues:
        # Attach grounding findings without widening the strategy contract.
        out = out.model_copy(update={"review_notes": [
            *out.review_notes,
            *[{"severity": i.claim_severity, "statement": i.message} for i in issues],
        ]})
    return out


def current_match(
    db: Session, job_id: int, cv_profile_id: int | None = None
) -> MatchResult | None:
    """The match a strategy for this scope is built from.

    ``cv_profile_id=None`` is the legacy lookup and is unchanged.
    """
    if cv_profile_id is not None:
        return matching_service.latest_match_for_profile(db, job_id, cv_profile_id)
    return matching_service.latest_match(db, job_id)


__all__ = [
    "build_for_match",
    "current_match",
    "latest_for_job",
    "persist",
    "refresh_if_stale",
    "strategy_history",
    "to_out",
    "to_strategy",
]
