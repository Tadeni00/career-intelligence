"""V3.1 extraction boundary.

An extraction is one of four states, and only one of them may legitimately
produce a job with no requirements::

    SUCCESS          requirements extracted and well formed
    PARTIAL          some requirements extracted; some elements were malformed
                     and recovered or dropped (recorded)
    FAILED           extraction could not produce a usable requirement set
    EMPTY_CONFIRMED  extraction established that the posting states none

The defect this module exists to prevent, observed in V3:

    A malformed element inside one of the four structured ``*_requirements``
    arrays used to invalidate the whole extraction, and a zero-length result was
    persisted as "this job has no requirements". The engine then scored that job
    on neutral defaults and returned a **positive** recommendation -
    APPLY_WITH_TAILORING at 72.0 - for a job the system had never read.

Two rules follow, and they are the whole point:

1. Coercion is symmetric. Malformed elements in the structured arrays are
   recovered or recorded, never silently dropped into an empty set.
2. A failure is a failure. It propagates explicitly and never reaches the
   matching scorer.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

from pydantic import ValidationError

from app.ai.base import AIProvider, AIProviderError
from app.models import ExtractionStatus
from app.schemas import (
    ExtractedJobRequirements,
    ExtractionAttempt,
    ExtractionMeta,
    ExtractionResult,
)

SCHEMA_VERSION = "ExtractedJobRequirements@1"

STRING_ARRAYS = ("required_skills", "preferred_skills", "responsibilities", "issues")
STRUCTURED_ARRAYS = (
    "experience_requirements",
    "education_requirements",
    "location_requirements",
    "other_requirements",
)

# EMPTY_CONFIRMED policy, stated explicitly so it cannot be widened silently:
# a zero-requirement result counts as confirmed-empty only when the posting is
# too short to state any requirement. Absence of extracted requirements is
# otherwise treated as a failure, never as proof the job has none.
EMPTY_CONFIRMED_MAX_SOURCE_CHARS = 40

_ERROR = {
    "PROVIDER_ERROR": "The AI provider could not return usable JSON.",
    "INVALID_JSON": "The provider response was not valid JSON.",
    "SCHEMA_INVALID": "The provider response did not match the extraction schema.",
    "ALL_ELEMENTS_MALFORMED": "Every structured element was malformed and none could be recovered.",
    "NO_REQUIREMENTS_FOUND": "No requirements were extracted from a non-empty posting.",
    "EMPTY_SOURCE": "The posting contained no text to extract from.",
    "UNSUPPORTED_SHAPE": "The provider response was not an object.",
}


class ExtractionNotMatchableError(RuntimeError):
    """Raised when a job's requirement set is unusable for scoring.

    This is the zero-requirement guard. It exists so that a failed extraction can
    never be scored, and therefore can never produce a recommendation.
    """


@dataclass
class CoercionReport:
    """What the coercion did, for diagnostics."""

    recovered: int = 0
    dropped: list[str] = field(default_factory=list)
    raw_counts: dict[str, int] = field(default_factory=dict)


def _as_str_list(value) -> list[str]:
    """Coerce a value into a list of plain strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        name = value.get("name") or value.get("skill") or value.get("technology")
        return [str(name)] if name else []
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            out.extend(_as_str_list(item))
        return out
    return [str(value)]


def _as_float_or_none(value):
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    digits = ""
    for ch in text:
        if ch.isdigit() or ch == ".":
            digits += ch
        elif digits:
            break
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def _coerce_structured_element(value, field_name: str, index: int,
                               report: CoercionReport) -> dict | None:
    """Coerce one structured element. Returns None only if unrecoverable."""
    if isinstance(value, dict):
        name = value.get("name")
        if isinstance(name, (list, dict)):
            name = _as_str_list(name)
            name = name[0] if name else None
        if name is None or not str(name).strip():
            # Recover from the description if the name is missing but the
            # element still carries usable text.
            for alt in ("description", "requirement", "text"):
                candidate = value.get(alt)
                if candidate:
                    name = str(candidate)[:255]
                    report.recovered += 1
                    break
            else:
                report.dropped.append(
                    f"{field_name}[{index}]: object with no name/description")
                return None
        importance = value.get("importance")
        importance = getattr(importance, "value", importance)
        importance = str(importance).upper() if importance else "UNKNOWN"
        if importance not in ("REQUIRED", "PREFERRED", "SOFT_SIGNAL",
                              "INFORMATIONAL", "UNKNOWN"):
            report.recovered += 1
            importance = "UNKNOWN"
        description = value.get("description")
        # V3.3: preserve auditable source evidence and category through
        # coercion. Dropping them here would silently discard the evidence the
        # contract requires for every requirement.
        source_text = value.get("source_text")
        if source_text is not None and not isinstance(source_text, str):
            source_text = _as_str_list(source_text)
            source_text = source_text[0] if source_text else None
        category = value.get("category")
        return {
            "name": str(name)[:255],
            "description": str(description) if description is not None else None,
            "importance": importance,
            "years_required": _as_float_or_none(value.get("years_required")),
            "source_text": source_text.strip()[:500] if source_text else None,
            "category": str(category).upper()[:32] if category else None,
        }

    if isinstance(value, str):
        # The V3 defect: a bare string here used to invalidate the extraction.
        text = value.strip()
        if not text:
            report.dropped.append(f"{field_name}[{index}]: empty string")
            return None
        report.recovered += 1
        return {"name": text[:255], "description": None,
                "importance": "UNKNOWN", "years_required": None,
                "source_text": None, "category": None}

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        report.recovered += 1
        return {"name": str(value)[:255], "description": None,
                "importance": "UNKNOWN", "years_required": None,
                "source_text": None, "category": None}

    report.dropped.append(f"{field_name}[{index}]: unsupported type "
                          f"{type(value).__name__}")
    return None


def coerce_requirements_payload(data) -> tuple[dict, CoercionReport]:
    """Symmetric coercion across every array in the extraction payload."""
    report = CoercionReport()
    if not isinstance(data, dict):
        return {}, report

    out = dict(data)
    for key in STRING_ARRAYS:
        if key in out:
            before = out[key]
            out[key] = _as_str_list(before)
            n_before = len(before) if isinstance(before, (list, tuple, set)) else int(bool(before))
            n_after = len(out[key])
            if n_after < n_before:
                report.recovered += n_before - n_after

    for key in STRUCTURED_ARRAYS:
        if key not in out:
            continue
        raw = out[key]
        report.raw_counts[key] = len(raw) if isinstance(raw, (list, tuple)) else int(bool(raw))
        if raw is None:
            out[key] = []
            continue
        if not isinstance(raw, (list, tuple)):
            raw = [raw]
        coerced = []
        for index, item in enumerate(raw):
            element = _coerce_structured_element(item, key, index, report)
            if element is not None:
                coerced.append(element)
        out[key] = coerced

    for key in STRING_ARRAYS:
        report.raw_counts.setdefault(key, len(out.get(key) or []))
    return out, report


def source_hash(text: str | None) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _meta(status: str, *, error_code: str | None = None, error_detail: str | None = None,
          provider: str = "unknown", model: str = "unknown",
          source: str = "", attempts: list[ExtractionAttempt] | None = None,
          report: CoercionReport | None = None,
          requirement_count: int = 0) -> ExtractionMeta:
    report = report or CoercionReport()
    return ExtractionMeta(
        status=status,
        error_code=error_code,
        error_detail=error_detail or (_ERROR.get(error_code or "") or None),
        provider=provider,
        model=model,
        schema_version=SCHEMA_VERSION,
        source_sha256=source_hash(source),
        source_chars=len(source or ""),
        attempts=attempts or [],
        recovered_elements=report.recovered,
        dropped_elements=list(report.dropped)[:20],
        raw_counts=dict(report.raw_counts),
        requirement_count=requirement_count,
    )


def resolve_status(requirement_count: int, report: CoercionReport,
                   source: str) -> tuple[str, str | None]:
    """Decide SUCCESS / PARTIAL / FAILED / EMPTY_CONFIRMED.

    An empty result is only EMPTY_CONFIRMED when the posting is too short to
    state a requirement. Otherwise it is a failure, because "nothing was
    extracted" is not evidence that "nothing is required".
    """
    raw_structured = sum(
        n for k, n in report.raw_counts.items() if k in STRUCTURED_ARRAYS
    )
    if requirement_count == 0:
        if report.dropped and (raw_structured or report.raw_counts):
            return ExtractionStatus.FAILED.value, "ALL_ELEMENTS_MALFORMED"
        if len((source or "").strip()) < EMPTY_CONFIRMED_MAX_SOURCE_CHARS:
            return ExtractionStatus.EMPTY_CONFIRMED.value, None
        return ExtractionStatus.FAILED.value, "NO_REQUIREMENTS_FOUND"
    if report.dropped:
        return ExtractionStatus.PARTIAL.value, None
    return ExtractionStatus.SUCCESS.value, None


def extract_requirements(
    provider: AIProvider,
    job_description: str,
    *,
    model: str = "unknown",
) -> ExtractionResult:
    """Run one extraction and classify the outcome. Never raises for provider failure."""
    provider_name = getattr(provider, "name", "unknown")
    text = job_description or ""
    attempts: list[ExtractionAttempt] = []

    try:
        extracted = provider.extract_job_requirements(text)
    except AIProviderError as exc:
        attempts.append(ExtractionAttempt(attempt=1, ok=False,
                                         error_code="PROVIDER_ERROR",
                                         error_detail=str(exc)[:400]))
        return ExtractionResult(
            meta=_meta(ExtractionStatus.FAILED.value, error_code="PROVIDER_ERROR",
                       error_detail=str(exc)[:400], provider=provider_name,
                       model=model, source=text, attempts=attempts),
            requirements=ExtractedJobRequirements(),
        )
    attempts.append(ExtractionAttempt(attempt=1, ok=True))

    payload = extracted.model_dump()
    count = (
        len(payload.get("required_skills") or [])
        + len(payload.get("preferred_skills") or [])
        + sum(len(payload.get(k) or []) for k in STRUCTURED_ARRAYS)
    )
    status, error_code = resolve_status(count, CoercionReport(), text)

    return ExtractionResult(
        meta=_meta(status, error_code=error_code, provider=provider_name,
                   model=model, source=text, attempts=attempts,
                   requirement_count=count),
        requirements=extracted,
    )


def classify_raw_payload(
    data,
    *,
    provider: str = "unknown",
    model: str = "unknown",
    source: str = "",
) -> ExtractionResult:
    """Classify a raw provider payload. Used by providers before validation.

    This is the symmetric counterpart of the old coercion: it recovers malformed
    structured elements, records what it could not recover, and refuses to
    present a malformed payload as an empty requirement set.
    """
    if not isinstance(data, dict):
        return ExtractionResult(
            meta=_meta(ExtractionStatus.FAILED.value, error_code="UNSUPPORTED_SHAPE",
                       provider=provider, model=model, source=source,
                       attempts=[ExtractionAttempt(attempt=1, ok=False,
                                                   error_code="UNSUPPORTED_SHAPE")]),
            requirements=ExtractedJobRequirements(),
        )

    coerced, report = coerce_requirements_payload(data)
    try:
        extracted = ExtractedJobRequirements.model_validate(coerced)
    except ValidationError as exc:
        first = exc.errors()[0]
        return ExtractionResult(
            meta=_meta(ExtractionStatus.FAILED.value, error_code="SCHEMA_INVALID",
                       error_detail=f"{first.get('loc')}: {first.get('msg')}"[:300],
                       provider=provider, model=model, source=text_or(source),
                       attempts=[ExtractionAttempt(attempt=1, ok=False,
                                                   error_code="SCHEMA_INVALID")],
                       report=report),
            requirements=ExtractedJobRequirements(),
        )

    payload = coerced
    count = (
        len(payload.get("required_skills") or [])
        + len(payload.get("preferred_skills") or [])
        + sum(len(payload.get(k) or []) for k in STRUCTURED_ARRAYS)
    )
    status, error_code = resolve_status(count, report, source)
    return ExtractionResult(
        meta=_meta(status, error_code=error_code, provider=provider, model=model,
                   source=source, report=report, requirement_count=count,
                   attempts=[ExtractionAttempt(attempt=1, ok=True)]),
        requirements=extracted,
    )


def text_or(value: str) -> str:
    return value or ""


# --------------------------------------------------------------------------- #
# V3.3 deterministic canonicalisation
# --------------------------------------------------------------------------- #

_TYPE_HINT = {
    "experience_requirements": "EXPERIENCE",
    "education_requirements": "EDUCATION",
    "location_requirements": "LOCATION",
    "other_requirements": "OTHER",
}


def canonical_requirements(payload: dict, *, source_document: str = "",
                           validate_evidence: bool = False
                           ) -> tuple[list, list[str]]:
    """Canonicalise a coerced payload into the deterministic requirement set.

    Never collapses materially different requirements and never infers a
    duration. When ``validate_evidence`` is set, each requirement's quote must
    occur in ``source_document``.
    """
    from app.services.requirements import canonicalize

    notes: list[str] = []
    out = []
    for key, type_hint in _TYPE_HINT.items():
        items = payload.get(key) or []
        if not items:
            continue
        canon, item_notes = canonicalize(
            items, type_hint=type_hint,
            source_document=source_document if validate_evidence else "")
        notes.extend(item_notes)
        out.extend(canon)

    # Named technical capabilities are strings, not objects. They are kept as
    # objects so that evidence and importance validation apply uniformly.
    for key, importance in (("required_skills", "REQUIRED"),
                            ("preferred_skills", "PREFERRED")):
        values = payload.get(key) or []
        if not values:
            continue
        canon, item_notes = canonicalize(
            [{"name": v, "description": None, "importance": importance,
              "years_required": None, "source_text": "", "category": "TECHNICAL"}
             for v in values],
            type_hint="SKILL",
            require_evidence=False,
        )
        notes.extend(item_notes)
        out.extend(canon)

    return out, notes


def canonical_identity_set(payload: dict, *, source_document: str = "",
                           validate_evidence: bool = False) -> set[tuple]:
    """Canonical identity set for stability comparison (spec section 19)."""
    canon, _notes = canonical_requirements(
        payload, source_document=source_document,
        validate_evidence=validate_evidence)
    return {req.identity() for req in canon}


# --------------------------------------------------------------------------- #
# zero-requirement guard
# --------------------------------------------------------------------------- #


def assert_matchable(job) -> None:
    """Refuse to score a job whose requirement set is not usable.

    A job may have zero requirements only when extraction explicitly established
    EMPTY_CONFIRMED. Anything else - never extracted, failed, or silently empty -
    is refused, so no failed extraction can reach the scorer.
    """
    status = getattr(job, "extraction_status", None)
    if status == ExtractionStatus.EMPTY_CONFIRMED.value:
        return

    if getattr(job, "requirements", None):
        return

    if status in (ExtractionStatus.FAILED.value, ExtractionStatus.PARTIAL.value):
        raise ExtractionNotMatchableError(
            f"Job {getattr(job, 'id', '?')} has extraction_status={status} "
            f"({getattr(job, 'extraction_error_code', None)}) and no usable "
            "requirements; it cannot be matched."
        )

    raise ExtractionNotMatchableError(
        f"Job {getattr(job, 'id', '?')} has no requirements and no confirmed "
        "extraction state. Run requirement extraction before matching."
    )


__all__ = [
    "EMPTY_CONFIRMED_MAX_SOURCE_CHARS",
    "ExtractionNotMatchableError",
    "assert_matchable",
    "classify_raw_payload",
    "coerce_requirements_payload",
    "extract_requirements",
    "resolve_status",
    "source_hash",
]
