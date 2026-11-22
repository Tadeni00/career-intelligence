"""Candidate profile access and mutation."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import (
    Candidate,
    CandidateSkill,
    CareerEvidence,
    Education,
    Experience,
    Project,
    Skill,
)
from app.schemas import (
    CandidateSkillCreate,
    CandidateUpdate,
    EducationCreate,
    EducationUpdate,
    ExperienceCreate,
    ExperienceUpdate,
    ProfileSummary,
    ProjectCreate,
    ProjectUpdate,
)

logger = logging.getLogger(__name__)

_EAGER = (
    Candidate.skills,
    Candidate.experience,
    Candidate.education,
    Candidate.projects,
)


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in value.split(",") if part.strip()]


def _join_list(values: list[str] | None) -> str | None:
    if values is None:
        return None
    return ", ".join(v.strip() for v in values if v and v.strip()) or None


def get_or_create_candidate(db: Session) -> Candidate:
    """V1 is single-user: return the first profile, creating it if needed."""
    candidate = db.execute(select(Candidate).order_by(Candidate.id)).scalars().first()
    if candidate is None:
        candidate = Candidate(name="Candidate")
        db.add(candidate)
        db.commit()
        db.refresh(candidate)
    return candidate


def load_candidate(db: Session, candidate_id: int) -> Candidate:
    stmt = (
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(
            selectinload(Candidate.skills).selectinload(CandidateSkill.skill),
            selectinload(Candidate.experience),
            selectinload(Candidate.education),
            selectinload(Candidate.projects),
        )
    )
    candidate = db.execute(stmt).unique().scalars().first()
    if candidate is None:
        raise LookupError(f"Candidate {candidate_id} not found")
    return candidate


def to_profile_summary(candidate: Candidate) -> ProfileSummary:
    from app.schemas import CandidateSkillOut, EducationOut, ExperienceOut, ProjectOut

    skills = [
        CandidateSkillOut(
            id=link.id,
            name=link.skill.name,
            category=link.skill.category,
            proficiency=link.proficiency,
            years_experience=link.years_experience,
            notes=link.notes,
        )
        for link in candidate.skills
        if link.skill
    ]
    summary = ProfileSummary.model_validate(
        {
            "id": candidate.id,
            "name": candidate.name,
            "professional_title": candidate.professional_title,
            "email": candidate.email,
            "phone": candidate.phone,
            "location": candidate.location,
            "summary": candidate.summary,
            "years_of_experience": candidate.years_of_experience,
            "preferred_roles": _split_list(candidate.preferred_roles),
            "preferred_locations": _split_list(candidate.preferred_locations),
            "remote_preference": candidate.remote_preference,
            "minimum_salary": candidate.minimum_salary,
        }
    )
    summary.skills = sorted(skills, key=lambda s: s.name.lower())

    summary.experience = [
        ExperienceOut.model_validate(
            {
                "id": e.id,
                "company": e.company,
                "title": e.title,
                "start_date": e.start_date,
                "end_date": e.end_date,
                "description": e.description,
                "is_current": e.is_current,
            }
        )
        for e in candidate.experience
    ]
    summary.education = [
        EducationOut.model_validate(
            {
                "id": e.id,
                "institution": e.institution,
                "degree": e.degree,
                "field": e.field,
                "start_date": e.start_date,
                "end_date": e.end_date,
                "description": e.description,
            }
        )
        for e in candidate.education
    ]
    summary.projects = [
        ProjectOut.model_validate(
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "technologies": _split_list(p.technologies),
                "url": p.url,
            }
        )
        for p in candidate.projects
    ]
    return summary


def update_candidate(db: Session, candidate: Candidate, payload: CandidateUpdate) -> Candidate:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "preferred_roles":
            candidate.preferred_roles = _join_list(value)
        elif key == "preferred_locations":
            candidate.preferred_locations = _join_list(value)
        else:
            setattr(candidate, key, value)
    db.commit()
    db.refresh(candidate)
    return candidate


# ------------------------------------------------------------------- skills


def get_or_create_skill(db: Session, name: str, category: str | None) -> Skill:
    clean = name.strip()
    skill = db.execute(select(Skill).where(Skill.name == clean)).scalars().first()
    if skill is None:
        skill = Skill(name=clean, category=category)
        db.add(skill)
        db.flush()
    elif category and not skill.category:
        skill.category = category
    return skill


def add_skill(
    db: Session, candidate: Candidate, payload: CandidateSkillCreate
) -> CandidateSkill:
    skill = get_or_create_skill(db, payload.name, payload.category)
    existing = db.execute(
        select(CandidateSkill).where(
            CandidateSkill.candidate_id == candidate.id, CandidateSkill.skill_id == skill.id
        )
    ).scalars().first()
    if existing is not None:
        existing.proficiency = payload.proficiency or existing.proficiency
        existing.years_experience = (
            payload.years_experience
            if payload.years_experience is not None
            else existing.years_experience
        )
        existing.notes = payload.notes or existing.notes
        db.commit()
        return existing
    link = CandidateSkill(
        candidate_id=candidate.id,
        skill_id=skill.id,
        proficiency=payload.proficiency,
        years_experience=payload.years_experience,
        notes=payload.notes,
    )
    db.add(link)
    db.add(
        CareerEvidence(
            candidate_id=candidate.id,
            source_type="SKILL",
            claim=payload.name,
            evidence_text=payload.notes or "Confirmed manually by the candidate.",
            confidence=1.0,
        )
    )
    db.commit()
    db.refresh(link)
    return link


def remove_skill(db: Session, link: CandidateSkill) -> None:
    db.delete(link)
    db.commit()


# --------------------------------------------------------------- experience


def add_experience(db: Session, candidate: Candidate, payload: ExperienceCreate) -> Experience:
    record = Experience(
        candidate_id=candidate.id,
        company=payload.company,
        title=payload.title,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
        is_current=payload.is_current or not payload.end_date,
    )
    db.add(record)
    db.flush()
    db.add(
        CareerEvidence(
            candidate_id=candidate.id,
            source_type="EXPERIENCE",
            source_id=record.id,
            claim=f"{payload.title} at {payload.company}",
            evidence_text=payload.description or "",
            confidence=1.0,
        )
    )
    db.commit()
    db.refresh(record)
    return record


def update_experience(db: Session, record: Experience, payload: ExperienceUpdate) -> Experience:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    if payload.end_date is not None and not record.end_date.strip():
        record.is_current = True
    db.commit()
    db.refresh(record)
    return record


def remove_experience(db: Session, record: Experience) -> None:
    db.delete(record)
    db.commit()


# ---------------------------------------------------------------- education


def add_education(db: Session, candidate: Candidate, payload: EducationCreate) -> Education:
    record = Education(
        candidate_id=candidate.id,
        institution=payload.institution,
        degree=payload.degree,
        field=payload.field,
        start_date=payload.start_date,
        end_date=payload.end_date,
        description=payload.description,
    )
    db.add(record)
    db.flush()
    db.add(
        CareerEvidence(
            candidate_id=candidate.id,
            source_type="EDUCATION",
            source_id=record.id,
            claim=f"{payload.degree or ''} {payload.field or ''} at {payload.institution}".strip(),
            evidence_text=payload.description or "",
            confidence=1.0,
        )
    )
    db.commit()
    db.refresh(record)
    return record


def update_education(db: Session, record: Education, payload: EducationUpdate) -> Education:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


def remove_education(db: Session, record: Education) -> None:
    db.delete(record)
    db.commit()


# ----------------------------------------------------------------- projects


def add_project(db: Session, candidate: Candidate, payload: ProjectCreate) -> Project:
    record = Project(
        candidate_id=candidate.id,
        name=payload.name,
        description=payload.description,
        technologies=_join_list(payload.technologies),
        url=payload.url,
    )
    db.add(record)
    db.flush()
    db.add(
        CareerEvidence(
            candidate_id=candidate.id,
            source_type="PROJECT",
            source_id=record.id,
            claim=payload.name,
            evidence_text=payload.description or "",
            confidence=1.0,
        )
    )
    db.commit()
    db.refresh(record)
    return record


def update_project(db: Session, record: Project, payload: ProjectUpdate) -> Project:
    data = payload.model_dump(exclude_unset=True)
    for key, value in data.items():
        if key == "technologies":
            record.technologies = _join_list(value)
        else:
            setattr(record, key, value)
    db.commit()
    db.refresh(record)
    return record


def remove_project(db: Session, record: Project) -> None:
    db.delete(record)
    db.commit()


def profile_completeness(profile: ProfileSummary) -> float:
    """Fraction of core profile areas that hold usable information."""
    checks = (
        bool(profile.professional_title),
        bool(profile.summary),
        bool(profile.location),
        profile.years_of_experience is not None,
        bool(profile.skills),
        bool(profile.experience),
        bool(profile.education),
        bool(profile.email),
    )
    return sum(1 for check in checks if check) / len(checks)


__all__ = [
    "add_education",
    "add_experience",
    "add_project",
    "add_skill",
    "get_or_create_candidate",
    "get_or_create_skill",
    "load_candidate",
    "profile_completeness",
    "remove_education",
    "remove_experience",
    "remove_project",
    "remove_skill",
    "to_profile_summary",
    "update_candidate",
    "update_education",
    "update_experience",
    "update_project",
]
