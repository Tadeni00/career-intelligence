"""SQLAlchemy models for the Career Intelligence Platform (V1)."""

from __future__ import annotations

import enum
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class CVStatus(enum.StrEnum):
    UPLOADED = "UPLOADED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    READY = "READY"
    FAILED = "FAILED"


class CVProfileStatus(enum.StrEnum):
    """Lifecycle of one independent CV profile.

    A profile is created as soon as a CV is uploaded and carries its own
    extracted and confirmed candidate information from then on. It never shares
    state with another profile of the same candidate.
    """

    AWAITING_EXTRACTION = "AWAITING_EXTRACTION"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    CONFIRMED = "CONFIRMED"
    EXTRACTION_FAILED = "EXTRACTION_FAILED"


class RequirementType(enum.StrEnum):
    SKILL = "SKILL"
    EXPERIENCE = "EXPERIENCE"
    EDUCATION = "EDUCATION"
    LOCATION = "LOCATION"
    OTHER = "OTHER"


class Importance(enum.StrEnum):
    REQUIRED = "REQUIRED"
    PREFERRED = "PREFERRED"
    SOFT_SIGNAL = "SOFT_SIGNAL"
    INFORMATIONAL = "INFORMATIONAL"
    UNKNOWN = "UNKNOWN"


class Recommendation(enum.StrEnum):
    APPLY = "APPLY"
    APPLY_WITH_TAILORING = "APPLY_WITH_TAILORING"
    STRETCH = "STRETCH"
    SKIP = "SKIP"


class ValidationStatus(enum.StrEnum):
    PENDING = "PENDING"
    VALID = "VALID"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    VALIDATION_FAILED = "VALIDATION_FAILED"


class StrategyStatus(enum.StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"


class ExtractionStatus(enum.StrEnum):
    """V3.1 extraction-boundary contract.

    A requirement extraction is one of these four states. Critically, a job's
    requirement set is only ever empty because extraction *established* it, not
    because extraction silently failed.
    """

    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    EMPTY_CONFIRMED = "EMPTY_CONFIRMED"


class EvidenceRelationship(enum.StrEnum):
    """How a requirement relates to confirmed candidate evidence (V2 section 11)."""

    DIRECT = "DIRECT"
    TRANSFERABLE = "TRANSFERABLE"
    PARTIAL = "PARTIAL"
    UNCERTAIN = "UNCERTAIN"


class GapSeverity(enum.StrEnum):
    REQUIRED = "REQUIRED_GAP"
    PREFERRED = "PREFERRED_GAP"
    SOFT_SIGNAL = "SOFT_SIGNAL_GAP"


class ApplicationStatus(enum.StrEnum):
    INTERESTED = "INTERESTED"
    READY_TO_APPLY = "READY_TO_APPLY"
    APPLIED = "APPLIED"
    INTERVIEW = "INTERVIEW"
    OFFER = "OFFER"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class EvidenceSourceType(enum.StrEnum):
    EXPERIENCE = "EXPERIENCE"
    EDUCATION = "EDUCATION"
    PROJECT = "PROJECT"
    SKILL = "SKILL"
    CERTIFICATION = "CERTIFICATION"
    CV = "CV"
    MANUAL = "MANUAL"


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# --------------------------------------------------------------------- candidate


class Candidate(Base, TimestampMixin):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), default="Candidate")
    professional_title: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    location: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    years_of_experience: Mapped[float | None] = mapped_column(Float)
    preferred_roles: Mapped[str | None] = mapped_column(Text)  # comma-separated
    preferred_locations: Mapped[str | None] = mapped_column(Text)
    remote_preference: Mapped[str | None] = mapped_column(String(32))
    minimum_salary: Mapped[float | None] = mapped_column(Float)

    skills: Mapped[list[CandidateSkill]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    experience: Mapped[list[Experience]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="Experience.start_date.desc()",
    )
    education: Mapped[list[Education]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    projects: Mapped[list[Project]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )
    evidence: Mapped[list[CareerEvidence]] = relationship(
        back_populates="candidate", cascade="all, delete-orphan"
    )


class Skill(Base):
    __tablename__ = "skills"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    category: Mapped[str | None] = mapped_column(String(64))

    links: Mapped[list[CandidateSkill]] = relationship(back_populates="skill")


class CandidateSkill(Base):
    __tablename__ = "candidate_skills"
    __table_args__ = (UniqueConstraint("candidate_id", "skill_id", name="uq_candidate_skill"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    skill_id: Mapped[int] = mapped_column(ForeignKey("skills.id", ondelete="CASCADE"), index=True)
    proficiency: Mapped[str | None] = mapped_column(String(64))
    years_experience: Mapped[float | None] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text)

    candidate: Mapped[Candidate] = relationship(back_populates="skills")
    skill: Mapped[Skill] = relationship(back_populates="links")


class Experience(Base):
    __tablename__ = "experience"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    company: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    start_date: Mapped[str | None] = mapped_column(String(64))
    end_date: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)

    candidate: Mapped[Candidate] = relationship(back_populates="experience")


class Education(Base):
    __tablename__ = "education"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    institution: Mapped[str] = mapped_column(String(255))
    degree: Mapped[str | None] = mapped_column(String(128))
    field: Mapped[str | None] = mapped_column(String(255))
    start_date: Mapped[str | None] = mapped_column(String(64))
    end_date: Mapped[str | None] = mapped_column(String(64))
    description: Mapped[str | None] = mapped_column(Text)

    candidate: Mapped[Candidate] = relationship(back_populates="education")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[str | None] = mapped_column(Text)  # comma-separated
    url: Mapped[str | None] = mapped_column(String(1024))

    candidate: Mapped[Candidate] = relationship(back_populates="projects")


class CareerEvidence(Base):
    """Traceable source for a claim used in generated documents."""

    __tablename__ = "career_evidence"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    source_type: Mapped[str] = mapped_column(String(32), default=EvidenceSourceType.MANUAL.value)
    source_id: Mapped[int | None] = mapped_column(Integer)
    claim: Mapped[str] = mapped_column(Text)
    evidence_text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    candidate: Mapped[Candidate] = relationship(back_populates="evidence")


# --------------------------------------------------------------------------- CV


class CVDocument(Base):
    __tablename__ = "cv_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(16))
    storage_path: Mapped[str] = mapped_column(String(1024))
    content_hash: Mapped[str | None] = mapped_column(String(64))
    is_master: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default=CVStatus.UPLOADED.value)
    error_message: Mapped[str | None] = mapped_column(Text)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    extractions: Mapped[list[CVExtraction]] = relationship(
        back_populates="cv", cascade="all, delete-orphan"
    )


class CVExtraction(Base):
    """Structured extraction result. Never applied to the profile automatically."""

    __tablename__ = "cv_extractions"

    id: Mapped[int] = mapped_column(primary_key=True)
    cv_id: Mapped[int] = mapped_column(
        ForeignKey("cv_documents.id", ondelete="CASCADE"), index=True
    )
    raw_text: Mapped[str | None] = mapped_column(Text)
    data: Mapped[str] = mapped_column(Text)  # JSON payload of ExtractedCV
    issues: Mapped[str | None] = mapped_column(Text)  # JSON list of warnings
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    cv: Mapped[CVDocument] = relationship(back_populates="extractions")


class CVProfile(Base, TimestampMixin):
    """One independent CV profile belonging to a candidate.

    A profile is self-contained. It retains its own filename, extracted text,
    unconfirmed extraction and confirmed candidate information, so a candidate
    may hold several profiles without any of them overwriting another.

    The structured candidate information is stored as a JSON payload validated
    by ``app.schemas.CVProfileData`` rather than as normalised child tables.
    This mirrors the existing convention for structured payloads attached to a
    record (``CVExtraction.data``, ``TailoredCV.content_json``), keeps the
    migration additive, and keeps each profile isolated from the shared
    ``Candidate`` rows that matching still reads.

    This model deliberately carries no "selected"/"active" marker. Selection is
    a separate concern and is not implemented yet; until it is, nothing here
    claims a profile is used by matching.
    """

    __tablename__ = "cv_profiles"
    __table_args__ = (UniqueConstraint("cv_id", name="uq_cv_profiles_cv_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    # Provenance only. SET NULL keeps a profile readable if the source upload is
    # ever removed; the profile keeps its own text and data either way.
    cv_id: Mapped[int | None] = mapped_column(
        ForeignKey("cv_documents.id", ondelete="SET NULL")
    )
    label: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(
        String(32), default=CVProfileStatus.AWAITING_EXTRACTION.value
    )
    error_message: Mapped[str | None] = mapped_column(Text)

    # The profile keeps its own copy of the file reference so it can extract its
    # own text without depending on the legacy cv_documents row.
    file_type: Mapped[str] = mapped_column(String(16), default="pdf")
    storage_path: Mapped[str] = mapped_column(String(1024))
    content_hash: Mapped[str | None] = mapped_column(String(64))

    # Unconfirmed extraction, kept separate from what the user later confirms.
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extracted_data: Mapped[str | None] = mapped_column(Text)  # JSON ExtractedCV
    extracted_issues: Mapped[str | None] = mapped_column(Text)  # JSON list[str]

    # Confirmed candidate information for this profile alone.
    confirmed_data: Mapped[str | None] = mapped_column(Text)  # JSON CVProfileData

    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Soft retirement. Archiving keeps every match and document that cites this
    # profile attributable to it, which is why there is no hard-delete path:
    # the FKs from match_results, tailored_cvs and cover_letters all RESTRICT.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    candidate: Mapped[Candidate] = relationship()
    cv: Mapped[CVDocument | None] = relationship()

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


# --------------------------------------------------------------------------- job


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255), index=True)
    company: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    url: Mapped[str | None] = mapped_column(String(2048))
    source: Mapped[str | None] = mapped_column(String(64), default="manual")
    # Provider job identifiers are opaque and long: JSearch ids observed live
    # are ~200 base64 characters, so 128 truncates them. external_id carries
    # the same id plus a provider prefix, hence the same headroom.
    source_id: Mapped[str | None] = mapped_column(String(512))
    external_id: Mapped[str | None] = mapped_column(String(512))
    is_discovered: Mapped[bool] = mapped_column(Boolean, default=False)
    description: Mapped[str | None] = mapped_column(Text)
    employment_type: Mapped[str | None] = mapped_column(String(64))
    remote_status: Mapped[str | None] = mapped_column(String(32))
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_query: Mapped[dict | None] = mapped_column(sa.JSON)
    requirements_extracted: Mapped[bool] = mapped_column(Boolean, default=False)
    # V3.1 extraction boundary: outcome of the last extraction attempt.
    # NULL means "never extracted". A FAILED job is never matchable.
    extraction_status: Mapped[str | None] = mapped_column(String(16))
    extraction_error_code: Mapped[str | None] = mapped_column(String(64))

    requirements: Mapped[list[JobRequirement]] = relationship(
        back_populates="job", cascade="all, delete-orphan", order_by="JobRequirement.id"
    )
    matches: Mapped[list[MatchResult]] = relationship(
        back_populates="job", cascade="all, delete-orphan"
    )


class JobRequirement(Base):
    __tablename__ = "job_requirements"

    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    requirement_type: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    importance: Mapped[str] = mapped_column(String(16), default=Importance.UNKNOWN.value)
    years_required: Mapped[float | None] = mapped_column(Float)

    job: Mapped[Job] = relationship(back_populates="requirements")


# ------------------------------------------------------------------------- match


class MatchResult(Base):
    __tablename__ = "match_results"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)

    technical_score: Mapped[float] = mapped_column(Float, default=0.0)
    experience_score: Mapped[float] = mapped_column(Float, default=0.0)
    education_score: Mapped[float] = mapped_column(Float, default=0.0)
    location_score: Mapped[float] = mapped_column(Float, default=0.0)
    other_score: Mapped[float] = mapped_column(Float, default=0.0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)

    recommendation: Mapped[str] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    matched_items: Mapped[str] = mapped_column(Text, default="[]")
    gap_items: Mapped[str] = mapped_column(Text, default="[]")
    blocker_items: Mapped[str] = mapped_column(Text, default="[]")
    unknown_items: Mapped[str] = mapped_column(Text, default="[]")
    explanation: Mapped[str | None] = mapped_column(Text)

    # Provenance of the candidate evidence this result was calculated from.
    #
    # NULL means "the shared Candidate record" and is reserved for every
    # historical and legacy result: their provenance is unknown and is never
    # back-filled. A non-NULL value means the result was calculated from exactly
    # that CV profile's confirmed data.
    #
    # RESTRICT, not SET NULL or CASCADE. A null cv_profile_id means "calculated
    # from the shared Candidate record", so letting a profile deletion null this
    # column would silently reclassify a profile-specific result as legacy and
    # erase the distinction permanently. RESTRICT refuses the deletion instead,
    # and a profile is retired by archiving it (CVProfile.archived_at), never by
    # hard deletion while dependent history exists.
    #
    # No uniqueness constraint is added: one row per (candidate, job) is
    # precisely what must be relaxed to let two profiles hold separate results.
    cv_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("cv_profiles.id", ondelete="RESTRICT"), index=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job: Mapped[Job] = relationship(back_populates="matches")


# ------------------------------------------------------------- tailored CVs/CL


class TailoredCV(Base):
    __tablename__ = "tailored_cvs"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    source_cv_id: Mapped[int | None] = mapped_column(ForeignKey("cv_documents.id", ondelete="SET NULL"))
    # Which CV profile supplied the evidence this document was generated from.
    # NULL means the shared Candidate record, which is also what every document
    # created before profiles existed carries. RESTRICT keeps that distinction
    # from being erased by deleting a profile.
    cv_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("cv_profiles.id", ondelete="RESTRICT"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(1024))
    summary: Mapped[str | None] = mapped_column(Text)
    analysis: Mapped[str | None] = mapped_column(Text)  # JSON
    changes_summary: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(
        String(32), default=ValidationStatus.PENDING.value
    )
    validation_issues: Mapped[str | None] = mapped_column(Text)  # JSON
    content_json: Mapped[str | None] = mapped_column(Text)  # structured CV content
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job: Mapped[Job] = relationship()


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    # Same provenance contract as TailoredCV: NULL is the shared Candidate
    # record, RESTRICT keeps it that way.
    cv_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("cv_profiles.id", ondelete="RESTRICT"), index=True
    )
    validation_status: Mapped[str] = mapped_column(
        String(32), default=ValidationStatus.PENDING.value
    )
    validation_issues: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    job: Mapped[Job] = relationship()


# ----------------------------------------------------------- application strategy


class ApplicationStrategy(Base, TimestampMixin):
    """Persisted application strategy (V2 section 25).

    The strategy is an *interpretation* of a specific match result over a
    specific evidence state. It is versioned and can be marked STALE when the
    candidate evidence or the job requirements change, so a stale strategy is
    never silently reused for document generation.
    """

    __tablename__ = "application_strategies"

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int | None] = mapped_column(
        ForeignKey("match_results.id", ondelete="SET NULL"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(16), default=StrategyStatus.CURRENT.value)

    decision: Mapped[str] = mapped_column(String(32))
    decision_summary: Mapped[str | None] = mapped_column(Text)

    strengths: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    gaps: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    blockers: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    transferable_evidence: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    evidence_emphasis: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    claim_restrictions: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    actions: Mapped[str] = mapped_column(Text, default="[]")  # JSON
    review_notes: Mapped[str] = mapped_column(Text, default="[]")  # JSON

    # Fingerprint of the evidence + requirement state this strategy was built
    # from. Used to detect staleness without an event-sourcing system.
    evidence_fingerprint: Mapped[str | None] = mapped_column(String(64))

    # Which CV profile's confirmed evidence this strategy interprets.
    #
    # NULL means the shared Candidate record, which is also what every strategy
    # created before profiles existed carries. It is the *identity of the
    # evidence*, not a claim that anything was submitted anywhere.
    #
    # RESTRICT for the same reason as match_results: a null here means "legacy",
    # so a profile deletion must never be able to relabel it. There is
    # deliberately no uniqueness constraint - history is a free-form revision
    # chain, and scoping is enforced in the retrieval helpers, not by the schema.
    cv_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("cv_profiles.id", ondelete="RESTRICT"), index=True
    )

    job: Mapped[Job] = relationship()


# ----------------------------------------------------------------- application


class Application(Base, TimestampMixin):
    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("candidate_id", "job_id", name="uq_candidate_job_app"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("candidates.id", ondelete="CASCADE"), index=True
    )
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), index=True)
    match_id: Mapped[int | None] = mapped_column(ForeignKey("match_results.id", ondelete="SET NULL"))
    tailored_cv_id: Mapped[int | None] = mapped_column(
        ForeignKey("tailored_cvs.id", ondelete="SET NULL")
    )
    cover_letter_id: Mapped[int | None] = mapped_column(
        ForeignKey("cover_letters.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(32), default=ApplicationStatus.INTERESTED.value)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)

    # The CV profile this application is tracked under.
    #
    # An application represents one person's pursuit of one vacancy, not one per
    # profile evaluated, which is why ``uq_candidate_job_app`` is retained: two
    # profiles assessing the same vacancy must not produce two application rows.
    #
    # This records the profile whose evidence trail the application follows. It
    # is NOT a record of submission: clicking Apply on an external site is
    # invisible to this system, and ``status``/``applied_at`` remain the
    # candidate's own manual assertion.
    #
    # NULL means the shared Candidate record, and is what every historical
    # application carries. Once set it is never silently overwritten, and
    # RESTRICT keeps profile archival from erasing it.
    cv_profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("cv_profiles.id", ondelete="RESTRICT"), index=True
    )

    job: Mapped[Job] = relationship()
    tailored_cv: Mapped[TailoredCV | None] = relationship()
    cover_letter: Mapped[CoverLetter | None] = relationship()
    match: Mapped[MatchResult | None] = relationship()


__all__ = [
    "Application",
    "ApplicationStatus",
    "ApplicationStrategy",
    "CVDocument",
    "CVExtraction",
    "CVStatus",
    "Candidate",
    "CandidateSkill",
    "CareerEvidence",
    "CoverLetter",
    "Education",
    "ExtractionStatus",
    "EvidenceRelationship",
    "EvidenceSourceType",
    "Experience",
    "GapSeverity",
    "Importance",
    "Job",
    "JobRequirement",
    "MatchResult",
    "Project",
    "Recommendation",
    "RequirementType",
    "Skill",
    "StrategyStatus",
    "TailoredCV",
    "ValidationStatus",
]
