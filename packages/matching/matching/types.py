"""Input/output value objects for the matching engine.

These are plain dataclasses so the package stays free of SQLAlchemy/FastAPI
dependencies and can be tested on its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field

SKILL = "SKILL"
EXPERIENCE = "EXPERIENCE"
EDUCATION = "EDUCATION"
LOCATION = "LOCATION"
OTHER = "OTHER"

REQUIRED = "REQUIRED"
PREFERRED = "PREFERRED"
UNKNOWN_IMPORTANCE = "UNKNOWN"


@dataclass
class Requirement:
    """A single requirement extracted from a job description."""

    id: int | None = None
    type: str = OTHER
    name: str = ""
    description: str = ""
    importance: str = UNKNOWN_IMPORTANCE
    years_required: float | None = None

    def is_hard_requirement(self) -> bool:
        return self.importance == REQUIRED


@dataclass
class JobProfile:
    """Job-side input to the engine."""

    id: int | None = None
    title: str = ""
    company: str = ""
    location: str = ""
    remote_status: str = ""  # REMOTE / HYBRID / ONSITE / "" (unknown)
    employment_type: str = ""
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    requirements: list[Requirement] = field(default_factory=list)


@dataclass
class CandidateSkill:
    id: int | None = None
    name: str = ""
    category: str = ""
    proficiency: str = ""
    years_experience: float | None = None
    notes: str = ""


@dataclass
class CandidateExperience:
    id: int | None = None
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""

    @property
    def is_current(self) -> bool:
        return not self.end_date or self.end_date.strip().lower() in {
            "present",
            "current",
            "now",
            "today",
        }


@dataclass
class CandidateEducation:
    id: int | None = None
    institution: str = ""
    degree: str = ""
    field: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


@dataclass
class CandidateProfile:
    """Candidate-side input to the engine."""

    id: int | None = None
    name: str = ""
    professional_title: str = ""
    location: str = ""
    summary: str = ""
    years_of_experience: float | None = None
    preferred_roles: list[str] = field(default_factory=list)
    preferred_locations: list[str] = field(default_factory=list)
    remote_preference: str = ""  # REMOTE / HYBRID / ONSITE / ANY / ""
    minimum_salary: float | None = None
    skills: list[CandidateSkill] = field(default_factory=list)
    experience: list[CandidateExperience] = field(default_factory=list)
    education: list[CandidateEducation] = field(default_factory=list)


@dataclass
class MatchItem:
    """One explainable line item in a match result."""

    category: str
    name: str
    detail: str = ""
    importance: str = UNKNOWN_IMPORTANCE

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "name": self.name,
            "detail": self.detail,
            "importance": self.importance,
        }


@dataclass
class DimensionScore:
    name: str
    score: float
    items: list[MatchItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class MatchOutcome:
    technical_score: float
    experience_score: float
    education_score: float
    location_score: float
    other_score: float
    overall_score: float
    recommendation: str
    confidence: float
    matched: list[MatchItem] = field(default_factory=list)
    gaps: list[MatchItem] = field(default_factory=list)
    blockers: list[MatchItem] = field(default_factory=list)
    unknowns: list[MatchItem] = field(default_factory=list)
    explanation: str = ""

    def to_dict(self) -> dict:
        return {
            "technical_score": self.technical_score,
            "experience_score": self.experience_score,
            "education_score": self.education_score,
            "location_score": self.location_score,
            "other_score": self.other_score,
            "overall_score": self.overall_score,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "matched_items": [i.to_dict() for i in self.matched],
            "gap_items": [i.to_dict() for i in self.gaps],
            "blocker_items": [i.to_dict() for i in self.blockers],
            "unknown_items": [i.to_dict() for i in self.unknowns],
            "explanation": self.explanation,
        }
