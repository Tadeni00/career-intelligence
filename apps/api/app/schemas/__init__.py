"""Pydantic schemas (API + AI contract)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import (
    ApplicationStatus,
    CVStatus,
    Importance,
    Recommendation,
    RequirementType,
    ValidationStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------- candidate


class SkillOut(ORMModel):
    id: int
    name: str
    category: str | None = None


class CandidateSkillCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    category: str | None = None
    proficiency: str | None = None
    years_experience: float | None = None
    notes: str | None = None


class CandidateSkillOut(ORMModel):
    id: int
    name: str
    category: str | None = None
    proficiency: str | None = None
    years_experience: float | None = None
    notes: str | None = None


class CandidateBase(BaseModel):
    name: str | None = None
    professional_title: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    years_of_experience: float | None = None
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: str | None = None
    minimum_salary: float | None = None


class CandidateUpdate(CandidateBase):
    pass


class CandidateOut(ORMModel):
    id: int
    name: str
    professional_title: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    years_of_experience: float | None = None
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: str | None = None
    minimum_salary: float | None = None
    created_at: datetime
    updated_at: datetime


class ExperienceBase(BaseModel):
    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    is_current: bool = False


class ExperienceCreate(ExperienceBase):
    pass


class ExperienceUpdate(BaseModel):
    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    is_current: bool | None = None


class ExperienceOut(ORMModel):
    id: int
    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    is_current: bool


class EducationBase(BaseModel):
    institution: str
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class EducationCreate(EducationBase):
    pass


class EducationUpdate(BaseModel):
    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class EducationOut(ORMModel):
    id: int
    institution: str
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class ProjectBase(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    technologies: list[str] | None = None
    url: str | None = None


class ProjectOut(ORMModel):
    id: int
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    url: str | None = None


class ProfileSummary(ORMModel):
    """Everything the AI layer needs about the candidate."""

    id: int
    name: str
    professional_title: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    years_of_experience: float | None = None
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: str | None = None
    minimum_salary: float | None = None
    skills: list[CandidateSkillOut] = Field(default_factory=list)
    experience: list[ExperienceOut] = Field(default_factory=list)
    education: list[EducationOut] = Field(default_factory=list)
    projects: list[ProjectOut] = Field(default_factory=list)


# --------------------------------------------------------------------------- CV


class CVOut(ORMModel):
    id: int
    candidate_id: int
    filename: str
    file_type: str
    is_master: bool
    status: str
    error_message: str | None = None
    uploaded_at: datetime
    extracted_at: datetime | None = None
    confirmed_at: datetime | None = None
    text_preview: str | None = None


# --- AI contract for CV extraction ---

ExtractedSummary = str | None


class ExtractedExperience(BaseModel):
    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    is_current: bool = False


class ExtractedEducation(BaseModel):
    institution: str
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class ExtractedProject(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    results: str | None = None


class ExtractedSkill(BaseModel):
    name: str
    category: str | None = None


class ExtractedCertification(BaseModel):
    name: str
    issuer: str | None = None
    date: str | None = None


class ExtractedCV(BaseModel):
    """Structured extraction. Empty sections are allowed — CVs vary."""

    name: str | None = None
    professional_title: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: ExtractedSummary = None
    experience: list[ExtractedExperience] = Field(default_factory=list)
    education: list[ExtractedEducation] = Field(default_factory=list)
    projects: list[ExtractedProject] = Field(default_factory=list)
    skills: list[ExtractedSkill] = Field(default_factory=list)
    certifications: list[ExtractedCertification] = Field(default_factory=list)
    other: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class CVExtractionOut(ORMModel):
    id: int
    cv_id: int
    confirmed: bool
    created_at: datetime
    confirmed_at: datetime | None = None
    data: ExtractedCV
    issues: list[str] = Field(default_factory=list)
    text_length: int = 0


class CVConfirmRequest(BaseModel):
    extraction_id: int | None = None
    overwrite_existing: bool = Field(
        default=False,
        description="When false, existing profile entries are kept and only new ones are added.",
    )


# --------------------------------------------------------------- CV profile (V2)

# The confirmed candidate information a CV profile carries. These are the same
# fields matching and document generation read from a candidate, so a profile can
# stand in for one without changing any downstream contract.
class CVProfileSkill(BaseModel):
    name: str
    category: str | None = None
    proficiency: str | None = None
    years_experience: float | None = None


class CVProfileExperience(BaseModel):
    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class CVProfileEducation(BaseModel):
    institution: str
    degree: str | None = None
    field: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    description: str | None = None


class CVProfileProject(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class CVProfileData(BaseModel):
    """Confirmed candidate information, scoped to exactly one CV profile."""

    name: str | None = None
    professional_title: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    years_of_experience: float | None = None
    preferred_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    remote_preference: str | None = None
    minimum_salary: float | None = None
    skills: list[CVProfileSkill] = Field(default_factory=list)
    experience: list[CVProfileExperience] = Field(default_factory=list)
    education: list[CVProfileEducation] = Field(default_factory=list)
    projects: list[CVProfileProject] = Field(default_factory=list)


class CVProfileCreate(BaseModel):
    """Optional body for creating a profile from an existing upload."""

    label: str | None = Field(default=None, max_length=255)


class CVProfileConfirmRequest(BaseModel):
    """Confirms, and optionally corrects, one profile's extracted information.

    Any field left null is taken from the extraction, so a partial correction is
    never destructive. Nothing here touches the shared Candidate row.
    """

    label: str | None = Field(default=None, max_length=255)
    name: str | None = None
    professional_title: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    years_of_experience: float | None = None
    preferred_roles: list[str] | None = None
    preferred_locations: list[str] | None = None
    remote_preference: str | None = None
    minimum_salary: float | None = None
    skills: list[CVProfileSkill] | None = None
    experience: list[CVProfileExperience] | None = None
    education: list[CVProfileEducation] | None = None
    projects: list[CVProfileProject] | None = None


class CVProfileOut(ORMModel):
    id: int
    candidate_id: int
    cv_id: int | None = None
    label: str
    status: str
    error_message: str | None = None
    extracted: ExtractedCV | None = None
    extracted_issues: list[str] = Field(default_factory=list)
    confirmed: CVProfileData | None = None
    text_length: int = 0
    archived_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    extracted_at: datetime | None = None
    confirmed_at: datetime | None = None


# --------------------------------------------------------------------------- job


class JobRequirementIn(BaseModel):
    requirement_type: RequirementType = RequirementType.OTHER
    name: str
    description: str | None = None
    importance: Importance = Importance.UNKNOWN
    years_required: float | None = None


class JobRequirementOut(ORMModel):
    id: int
    requirement_type: str
    name: str
    description: str | None = None
    importance: str
    years_required: float | None = None


class JobCreate(BaseModel):
    title: str
    company: str | None = None
    location: str | None = None
    url: str | None = None
    source: str | None = "manual"
    source_id: str | None = None
    external_id: str | None = None
    is_discovered: bool = False
    description: str | None = None
    employment_type: str | None = None
    remote_status: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    posted_at: datetime | None = None
    expires_at: datetime | None = None
    search_query: dict | None = None
    requirements: list[JobRequirementIn] | None = None


class JobUpdate(BaseModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    url: str | None = None
    source: str | None = None
    description: str | None = None
    employment_type: str | None = None
    remote_status: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None


class JobSummaryOut(ORMModel):
    id: int
    title: str
    company: str | None = None
    location: str | None = None
    remote_status: str | None = None
    employment_type: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    created_at: datetime
    requirements_extracted: bool = False
    # V3.2: extraction state must be visible so PARTIAL cannot masquerade as
    # SUCCESS. requires_review is True whenever the requirement set is not
    # fully trustworthy.
    extraction_status: str | None = None
    extraction_error_code: str | None = None
    requires_review: bool = False
    latest_match: MatchSummary | None = None


class JobOut(ORMModel):
    id: int
    title: str
    company: str | None = None
    location: str | None = None
    url: str | None = None
    source: str | None = None
    source_id: str | None = None
    external_id: str | None = None
    is_discovered: bool = False
    description: str | None = None
    employment_type: str | None = None
    remote_status: str | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    posted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    requirements_extracted: bool = False
    # V3.2: extraction state surfaced so a PARTIAL extraction is identifiable.
    extraction_status: str | None = None
    extraction_error_code: str | None = None
    requires_review: bool = False
    requirements: list[JobRequirementOut] = Field(default_factory=list)


# ------------------------------------------------------------------------- match


class MatchItemOut(BaseModel):
    category: str
    name: str
    detail: str = ""
    importance: str = "UNKNOWN"


class MatchSummary(ORMModel):
    id: int
    job_id: int
    overall_score: float
    recommendation: str
    confidence: float
    created_at: datetime


class MatchOut(ORMModel):
    id: int
    candidate_id: int
    job_id: int
    technical_score: float
    experience_score: float
    education_score: float
    location_score: float
    other_score: float
    overall_score: float
    recommendation: str
    confidence: float
    matched_items: list[MatchItemOut] = Field(default_factory=list)
    gap_items: list[MatchItemOut] = Field(default_factory=list)
    blocker_items: list[MatchItemOut] = Field(default_factory=list)
    unknown_items: list[MatchItemOut] = Field(default_factory=list)
    explanation: str | None = None
    # Which CV profile produced this result. NULL means the shared Candidate
    # record, which is also what every historical result carries.
    cv_profile_id: int | None = None
    created_at: datetime
    job: JobSummaryOut | None = None


class JobMatchRequest(BaseModel):
    """Optional body for an explicit job match.

    Omitting ``cv_profile_id`` keeps the legacy behaviour exactly: match the
    shared Candidate record. Supplying it matches that confirmed CV profile and
    nothing else.
    """

    cv_profile_id: int | None = Field(
        default=None,
        description="Confirmed CV profile to match against. Omit for legacy Candidate matching.",
    )


# ------------------------------------------------------- application strategy (V2)


class StrengthOut(BaseModel):
    """A job-specific strength with internal evidence provenance."""

    requirement_id: int | None = None
    requirement_name: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    statement: str = ""
    strength: str = "STRONG"  # STRONG / MODERATE


class StrategyGapOut(BaseModel):
    """A requirement not established in the candidate's evidence."""

    requirement_id: int | None = None
    requirement_name: str = ""
    importance: str = "UNKNOWN"
    severity: str = "PREFERRED_GAP"  # REQUIRED_GAP / PREFERRED_GAP / SOFT_SIGNAL_GAP
    statement: str = ""


class StrategyBlockerOut(BaseModel):
    requirement_id: int | None = None
    requirement_name: str = ""
    statement: str = ""
    severity: str = "CRITICAL"


class TransferableEvidenceOut(BaseModel):
    """Confirmed evidence that may legitimately support a requirement."""

    requirement_id: int | None = None
    requirement_name: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    relationship: str = "UNCERTAIN"  # DIRECT / TRANSFERABLE / PARTIAL / UNCERTAIN
    confidence: float = 0.0
    statement: str = ""


class EvidenceEmphasisOut(BaseModel):
    evidence_ids: list[str] = Field(default_factory=list)
    statement: str = ""
    priority: int = 1


class ClaimRestrictionOut(BaseModel):
    """Something the generated documents must not assert."""

    requirement_id: int | None = None
    subject: str = ""
    statement: str = ""
    reason: str = ""


class StrategyActionOut(BaseModel):
    priority: int = 1
    action: str = ""
    rationale: str = ""


class StrategyReviewNoteOut(BaseModel):
    severity: str = "INFORMATIONAL"
    statement: str = ""


class ApplicationStrategy(BaseModel):
    """The V2 decision interpretation layer."""

    decision: str
    decision_summary: str = ""
    strengths: list[StrengthOut] = Field(default_factory=list)
    gaps: list[StrategyGapOut] = Field(default_factory=list)
    blockers: list[StrategyBlockerOut] = Field(default_factory=list)
    transferable_evidence: list[TransferableEvidenceOut] = Field(default_factory=list)
    evidence_emphasis: list[EvidenceEmphasisOut] = Field(default_factory=list)
    claim_restrictions: list[ClaimRestrictionOut] = Field(default_factory=list)
    actions: list[StrategyActionOut] = Field(default_factory=list)
    review_notes: list[StrategyReviewNoteOut] = Field(default_factory=list)


class StrategyOut(ApplicationStrategy):
    # CV profile whose evidence this strategy interprets. NULL is the shared
    # Candidate record and is what every pre-profile strategy carries.
    id: int
    candidate_id: int
    job_id: int
    match_id: int | None = None
    cv_profile_id: int | None = None
    version: int = 1
    status: str = "CURRENT"
    evidence_fingerprint: str | None = None
    created_at: datetime
    updated_at: datetime


class StrategyContext(BaseModel):
    """Structured, fully deterministic input for the narrative model (section 18).

    The model is told what to explain, never asked to judge fit.
    """

    decision: str
    overall_score: float
    matched_items: list[MatchItemOut] = Field(default_factory=list)
    gap_items: list[MatchItemOut] = Field(default_factory=list)
    blocker_items: list[MatchItemOut] = Field(default_factory=list)
    strengths: list[StrengthOut] = Field(default_factory=list)
    gaps: list[StrategyGapOut] = Field(default_factory=list)
    blockers: list[StrategyBlockerOut] = Field(default_factory=list)
    transferable_evidence: list[TransferableEvidenceOut] = Field(default_factory=list)
    claim_restrictions: list[ClaimRestrictionOut] = Field(default_factory=list)


class StrategyNarrative(BaseModel):
    """The only field the model is permitted to author."""

    decision_summary: str = ""


# ------------------------------------------------------------- tailored CV/CL


class CVAnalysis(BaseModel):
    relevant_experience: list[str] = Field(default_factory=list)
    relevant_skills: list[str] = Field(default_factory=list)
    relevant_projects: list[str] = Field(default_factory=list)
    evidence_to_emphasize: list[str] = Field(default_factory=list)
    content_to_de_emphasize: list[str] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    potential_problems: list[str] = Field(default_factory=list)
    recommended_changes: list[str] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    detail: str | None = None
    # --- V1.2 reviewability (spec sections 12-13) -------------------------
    claim_severity: str = "INFORMATIONAL"
    action: str = ""
    matched_evidence: list[str] = Field(default_factory=list)


class TailoredCVOut(ORMModel):
    id: int
    candidate_id: int
    job_id: int
    source_cv_id: int | None = None
    # CV profile that supplied the evidence. NULL means the shared Candidate
    # record, which is also what every pre-profile document carries.
    cv_profile_id: int | None = None
    version: int
    filename: str
    storage_path: str
    summary: str | None = None
    analysis: CVAnalysis | None = None
    changes_summary: list[str] = Field(default_factory=list)
    validation_status: str
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    created_at: datetime


class CoverLetterOut(ORMModel):
    id: int
    candidate_id: int
    job_id: int
    content: str
    cv_profile_id: int | None = None
    validation_status: str
    validation_issues: list[ValidationIssue] = Field(default_factory=list)
    created_at: datetime


class DocumentProfileRequest(BaseModel):
    """Optional body selecting the CV profile a document is generated from.

    Omitting ``cv_profile_id`` is the unchanged legacy behaviour: generate from
    the shared Candidate record and record a null profile identifier.
    """

    cv_profile_id: int | None = Field(
        default=None,
        description="Confirmed CV profile to generate from. Omit for legacy Candidate generation.",
    )


# ----------------------------------------------------------------- application


class ApplicationCreate(BaseModel):
    job_id: int
    match_id: int | None = None
    tailored_cv_id: int | None = None
    cover_letter_id: int | None = None
    status: ApplicationStatus = ApplicationStatus.INTERESTED
    notes: str | None = None
    # The CV profile this application is tracked under. Optional: when omitted,
    # provenance is inferred from the linked artefacts only if they agree
    # unambiguously, and otherwise stays null.
    #
    # This records the evidence trail the application follows. It is not a claim
    # that an application was submitted anywhere.
    cv_profile_id: int | None = None


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    tailored_cv_id: int | None = None
    cover_letter_id: int | None = None
    match_id: int | None = None
    notes: str | None = None
    applied_at: datetime | None = None
    # May only be supplied while the application has no profile yet, and must
    # agree with any artefact supplied in the same request.
    cv_profile_id: int | None = None


class ApplicationOut(ORMModel):
    id: int
    candidate_id: int
    job_id: int
    match_id: int | None = None
    tailored_cv_id: int | None = None
    cover_letter_id: int | None = None
    cv_profile_id: int | None = None
    status: str
    applied_at: datetime | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    job: JobSummaryOut | None = None


# ------------------------------------------------------------------ dashboard


class DashboardStats(BaseModel):
    jobs: int
    strong_matches: int
    apply: int
    apply_with_tailoring: int
    stretch: int
    skip: int
    applications: int
    interviews: int
    offers: int


class DashboardEntry(BaseModel):
    job_id: int
    title: str
    company: str | None = None
    location: str | None = None
    overall_score: float
    recommendation: str
    match_id: int | None = None
    application_status: str | None = None


class DashboardOut(BaseModel):
    stats: DashboardStats
    opportunities: list[DashboardEntry] = Field(default_factory=list)
    recent_applications: list[ApplicationOut] = Field(default_factory=list)
    profile_complete: bool = False
    warnings: list[str] = Field(default_factory=list)


# -------------------------------------------------------------- AI job extract


class ExtractedJobRequirements(BaseModel):
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    experience_requirements: list[ExtractedRequirement] = Field(default_factory=list)
    education_requirements: list[ExtractedRequirement] = Field(default_factory=list)
    location_requirements: list[ExtractedRequirement] = Field(default_factory=list)
    other_requirements: list[ExtractedRequirement] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)


class ExtractedRequirement(BaseModel):
    name: str
    description: str | None = None
    importance: Importance = Importance.UNKNOWN
    years_required: float | None = None
    # V3.3: auditable source evidence. Every accepted requirement must be
    # traceable to text in the job posting; this answers "why does this
    # requirement exist?".
    source_text: str | None = None
    # V3.3: contract category, distinct from importance. Discovery decides
    # whether something is a candidate requirement at all; classification only
    # decides how binding it is.
    category: str | None = None


# --------------------------------------------- extraction boundary contract (V3.1)


class ExtractionAttempt(BaseModel):
    """One provider call attempt, preserved for diagnostics."""

    attempt: int = 1
    ok: bool = False
    error_code: str | None = None
    error_detail: str | None = None


class ExtractionMeta(BaseModel):
    """Everything needed to diagnose an extraction outcome later."""

    status: str = "FAILED"
    error_code: str | None = None
    error_detail: str | None = None
    provider: str = "unknown"
    model: str = "unknown"
    schema_version: str = "ExtractedJobRequirements@1"
    source_sha256: str = ""
    source_chars: int = 0
    attempts: list[ExtractionAttempt] = Field(default_factory=list)
    # Elements the coercion recovered, and elements it could not recover.
    recovered_elements: int = 0
    dropped_elements: list[str] = Field(default_factory=list)
    raw_counts: dict[str, int] = Field(default_factory=dict)
    requirement_count: int = 0


class ExtractionResult(BaseModel):
    """The extraction outcome plus its diagnostics.

    ``requirements`` may only be empty when ``meta.status`` is EMPTY_CONFIRMED.
    """

    meta: ExtractionMeta
    requirements: ExtractedJobRequirements = Field(
        default_factory=ExtractedJobRequirements
    )

    @property
    def usable(self) -> bool:
        return self.meta.status in ("SUCCESS", "PARTIAL", "EMPTY_CONFIRMED")


# ------------------------------------------------------ tailored CV generation


class TailoredCVContent(BaseModel):
    """Structured, evidence-bounded content for a tailored CV."""

    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[TailoredExperience] = Field(default_factory=list)
    education: list[TailoredEducation] = Field(default_factory=list)
    projects: list[TailoredProject] = Field(default_factory=list)
    changes_summary: list[str] = Field(default_factory=list)


class TailoredExperience(BaseModel):
    company: str
    title: str
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = Field(default_factory=list)


class TailoredEducation(BaseModel):
    institution: str
    degree: str | None = None
    field: str | None = None
    end_date: str | None = None


class TailoredProject(BaseModel):
    name: str
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)


class ValidationReport(BaseModel):
    status: ValidationStatus = ValidationStatus.PENDING
    issues: list[ValidationIssue] = Field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(i.severity == "error" for i in self.issues)


# ------------------------------------------------------------------ utilities


class HealthOut(BaseModel):
    status: str
    environment: str
    ai_provider: str
    database: str
    version: str = "0.1.0"


class MessageOut(BaseModel):
    message: str
    detail: dict[str, Any] | None = None


JobSummaryOut.model_rebuild()

__all__ = [name for name in dir() if not name.startswith("_")] + [
    "CVStatus",
    "Importance",
    "Recommendation",
]
