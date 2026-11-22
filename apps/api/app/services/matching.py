"""Matching service: bridges ORM records and the matching package."""

from __future__ import annotations

from dataclasses import dataclass

from matching import (
    CandidateEducation,
    CandidateExperience,
    CandidateProfile,
    CandidateSkill,
    JobProfile,
    MatchingEngine,
    MatchSettings,
    MatchWeights,
    RecommendationPolicy,
    Requirement,
)
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Candidate, Job, MatchResult
from app.schemas import CVProfileData
from app.services import extraction as extraction_service

_TYPE_MAP = {
    "SKILL": "SKILL",
    "EXPERIENCE": "EXPERIENCE",
    "EDUCATION": "EDUCATION",
    "LOCATION": "LOCATION",
    "OTHER": "OTHER",
}


def build_settings() -> MatchSettings:
    """Build matching settings from application configuration."""
    config = get_settings()
    return MatchSettings(
        weights=MatchWeights(
            technical=config.match_weight_technical,
            experience=config.match_weight_experience,
            education=config.match_weight_education,
            location=config.match_weight_location,
            other=config.match_weight_other,
        ).normalised(),
        policy=RecommendationPolicy(
            apply_threshold=config.threshold_apply,
            apply_with_tailoring_threshold=config.threshold_apply_with_tailoring,
            stretch_threshold=config.threshold_stretch,
        ),
    )


def to_candidate_profile(candidate: Candidate) -> CandidateProfile:
    from app.services.candidate import to_profile_summary

    summary = to_profile_summary(candidate)
    return CandidateProfile(
        id=candidate.id,
        name=summary.name,
        professional_title=summary.professional_title or "",
        location=summary.location or "",
        summary=summary.summary or "",
        years_of_experience=summary.years_of_experience,
        preferred_roles=summary.preferred_roles,
        preferred_locations=summary.preferred_locations,
        remote_preference=summary.remote_preference or "",
        minimum_salary=summary.minimum_salary,
        skills=[
            CandidateSkill(
                id=skill.id,
                name=skill.name,
                category=skill.category or "",
                proficiency=skill.proficiency or "",
                years_experience=skill.years_experience,
            )
            for skill in summary.skills
        ],
        experience=[
            CandidateExperience(
                id=item.id,
                company=item.company,
                title=item.title,
                start_date=item.start_date or "",
                end_date=item.end_date or "",
                description=item.description or "",
            )
            for item in summary.experience
        ],
        education=[
            CandidateEducation(
                id=item.id,
                institution=item.institution,
                degree=item.degree or "",
                field=item.field or "",
                start_date=item.start_date or "",
                end_date=item.end_date or "",
                description=item.description or "",
            )
            for item in summary.education
        ],
    )


@dataclass(frozen=True)
class MatchingInput:
    """The candidate evidence a match is about to be calculated from.

    ``cv_profile_id`` is the provenance written onto the stored result: None for
    the shared Candidate record, the profile id when a confirmed profile was
    explicitly selected. The two are never combined.
    """

    profile: CandidateProfile
    cv_profile_id: int | None = None


def to_profile_candidate_profile(
    data: CVProfileData, cv_profile_id: int
) -> CandidateProfile:
    """Build the engine's candidate input from one confirmed CV profile.

    Every field comes from ``data``. Nothing is read from the shared Candidate
    record, so a selected profile can never be partly filled in from the legacy
    profile and no value is invented.

    ``years_of_experience`` is passed through exactly as confirmed. When it is
    absent the engine's own established derivation (``MatchingEngine``'s
    estimate from recorded experience) applies, as it already does for a
    candidate that has never had the field set.
    """
    return CandidateProfile(
        id=cv_profile_id,
        name=data.name or "",
        professional_title=data.professional_title or "",
        location=data.location or "",
        summary=data.summary or "",
        years_of_experience=data.years_of_experience,
        preferred_roles=list(data.preferred_roles),
        preferred_locations=list(data.preferred_locations),
        remote_preference=data.remote_preference or "",
        minimum_salary=data.minimum_salary,
        skills=[
            CandidateSkill(
                id=index,
                name=skill.name,
                category=skill.category or "",
                proficiency=skill.proficiency or "",
                years_experience=skill.years_experience,
            )
            for index, skill in enumerate(data.skills, start=1)
        ],
        experience=[
            CandidateExperience(
                id=index,
                company=item.company,
                title=item.title,
                start_date=item.start_date or "",
                end_date=item.end_date or "",
                description=item.description or "",
            )
            for index, item in enumerate(data.experience, start=1)
        ],
        education=[
            CandidateEducation(
                id=index,
                institution=item.institution,
                degree=item.degree or "",
                field=item.field or "",
                start_date=item.start_date or "",
                end_date=item.end_date or "",
                description=item.description or "",
            )
            for index, item in enumerate(data.education, start=1)
        ],
    )


def resolve_matching_input(
    db: Session, candidate: Candidate, cv_profile_id: int | None
) -> MatchingInput:
    """Resolve which candidate evidence a match request refers to.

    ``cv_profile_id is None`` is the legacy path and is unchanged.

    When an id is supplied it is resolved through the owning candidate, so
    another candidate's profile is reported as not found. A profile that is not
    confirmed is rejected as a conflict. Neither case ever falls back to the
    shared Candidate record.
    """
    if cv_profile_id is None:
        return MatchingInput(profile=to_candidate_profile(candidate))

    # Imported here to keep the service import graph acyclic.
    from app.services import cv_profile as profile_service

    # One gate for every profile-aware path: ownership, archived, confirmed and
    # readable data are all checked in one place, so no caller can fall back to
    # the shared Candidate record.
    profile, data = profile_service.resolve_confirmed_profile(
        db, candidate, cv_profile_id
    )

    return MatchingInput(
        profile=to_profile_candidate_profile(data, profile.id),
        cv_profile_id=profile.id,
    )


def to_job_profile(job: Job) -> JobProfile:
    return JobProfile(
        id=job.id,
        title=job.title,
        company=job.company or "",
        location=job.location or "",
        remote_status=job.remote_status or "",
        employment_type=job.employment_type or "",
        description=job.description or "",
        salary_min=job.salary_min,
        salary_max=job.salary_max,
        requirements=[
            Requirement(
                id=req.id,
                type=_TYPE_MAP.get(req.requirement_type, "OTHER"),
                name=req.name,
                description=req.description or "",
                importance=req.importance,
                years_required=req.years_required,
            )
            for req in job.requirements
        ],
    )


def run_match(
    db: Session, candidate: Candidate, job: Job, cv_profile_id: int | None = None
) -> MatchResult:
    """Score a job against the selected candidate evidence and persist the result.

    ``cv_profile_id`` selects the input. Omitting it keeps the legacy behaviour
    exactly: the shared Candidate record is scored and the stored row carries a
    null profile identifier.

    Supplying it scores that confirmed profile alone and stamps the row with
    its id, so two profiles produce two independently attributable results for
    the same job. Each call inserts a new row; no existing result is updated or
    replaced.

    V3.1 zero-requirement guard: a job whose requirement set is empty for any
    reason other than a confirmed empty extraction cannot be scored. This is the
    last point before the scorer, so it is where a failed extraction is stopped.
    """
    extraction_service.assert_matchable(job)
    matching_input = resolve_matching_input(db, candidate, cv_profile_id)
    engine = MatchingEngine(build_settings())
    outcome, _dimensions = engine.match(matching_input.profile, to_job_profile(job))

    result = MatchResult(
        candidate_id=candidate.id,
        job_id=job.id,
        technical_score=outcome.technical_score,
        experience_score=outcome.experience_score,
        education_score=outcome.education_score,
        location_score=outcome.location_score,
        other_score=outcome.other_score,
        overall_score=outcome.overall_score,
        recommendation=outcome.recommendation,
        confidence=outcome.confidence,
        matched_items=_dumps(outcome.matched),
        gap_items=_dumps(outcome.gaps),
        blocker_items=_dumps(outcome.blockers),
        unknown_items=_dumps(outcome.unknowns),
        explanation=outcome.explanation,
        cv_profile_id=matching_input.cv_profile_id,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    return result


def latest_match(db: Session, job_id: int) -> MatchResult | None:
    """The most recent match calculated from the shared Candidate record.

    Scoped to null-profile rows. Before CV profiles existed every row was
    null-profile, so this returned exactly the same row as before; with the
    filter it stays that way. It now also guarantees a caller who never selected
    a profile is never handed evidence calculated from one, which is what keeps
    a legacy request's meaning stable.
    """
    from sqlalchemy import select

    return db.execute(
        select(MatchResult)
        .where(MatchResult.job_id == job_id, MatchResult.cv_profile_id.is_(None))
        .order_by(MatchResult.created_at.desc(), MatchResult.id.desc())
    ).scalars().first()


def latest_match_for_profile(
    db: Session, job_id: int, cv_profile_id: int
) -> MatchResult | None:
    """The most recent match a specific CV profile produced for a job.

    Scoped by ``cv_profile_id``, so it can never return another profile's result
    and never returns a historical null-profile result.
    """
    from sqlalchemy import select

    return db.execute(
        select(MatchResult)
        .where(
            MatchResult.job_id == job_id,
            MatchResult.cv_profile_id == cv_profile_id,
        )
        .order_by(MatchResult.created_at.desc(), MatchResult.id.desc())
    ).scalars().first()


def _dumps(items) -> str:
    import json

    return json.dumps([item.to_dict() for item in items])


__all__ = [
    "MatchingInput",
    "build_settings",
    "latest_match",
    "latest_match_for_profile",
    "resolve_matching_input",
    "run_match",
    "to_candidate_profile",
    "to_job_profile",
    "to_profile_candidate_profile",
]
