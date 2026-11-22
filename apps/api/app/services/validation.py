"""Evidence-grounded validation for employer-facing generated documents.

Two stages, both mandatory before a document may be finalised:

    claim validation  ->  output sanitisation  ->  final status

Status semantics (spec section 13):
  VALID              automated validation found no violation within its coverage
  REVIEW_REQUIRED    cannot establish sufficient confidence to declare safe
  VALIDATION_FAILED  at least one evidence or safety violation detected

Existing V1 error codes are preserved. New codes are added only for concepts
not already representable.
"""

from __future__ import annotations

import json
import re

from app.models import ValidationStatus
from app.schemas import (
    ProfileSummary,
    TailoredCVContent,
    ValidationIssue,
    ValidationReport,
)
from app.services import sanitize
from app.services.evidence import (
    ACCEPTED_CLASSES,
    ClaimClass,
    ClaimSeverity,
    EvidenceCategory,
    build_index,
    classify_sentence,
)
from app.services.normalization import (
    canonical_tech,
    normalize_text,
    normalize_title,
    tokens,
)

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")

# Boilerplate requirement names that must never act as hard requirements.
_SOFT_SIGNAL_PHRASES = {
    "team player", "self-starter", "self starter", "impact driven",
    "impact-oriented", "impact oriented", "commercially minded",
    "strong communication skills", "detail-oriented", "detail oriented",
    "highly organised", "highly organized", "well-organised", "well-organized",
    "proactive mindset", "willingness to learn", "fast-paced", "dynamic",
    "culture fit", "self motivated", "self-motivated", "go-getter",
    "thinker", "doer", "winner", "passion for", "good attitude",
    "attention to detail", "organisational skills", "interpersonal skills",
    "good communication", "written communication", "time management",
    "problem solver", "hard working", "hardworking", "dedicated",
}


# --------------------------------------------------------------------------- #
# Claim validation
# --------------------------------------------------------------------------- #


def _sentences(text: str) -> list[str]:
    return [s.strip(" -*•\t") for s in _SENT_SPLIT.split(text or "") if s and s.strip()]


def _extra_evidence(profile: ProfileSummary) -> list[str]:
    """Eligibility/other free-text evidence that is confirmed on the profile."""
    out: list[str] = []
    blob = " ".join(filter(None, [profile.summary or ""]))
    if re.search(r"\bauthoris?z?ed to work\b|\bright to work\b|\bwork permit\b", blob, re.I):
        out.append(blob)
    return out


def validate_cover_letter(
    text: str,
    profile: ProfileSummary,
    job_title: str,
    company: str | None,
    *,
    job_description: str = "",
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    if not (text or "").strip():
        issues.append(
            ValidationIssue(severity="error", code="EMPTY",
                            message="The cover letter is empty."))
        return _finalise(issues, sanitized=True)

    idx = build_index(profile, _extra_evidence(profile))
    # Vocabulary from the posting, plus the target role/company. Naming who the
    # candidate is applying to is not a claim about the candidate.
    jd_terms = tokens(job_description or "") if job_description else set()
    jd_terms |= tokens(job_title or "") | tokens(company or "")

    # --- required content checks (kept from V1, now WARNING severity) ----
    if job_title and normalize_text(job_title) not in normalize_text(text):
        issues.append(ValidationIssue(
            severity="warning", code="ROLE_NOT_NAMED",
            message=f"The cover letter does not mention the role '{job_title}'."))
    if company:
        cn = normalize_text(company)
        if cn and cn not in normalize_text(text):
            issues.append(ValidationIssue(
                severity="warning", code="COMPANY_NOT_NAMED",
                message=f"The cover letter does not mention '{company}'."))
        for marker in ("world-class", "industry-leading", "mission-driven",
                       "our culture", "our values", "your innovative",
                       "your commitment to", "your cutting-edge"):
            if marker in text.lower():
                issues.append(ValidationIssue(
                    severity="error", code="INVENTED_COMPANY_KNOWLEDGE",
                    message=("The cover letter asserts company knowledge "
                             f"('{marker}') not present in the job description."),
                    detail=marker))

    # --- claim-by-claim validation ---------------------------------------
    for sentence in _sentences(text):
        claim = classify_sentence(sentence, idx, job_terms=jd_terms)
        if claim.classification in ACCEPTED_CLASSES:
            continue
        issues.append(_issue_for(claim))

    # --- invented employer / title inside prose -------------------------
    known_employers = idx.employers()
    target_tokens = {normalize_text(job_title or ""), normalize_text(company or "")}
    for sentence in _sentences(text):
        low = normalize_text(sentence)
        # If any confirmed employer is named, the sentence is about the
        # candidate's own history and is handled by claim validation.
        #
        # Known employers are canonicalised with normalize_title, which drops
        # punctuation ("Independent AI & Data Science Development" becomes
        # "independent ai data science development"). normalize_text keeps the
        # "&", so comparing one against the other could never match for any
        # employer containing punctuation. The guard then fell through to the
        # "at <Name>" probe, whose pattern stops at "&" and captured only
        # "Independent AI", and a confirmed employer was reported as invented.
        # Canonicalising the sentence the same way makes the two comparable.
        if any(emp and emp in normalize_title(low) for emp in known_employers):
            continue
        # Otherwise an "at <Name>" reference is an unevidenced employer.
        m = re.search(r"\b[Aa]t\s+([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*){0,2})", sentence)
        if not m:
            continue
        name = m.group(1).strip()
        if normalize_title(name) in {normalize_title(t) for t in target_tokens if t}:
            continue
        if any(emp and emp in normalize_title(name) for emp in known_employers):
            continue
        issues.append(ValidationIssue(
            severity="error", code="INVENTED_EMPLOYER",
            message=(f"Letter references employer '{name}' which is not on the "
                     "confirmed profile."),
            detail=name, claim_severity=ClaimSeverity.CRITICAL.value,
            action="Remove or correct the employer reference."))

    return _finalise(issues, sanitized=False, text=text,
                     confirmed_emails=_contact_emails(profile),
                     confirmed_phones=_contact_phones(profile))


def _evidenced_phrases(profile: ProfileSummary) -> set[str]:
    """Multi-word capability phrases evidenced by experience/project prose.

    "Classification modeling" is supported when an experience record says
    "classification ... use cases", even though it is not a literal skill label.
    Without this, perfectly evidenced capabilities were flagged as fabricated.
    """
    phrases: set[str] = set()
    blobs: list[str] = [profile.summary or ""]
    for exp in profile.experience:
        blobs.append(f"{exp.title} {exp.description or ''}")
    for proj in profile.projects:
        blobs.append(f"{proj.name} {proj.description or ''} "
                     f"{' '.join(proj.technologies)}")
    for blob in blobs:
        low = " " + normalize_text(blob) + " "
        for term in (
            "classification", "regression", "modelling", "modeling",
            "prediction", "predictive", "segmentation", "forecasting",
            "reporting", "dashboards", "pipelines", "mentoring", "training",
            "teaching", "documentation", "validation", "cleaning",
            "transformation", "statistics", "visualization", "analysis",
        ):
            if f" {term} " in low or f" {term}s " in low:
                phrases.add(term)
    return phrases


def _phrase_supported(term: str, phrases: set[str]) -> bool:
    """True when a generated capability term is evidenced by profile prose."""
    words = set(normalize_text(term).split())
    words -= {"modeling", "modelling", "generation", "processing", "engineering"}
    if not words:
        return False
    return all(w in phrases or w.rstrip("s") in phrases for w in words)


def validate_tailored_cv(
    content: TailoredCVContent, profile: ProfileSummary, job_description: str = ""
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    idx = build_index(profile, _extra_evidence(profile))

    known_employers = idx.employers()
    known_titles = idx.titles()
    known_institutions = idx.institutions()
    known_degrees = idx.degrees()
    known_tech = idx.technologies()

    # --- employment identity ---------------------------------------------
    for item in content.experience:
        if normalize_title(item.company) not in known_employers:
            issues.append(ValidationIssue(
                severity="error", code="INVENTED_EMPLOYER",
                message=f"Employer '{item.company}' is not on the confirmed profile.",
                detail=item.company))
        if normalize_title(item.title) not in known_titles:
            issues.append(ValidationIssue(
                severity="error", code="INVENTED_POSITION",
                message=f"Position '{item.title}' is not on the confirmed profile.",
                detail=item.title))
        if _years(item.start_date) and _years(item.end_date):
            if _years(item.end_date) < _years(item.start_date):
                issues.append(ValidationIssue(
                    severity="error", code="CONTRADICTORY_DATES",
                    message=(f"'{item.title} @ {item.company}' ends before it starts "
                             f"({item.start_date} - {item.end_date}).")))

    for item in content.education:
        if normalize_title(item.institution) not in known_institutions:
            issues.append(ValidationIssue(
                severity="error", code="INVENTED_EDUCATION",
                message=f"Institution '{item.institution}' is not on the confirmed profile.",
                detail=item.institution))
        if item.degree and normalize_title(item.degree) not in known_degrees:
            issues.append(ValidationIssue(
                severity="error", code="INVENTED_DEGREE",
                message=f"Degree '{item.degree}' is not on the confirmed profile.",
                detail=item.degree))

    # --- technologies / skills (alias-aware, normalise-aware) -----------
    def check(values, where):
        phrases = _evidenced_phrases(profile)
        for value in values or []:
            canon = canonical_tech(value)
            if not canon or canon in known_tech:
                continue
            # Aspirational boilerplate ("Detail-Oriented") is not a technology
            # claim and is not a fabrication.
            if is_soft_signal(value):
                continue
            if _phrase_supported(value, phrases):
                continue
            issues.append(ValidationIssue(
                severity="error", code="UNSUPPORTED_TECHNOLOGY",
                message=(f"'{value}' appears in {where} but is not supported by "
                         "your confirmed profile."),
                detail=value))

    check(content.skills, "the skills section")
    for project in content.projects:
        check(project.technologies, f"project '{project.name}'")

    # --- per-bullet claim validation ------------------------------------
    for item in content.experience:
        source = _find_source(profile, item.company, item.title)
        for bullet in item.bullets:
            for sentence in _sentences(bullet):
                claim = classify_sentence(sentence, idx,
                                             job_terms=tokens(job_description))
                if claim.classification in ACCEPTED_CLASSES:
                    continue
                issues.append(_issue_for(claim, context=(
                    f"'{item.title} @ {item.company}'")))
            if source is not None:
                src_nums = set(re.findall(r"\d+(?:[.,]\d+)?", source or ""))
                for number in re.findall(r"\d+(?:[.,]\d+)?", bullet):
                    if number in {"1", "2", "3", "4", "5", "10"}:
                        continue
                    if number.replace(",", ".") not in {n.replace(",", ".")
                                                         for n in src_nums}:
                        issues.append(ValidationIssue(
                            severity="error", code="UNSUPPORTED_METRIC",
                            message=(f"Bullet introduces number '{number}' not present "
                                     f"in your recorded experience at {item.company}."),
                            detail=bullet[:240]))

    # --- summary ---------------------------------------------------------
    if content.summary:
        for sentence in _sentences(content.summary):
            claim = classify_sentence(sentence, idx,
                                    job_terms=tokens(job_description))
            if claim.classification in ACCEPTED_CLASSES:
                continue
            issues.append(_issue_for(claim, context="the summary"))

    # --- copied job text -------------------------------------------------
    if job_description:
        low_jd = normalize_text(job_description)
        for item in content.experience:
            for bullet in item.bullets:
                n = normalize_text(bullet)
                if len(n) > 60 and n[:60] in low_jd:
                    issues.append(ValidationIssue(
                        severity="error", code="COPIED_JOB_TEXT",
                        message="A bullet copies text from the job description.",
                        detail=bullet[:200]))

    rendered = _render_for_scan(content, profile.name)
    return _finalise(issues, sanitized=False, text=rendered,
                     confirmed_emails=_contact_emails(profile),
                     confirmed_phones=_contact_phones(profile))


def _find_source(profile: ProfileSummary, company: str, title: str):
    for exp in profile.experience:
        if normalize_title(exp.company) == normalize_title(company) and \
           normalize_title(exp.title) == normalize_title(title):
            return exp.description or ""
    return None


def _issue_for(claim, context: str | None = None) -> ValidationIssue:
    """Map a classified claim onto an actionable validation finding."""
    where = f" in {context}" if context else ""
    cls = claim.classification
    action = claim.action or "Review this wording against your profile."
    evidence = ", ".join(claim.matched_evidence[:3]) or "no matching evidence found"

    if cls is ClaimClass.PLAUSIBLE_BUT_UNVERIFIED:
        # Review-worthy ambiguity: not a fabrication call.
        return ValidationIssue(
            severity="warning", code="CLAIM_UNVERIFIED",
            message=(f"Claim{where} is consistent with your background but could "
                     f"not be matched to specific evidence. Reason: {claim.reason}. "
                     f"Evidence: {evidence}."),
            detail=claim.text[:300], action=action,
            claim_severity=ClaimSeverity.LOW.value,
            matched_evidence=claim.matched_evidence[:5])

    if cls is ClaimClass.STRENGTHENED:
        code = "CLAIM_STRENGTHENING"
        if claim.category is EvidenceCategory.ELIGIBILITY:
            code = "UNSUPPORTED_ELIGIBILITY"
        elif claim.category is EvidenceCategory.CLIENT:
            code = "UNSUPPORTED_CLIENT"
        message = (f"Claim{where} strengthens or invents detail beyond evidence. "
                   f"Reason: {claim.reason}. Evidence: {evidence}.")
    elif cls is ClaimClass.UNSUPPORTED:
        if claim.category is EvidenceCategory.ELIGIBILITY:
            code = "UNSUPPORTED_ELIGIBILITY"
        elif claim.category is EvidenceCategory.CONTACT:
            code = "UNSUPPORTED_CONTACT"
        elif claim.category is EvidenceCategory.METRIC:
            code = "UNSUPPORTED_METRIC"
        elif claim.category is EvidenceCategory.CLIENT:
            code = "UNSUPPORTED_CLIENT"
        elif claim.category is EvidenceCategory.ACHIEVEMENT:
            code = "UNSUPPORTED_ACHIEVEMENT"
        elif claim.category is EvidenceCategory.RESPONSIBILITY:
            code = "UNSUPPORTED_RESPONSIBILITY"
        else:
            code = "UNSUPPORTED_CLAIM"
        message = (f"Claim{where} is not supported by confirmed evidence. "
                   f"Reason: {claim.reason}. Evidence: {evidence}.")
    elif cls is ClaimClass.CONTRADICTORY:
        code = "CONTRADICTED_CLAIM"
        message = f"Claim{where} contradicts confirmed evidence: {claim.reason}."
    else:
        code = "UNSUPPORTED_CLAIM"
        message = f"Claim{where} could not be verified: {claim.reason}."

    return ValidationIssue(
        severity="error", code=code, message=message, detail=claim.text[:300],
        action=action, claim_severity=claim.severity.value,
        matched_evidence=claim.matched_evidence[:5])


def _render_for_scan(content: TailoredCVContent, name: str) -> str:
    """Flatten structured CV content into the text a reviewer would see."""
    parts = [name or "", content.summary or ""]
    parts.extend(content.skills)
    for exp in content.experience:
        parts.append(f"{exp.title} {exp.company}")
        parts.extend(exp.bullets)
    for proj in content.projects:
        parts.append(proj.name)
        if proj.description:
            parts.append(proj.description)
        parts.extend(proj.technologies)
    for edu in content.education:
        parts.append(f"{edu.degree} {edu.field} {edu.institution}")
    return "\n".join(p for p in parts if p)


def _contact_emails(profile: ProfileSummary) -> set[str]:
    return {profile.email} if profile.email else set()


def _contact_phones(profile: ProfileSummary) -> set[str]:
    return {profile.phone} if profile.phone else set()


def _years(value: str | None) -> int | None:
    if not value:
        return None
    m = re.search(r"(19|20)\d{2}", value)
    return int(m.group(0)) if m else None


# --------------------------------------------------------------------------- #
# Final gate
# --------------------------------------------------------------------------- #


def _finalise(
    issues: list[ValidationIssue],
    *,
    sanitized: bool,
    text: str = "",
    confirmed_emails: set[str] | None = None,
    confirmed_phones: set[str] | None = None,
) -> ValidationReport:
    if not sanitized and text:
        for finding in sanitize.find_issues(
            text,
            confirmed_emails=confirmed_emails,
            confirmed_phones=confirmed_phones,
        ):
            issues.append(ValidationIssue(
                severity=finding["severity"], code=finding["code"],
                message=finding["message"], detail=finding.get("detail"),
                claim_severity=ClaimSeverity.CRITICAL.value,
                action="Remove the suspicious content before sending this document.",
            ))

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    if errors:
        status = ValidationStatus.VALIDATION_FAILED
    elif _unverifiable(warnings):
        # Cannot establish sufficient confidence: surface for human review
        # rather than silently passing or wrongly failing.
        status = ValidationStatus.REVIEW_REQUIRED
    else:
        status = ValidationStatus.VALID
    return ValidationReport(status=status, issues=issues)


def _unverifiable(warnings: list[ValidationIssue]) -> bool:
    """REVIEW_REQUIRED when any finding means 'cannot establish confidence'."""
    review_codes = {
        "ROLE_NOT_NAMED", "COMPANY_NOT_NAMED", "JOB_TEXT_REUSE",
        "CLAIM_UNVERIFIED", "INVENTED_COMPANY_KNOWLEDGE",
    }
    return any(w.code in review_codes for w in warnings)


# --------------------------------------------------------------------------- #
# Requirement-extraction hygiene
# --------------------------------------------------------------------------- #


def is_soft_signal(name: str, description: str = "") -> bool:
    """True when a requirement is aspirational boilerplate, not a hard gate."""
    blob = normalize_text(f"{name} {description}")
    blob = blob.replace("-", " ")
    for phrase in _SOFT_SIGNAL_PHRASES:
        p = phrase.replace("-", " ")
        if p in blob:
            return True
    return False


def classify_requirement(name: str, description: str, importance: str) -> str:
    """Map an extracted requirement onto REQUIRED / PREFERRED / SOFT_SIGNAL."""
    if is_soft_signal(name, description):
        return "SOFT_SIGNAL"
    return importance


def report_to_json(report: ValidationReport) -> str:
    return json.dumps([i.model_dump() for i in report.issues])


__all__ = [
    "classify_requirement",
    "is_soft_signal",
    "profile_corpus",
    "report_to_json",
    "validate_cover_letter",
    "validate_tailored_cv",
]


def profile_corpus(profile: ProfileSummary) -> str:
    """Full text of confirmed evidence (retained for compatibility)."""
    parts: list[str] = [profile.summary or "", profile.professional_title or "",
                        profile.location or ""]
    parts.extend(s.name for s in profile.skills)
    for e in profile.experience:
        parts.append(f"{e.title} {e.company} {e.description or ''}")
    for e in profile.education:
        parts.append(f"{e.degree or ''} {e.field or ''} {e.institution}")
    for p in profile.projects:
        parts.append(f"{p.name} {p.description or ''} {' '.join(p.technologies)}")
    return "\n".join(parts)
