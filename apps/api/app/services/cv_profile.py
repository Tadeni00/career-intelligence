"""Independent CV profiles for one candidate.

A CV profile owns its own file reference, extracted text, unconfirmed extraction
and confirmed candidate information. Nothing in this module reads or writes the
shared ``Candidate`` row, so uploading, extracting or confirming a profile can
never overwrite the candidate's existing evidence, and two profiles of the same
candidate can never affect each other.

Selection is deliberately not implemented here. Nothing in this module marks a
profile as active, and the shared ``Candidate`` remains a first-class matching
and generation input in its own right.

Lifecycle: a profile is retired by archiving it, never by hard deletion. The
foreign keys from ``match_results``, ``tailored_cvs`` and ``cover_letters`` all
RESTRICT, so the database refuses to drop a profile that dependent history still
cites. Archiving keeps those records attributable and merely stops the profile
from being used for new work.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.models import Candidate, CVProfile, CVProfileStatus
from app.schemas import (
    CandidateSkillOut,
    CVProfileConfirmRequest,
    CVProfileData,
    CVProfileEducation,
    CVProfileExperience,
    CVProfileProject,
    CVProfileSkill,
    EducationOut,
    ExperienceOut,
    ExtractedCV,
    ProfileSummary,
    ProjectOut,
)
from app.services.cv import persist_upload
from app.services.documents import DocumentExtractionError, extract_text

logger = logging.getLogger(__name__)

_MAX_LABEL = 255


def _default_label(filename: str) -> str:
    return filename[:_MAX_LABEL]


def create_profile(
    db: Session,
    candidate: Candidate,
    upload: UploadFile,
    label: str | None = None,
) -> CVProfile:
    """Store an upload and open a new, empty profile for it.

    The profile starts at AWAITING_EXTRACTION and holds no candidate
    information yet. Creating one never touches ``candidate`` or any other
    profile.
    """
    stored = persist_upload(upload)

    profile = CVProfile(
        candidate_id=candidate.id,
        cv_id=None,
        label=(label or _default_label(stored.filename))[:_MAX_LABEL],
        status=CVProfileStatus.AWAITING_EXTRACTION.value,
        file_type=stored.file_type,
        storage_path=stored.storage_path,
        content_hash=stored.content_hash,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def list_profiles(
    db: Session, candidate: Candidate, include_archived: bool = False
) -> list[CVProfile]:
    """Every profile owned by this candidate, newest first.

    Archived profiles are excluded by default because they are retired, but they
    remain fully readable through :func:`get_profile` so every match and
    document that cites them stays attributable. Pass ``include_archived`` to
    see them in the listing too.
    """
    stmt = select(CVProfile).where(CVProfile.candidate_id == candidate.id)
    if not include_archived:
        stmt = stmt.where(CVProfile.archived_at.is_(None))
    return list(
        db.execute(
            stmt.order_by(CVProfile.created_at.desc(), CVProfile.id.desc())
        ).scalars().all()
    )


def archive_profile(db: Session, candidate: Candidate, profile_id: int) -> CVProfile:
    """Retire a profile while keeping every record that cites it attributable.

    Archiving is the only lifecycle operation offered. There is deliberately no
    hard-delete: dependent matches and documents would either be erased or, with
    a SET NULL foreign key, silently relabelled as legacy. The foreign keys
    RESTRICT back that up at the storage layer.
    """
    profile = get_profile(db, candidate, profile_id)
    if profile.archived_at is None:
        profile.archived_at = datetime.now(UTC)
        db.commit()
        db.refresh(profile)
    return profile


def delete_profile(db: Session, candidate: Candidate, profile_id: int) -> None:
    """Hard-delete a profile, but only if nothing references it.

    Every table with a ``cv_profile_id`` column has ON DELETE RESTRICT.
    Deleting a profile that is still cited would either erase that history
    or leave broken references. This function checks all five tables and
    raises if any row points to the profile.
    """
    from app.models import (
        Application,
        ApplicationStrategy,
        CoverLetter,
        MatchResult,
        TailoredCV,
    )

    profile = get_profile(db, candidate, profile_id)

    refs = []
    counts = [
        (MatchResult, "match_results"),
        (TailoredCV, "tailored_cvs"),
        (CoverLetter, "cover_letters"),
        (ApplicationStrategy, "application_strategies"),
        (Application, "applications"),
    ]
    for model, name in counts:
        c = db.execute(
            select(func.count(model.id)).where(model.cv_profile_id == profile_id)
        ).scalar()
        if c:
            refs.append(f"{name}: {c}")

    if refs:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Cannot delete CV profile "
                f"{profile_id}: it is referenced by {', '.join(refs)}. "
                "Archive it instead, or delete the referencing records first."
            ),
        )

    db.delete(profile)
    db.commit()


def resolve_confirmed_profile(
    db: Session, candidate: Candidate, cv_profile_id: int
) -> tuple[CVProfile, CVProfileData]:
    """Resolve a profile through its owner and return its confirmed data.

    The single gate every profile-aware path goes through. A profile that does
    not exist, belongs to another candidate, is not confirmed, is archived, or
    has unreadable confirmed data is rejected here, so no caller can fall back
    to the shared Candidate record by accident.
    """
    profile = get_profile(db, candidate, cv_profile_id)

    if profile.archived_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"CV profile {cv_profile_id} is archived and can no longer be "
                "used for new matches or documents. Its history is retained."
            ),
        )

    if profile.status != CVProfileStatus.CONFIRMED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"CV profile {cv_profile_id} is {profile.status}, not "
                f"{CVProfileStatus.CONFIRMED.value}. Only a confirmed profile "
                "can be used."
            ),
        )

    data = read_confirmed(profile)
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"CV profile {cv_profile_id} has no readable confirmed data "
                "and cannot be used."
            ),
        )
    return profile, data


def to_profile_summary(data: CVProfileData, profile_id: int | None = None) -> ProfileSummary:
    """Project a confirmed profile onto the schema document generation consumes.

    Generation, analysis and validation all already take a ``ProfileSummary``,
    so supplying one built purely from the profile keeps that whole pipeline -
    including every existing validation rule - unchanged, while guaranteeing no
    field can come from the shared Candidate record.
    """
    return ProfileSummary(
        id=profile_id,
        name=data.name or "Candidate",
        professional_title=data.professional_title,
        email=data.email,
        phone=data.phone,
        location=data.location,
        summary=data.summary,
        years_of_experience=data.years_of_experience,
        preferred_roles=list(data.preferred_roles),
        preferred_locations=list(data.preferred_locations),
        remote_preference=data.remote_preference,
        minimum_salary=data.minimum_salary,
        skills=[
            CandidateSkillOut(
                id=index,
                name=skill.name,
                category=skill.category,
                proficiency=skill.proficiency,
                years_experience=skill.years_experience,
            )
            for index, skill in enumerate(data.skills, start=1)
        ],
        experience=[
            ExperienceOut(
                id=index,
                company=item.company,
                title=item.title,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description,
                # Mirrors CandidateExperience.is_current: an open-ended role is
                # the current one.
                is_current=not (item.end_date or "").strip(),
            )
            for index, item in enumerate(data.experience, start=1)
        ],
        education=[
            EducationOut(
                id=index,
                institution=item.institution,
                degree=item.degree,
                field=item.field,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description,
            )
            for index, item in enumerate(data.education, start=1)
        ],
        projects=[
            ProjectOut(
                id=index,
                name=item.name,
                description=item.description,
                technologies=list(item.technologies),
            )
            for index, item in enumerate(data.projects, start=1)
        ],
    )


def get_profile(db: Session, candidate: Candidate, profile_id: int) -> CVProfile:
    """Resolve a profile through its owning candidate.

    A profile belonging to another candidate is reported as not found, exactly
    like a profile that does not exist, so an identifier cannot be used to probe
    for another candidate's data.
    """
    profile = db.execute(
        select(CVProfile).where(
            CVProfile.id == profile_id, CVProfile.candidate_id == candidate.id
        )
    ).scalars().first()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CV profile {profile_id} not found.",
        )
    return profile


def extract_profile(db: Session, profile: CVProfile) -> CVProfile:
    """Extract this profile's own text and structure.

    The result is stored as an unconfirmed extraction. It is never applied to the
    shared candidate and never applied automatically.
    """
    profile.status = CVProfileStatus.AWAITING_EXTRACTION.value
    profile.error_message = None
    db.commit()

    try:
        with open(profile.storage_path, "rb") as handle:
            data = handle.read()
        text = extract_text(data, profile.file_type)
    except DocumentExtractionError as exc:
        profile.status = CVProfileStatus.EXTRACTION_FAILED.value
        profile.error_message = str(exc)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    extracted = get_ai_provider().extract_cv(text)

    profile.extracted_text = text
    profile.extracted_data = extracted.model_dump_json()
    profile.extracted_issues = json.dumps(extracted.issues)
    profile.extracted_at = datetime.now(UTC)
    # Issues are reported on the profile rather than folded into its status:
    # the owner still has to review and confirm, with or without issues.
    profile.status = CVProfileStatus.AWAITING_REVIEW.value
    db.commit()
    db.refresh(profile)
    return profile


def _extracted_to_profile_data(extracted: ExtractedCV) -> CVProfileData:
    """Project an extraction onto the confirmed-profile shape.

    This is a projection, not an interpretation: nothing is invented and every
    field that the extraction did not supply stays empty.
    """
    return CVProfileData(
        name=extracted.name,
        professional_title=extracted.professional_title,
        email=extracted.email,
        phone=extracted.phone,
        location=extracted.location,
        summary=extracted.summary,
        experience=[
            CVProfileExperience(
                company=item.company,
                title=item.title,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description
                or " ".join(item.responsibilities + item.achievements)
                or None,
            )
            for item in extracted.experience
        ],
        education=[
            CVProfileEducation(
                institution=item.institution,
                degree=item.degree,
                field=item.field,
                start_date=item.start_date,
                end_date=item.end_date,
                description=item.description,
            )
            for item in extracted.education
        ],
        projects=[
            CVProfileProject(
                name=item.name,
                description=item.description,
                technologies=item.technologies,
            )
            for item in extracted.projects
        ],
        skills=[
            CVProfileSkill(name=item.name, category=item.category)
            for item in extracted.skills
        ],
    )


def confirm_profile(
    db: Session, profile: CVProfile, payload: CVProfileConfirmRequest
) -> CVProfile:
    """Confirm this profile's candidate information, optionally correcting it.

    Every field omitted from ``payload`` is taken from the extraction, so a
    partial correction is never destructive. The confirmed payload is written to
    this profile only: the shared ``Candidate`` row and every other profile are
    left exactly as they were.
    """
    if not profile.extracted_data:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This profile has no extraction to confirm. "
                "Run extraction on the profile first."
            ),
        )

    try:
        extracted = ExtractedCV.model_validate_json(profile.extracted_data)
    except ValueError as exc:
        logger.warning(
            "CV profile %s has unreadable extraction data: %s", profile.id, exc
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This profile's extraction could not be read; re-run extraction.",
        ) from exc

    data = _extracted_to_profile_data(extracted)

    # Only fields the caller actually supplied are overridden. ``None`` means
    # "not supplied" rather than "clear this value". Overrides are merged as
    # plain data and re-validated, so a supplied value is type-checked exactly
    # like an extracted one.
    overrides = payload.model_dump(exclude_unset=True, exclude_none=True)
    label = overrides.pop("label", None)
    merged = data.model_dump()
    merged.update(overrides)
    data = CVProfileData.model_validate(merged)

    if label:
        profile.label = label[:_MAX_LABEL]

    profile.confirmed_data = data.model_dump_json()
    profile.status = CVProfileStatus.CONFIRMED.value
    profile.confirmed_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)
    return profile


def read_extracted(profile: CVProfile) -> ExtractedCV | None:
    if not profile.extracted_data:
        return None
    try:
        return ExtractedCV.model_validate_json(profile.extracted_data)
    except ValueError:
        logger.warning("CV profile %s has unreadable extraction data.", profile.id)
        return None


def read_issues(profile: CVProfile) -> list[str]:
    if not profile.extracted_issues:
        return []
    try:
        parsed = json.loads(profile.extracted_issues)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def read_confirmed(profile: CVProfile) -> CVProfileData | None:
    if not profile.confirmed_data:
        return None
    try:
        return CVProfileData.model_validate_json(profile.confirmed_data)
    except ValueError:
        logger.warning("CV profile %s has unreadable confirmed data.", profile.id)
        return None


__all__ = [
    "archive_profile",
    "confirm_profile",
    "create_profile",
    "extract_profile",
    "get_profile",
    "list_profiles",
    "read_confirmed",
    "read_extracted",
    "read_issues",
    "resolve_confirmed_profile",
    "to_profile_summary",
]
