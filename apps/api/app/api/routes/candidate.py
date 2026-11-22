"""Candidate profile endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_candidate
from app.db.session import get_db
from app.models import Candidate, CandidateSkill, Education, Experience, Project
from app.schemas import (
    CandidateSkillCreate,
    CandidateSkillOut,
    CandidateUpdate,
    EducationCreate,
    EducationOut,
    EducationUpdate,
    ExperienceCreate,
    ExperienceOut,
    ExperienceUpdate,
    ProfileSummary,
    ProjectCreate,
    ProjectOut,
    ProjectUpdate,
)
from app.services import candidate as service

router = APIRouter(prefix="/candidate", tags=["candidate"])


def _owned(model, db: Session, record_id: int, candidate: Candidate, label: str):
    record = db.get(model, record_id)
    if record is None or record.candidate_id != candidate.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"{label} {record_id} not found."
        )
    return record


# ------------------------------------------------------------------- profile


@router.get("", response_model=ProfileSummary)
def get_profile(
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> ProfileSummary:
    return service.to_profile_summary(service.load_candidate(db, candidate.id))


@router.put("", response_model=ProfileSummary)
def update_profile(
    payload: CandidateUpdate,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> ProfileSummary:
    loaded = service.load_candidate(db, candidate.id)
    service.update_candidate(db, loaded, payload)
    return service.to_profile_summary(service.load_candidate(db, candidate.id))


# -------------------------------------------------------------------- skills


@router.get("/skills", response_model=list[CandidateSkillOut])
def list_skills(
    candidate: Candidate = Depends(current_candidate), db: Session = Depends(get_db)
) -> list[CandidateSkillOut]:
    summary = service.to_profile_summary(service.load_candidate(db, candidate.id))
    return summary.skills


@router.post("/skills", response_model=CandidateSkillOut, status_code=status.HTTP_201_CREATED)
def create_skill(
    payload: CandidateSkillCreate,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> CandidateSkillOut:
    loaded = service.load_candidate(db, candidate.id)
    link = service.add_skill(db, loaded, payload)
    db.refresh(link)
    return CandidateSkillOut(
        id=link.id,
        name=link.skill.name,
        category=link.skill.category,
        proficiency=link.proficiency,
        years_experience=link.years_experience,
        notes=link.notes,
    )


@router.delete("/skills/{skill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_skill(
    skill_id: int,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> Response:
    link = _owned(CandidateSkill, db, skill_id, candidate, "Skill")
    service.remove_skill(db, link)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------- experience


@router.get("/experience", response_model=list[ExperienceOut])
def list_experience(
    candidate: Candidate = Depends(current_candidate), db: Session = Depends(get_db)
) -> list[ExperienceOut]:
    summary = service.to_profile_summary(service.load_candidate(db, candidate.id))
    return summary.experience


@router.post("/experience", response_model=ExperienceOut, status_code=status.HTTP_201_CREATED)
def create_experience(
    payload: ExperienceCreate,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> ExperienceOut:
    record = service.add_experience(db, candidate, payload)
    return ExperienceOut.model_validate(record)


@router.put("/experience/{experience_id}", response_model=ExperienceOut)
def update_experience(
    experience_id: int,
    payload: ExperienceUpdate,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> ExperienceOut:
    record = _owned(Experience, db, experience_id, candidate, "Experience")
    service.update_experience(db, record, payload)
    return ExperienceOut.model_validate(record)


@router.delete("/experience/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_experience(
    experience_id: int,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> Response:
    record = _owned(Experience, db, experience_id, candidate, "Experience")
    service.remove_experience(db, record)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ----------------------------------------------------------------- education


@router.get("/education", response_model=list[EducationOut])
def list_education(
    candidate: Candidate = Depends(current_candidate), db: Session = Depends(get_db)
) -> list[EducationOut]:
    summary = service.to_profile_summary(service.load_candidate(db, candidate.id))
    return summary.education


@router.post("/education", response_model=EducationOut, status_code=status.HTTP_201_CREATED)
def create_education(
    payload: EducationCreate,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> EducationOut:
    record = service.add_education(db, candidate, payload)
    return EducationOut.model_validate(record)


@router.put("/education/{education_id}", response_model=EducationOut)
def update_education(
    education_id: int,
    payload: EducationUpdate,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> EducationOut:
    record = _owned(Education, db, education_id, candidate, "Education")
    service.update_education(db, record, payload)
    return EducationOut.model_validate(record)


@router.delete("/education/{education_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_education(
    education_id: int,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> Response:
    record = _owned(Education, db, education_id, candidate, "Education")
    service.remove_education(db, record)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ------------------------------------------------------------------ projects


@router.get("/projects", response_model=list[ProjectOut])
def list_projects(
    candidate: Candidate = Depends(current_candidate), db: Session = Depends(get_db)
) -> list[ProjectOut]:
    summary = service.to_profile_summary(service.load_candidate(db, candidate.id))
    return summary.projects


@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> ProjectOut:
    record = service.add_project(db, candidate, payload)
    return ProjectOut(
        id=record.id,
        name=record.name,
        description=record.description,
        technologies=[t.strip() for t in (record.technologies or "").split(",") if t.strip()],
        url=record.url,
    )


@router.put("/projects/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> ProjectOut:
    record = _owned(Project, db, project_id, candidate, "Project")
    service.update_project(db, record, payload)
    return ProjectOut(
        id=record.id,
        name=record.name,
        description=record.description,
        technologies=[t.strip() for t in (record.technologies or "").split(",") if t.strip()],
        url=record.url,
    )


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    candidate: Candidate = Depends(current_candidate),
    db: Session = Depends(get_db),
) -> Response:
    record = _owned(Project, db, project_id, candidate, "Project")
    service.remove_project(db, record)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


__all__ = ["router"]
