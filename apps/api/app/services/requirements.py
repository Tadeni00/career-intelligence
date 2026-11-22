"""V3.3 deterministic requirement canonicalisation.

The model enumerates; this layer decides what the requirement *is*. It runs
after extraction and is the only place where duplicates, spelling variants and
unsupportable importance values are resolved.

Pipeline (spec section 9)::

    Raw job text
        -> LLM candidate enumeration
        -> structured requirements
        -> source-evidence validation
        -> normalization
        -> deterministic deduplication
        -> importance validation
        -> canonical requirement set

Design rules that matter:

* Normalization must not collapse distinct concepts. ``Python`` and
  ``Python programming`` stay separate; only spelling, casing, punctuation,
  Unicode and controlled technology aliases fold together.
* Deduplication must not collapse materially different requirements. Two
  requirements with different durations, categories or eligibility semantics
  remain distinct even when their wording is similar.
* ``years_required`` is never inferred. If the posting does not state a
  duration it stays ``None``.
* Importance is validated against the requirement's own source text, so
  ``REQUIRED`` cannot be asserted without mandatory language to support it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.normalization import canonical_tech, normalize_text

REQUIREMENT_CATEGORIES = (
    "TECHNICAL",
    "EXPERIENCE",
    "EDUCATION",
    "WORK_CONDITION",
    "ELIGIBILITY",
    "DOMAIN",
    "SOFT_SIGNAL",
    "INFORMATIONAL",
)

# Unambiguous mandatory-qualification language. A requirement may only be
# REQUIRED when its own source text carries one of these.
_STRONG_MANDATORY_MARKERS = (
    "required", "requirement", "must", "essential", "mandatory", "minimum",
    "at least", "need to", "needs to", "we require", "you must",
    "qualification", "non-negotiable", "authorized", "authorised",
    "eligible", "based in",
)

# Weaker possession language. "You have X" implies X is expected, but the word
# "have" also appears inside "nice to have", so preference is checked first.
_WEAK_MANDATORY_MARKERS = (
    "you have", "you will have", "you has", "you hold", "you possess",
)

_MANDATORY_MARKERS = _STRONG_MANDATORY_MARKERS + _WEAK_MANDATORY_MARKERS

# Preference markers.
_PREFERENCE_MARKERS = (
    "preferred", "preference", "desirable", "nice to have", "nice-to-have",
    "bonus", "advantage", "plus", "ideally", "familiarity", "exposure to",
)

_SOFT_HINTS = (
    "communication", "communicate", "teamwork", "collaborat", "adapt",
    "motivat", "stakeholder", "ownership", "curious", "self-starter",
    "problem solver", "detail-oriented", "detail oriented", "organised",
    "organized", "culture fit",
)

_ELIGIBILITY_HINTS = (
    "work authorization", "work authorisation", "right to work", "visa",
    "sponsorship", "security clearance", "citizen", "residency", "resident",
    "must be based", "must reside", "eligible to work",
)

_WORK_CONDITION_HINTS = (
    "remote", "hybrid", "on-site", "onsite", "on site", "office",
    "willing to travel", "travel", "flexible hours", "shift",
)

_DOMAIN_HINTS = (
    "banking", "finance", "fintech", "insurance", "healthcare", "health care",
    "pharma", "retail", "telecom", "gaming", "public sector", "e-commerce",
    "marketing analytics", "fraud", "underwriting", "credit risk",
)

_EDUCATION_HINTS = (
    "degree", "bachelor", "master", "phd", "doctorate", "university",
    "college", "bsc", "msc", "diploma", "graduat",
)

_EXPERIENCE_HINTS = (
    "years of experience", "year of experience", "years experience",
    "experience in", "experience with", "background in", "years of",
    "previously", "worked with",
)

# Duration extraction is deliberately conservative: only explicit durations.
_DURATION_RE = re.compile(
    r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?)",
    re.IGNORECASE,
)


def _field(item, key, default=None):
    """Read a field from a dict or an object, tolerating either shape."""
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


@dataclass
class CanonicalRequirement:
    """One requirement in canonical form, plus its audit trail."""

    name: str
    category: str
    importance: str
    type: str
    years_required: float | None
    source_text: str
    evidence_ok: bool = True
    adjustments: list[str] = field(default_factory=list)
    merged_sources: int = 1

    def identity(self) -> tuple:
        """Canonical identity used for stability comparison (spec section 19).

        Semantically meaningful fields only. Formatting, ordering and casing
        are already normalised away upstream.
        """
        return (
            normalize_text(self.name),
            self.category,
            self.importance,
            self.type,
            None if self.years_required is None else round(self.years_required, 2),
            _eligibility_class(self.source_text),
            _work_condition_class(self.source_text),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category,
            "importance": self.importance,
            "type": self.type,
            "years_required": self.years_required,
            "source_text": self.source_text[:300],
            "identity": list(self.identity()),
        }


def _eligibility_class(text: str) -> str:
    low = normalize_text(text)
    for hint in _ELIGIBILITY_HINTS:
        if hint in low:
            return "ELIGIBILITY"
    return "NONE"


def _work_condition_class(text: str) -> str:
    low = normalize_text(text)
    for hint in _WORK_CONDITION_HINTS:
        if hint in low:
            return hint.replace(" ", "_").replace("-", "_").upper()
    return "NONE"


def infer_category(name: str, description: str, source_text: str) -> str:
    """Deterministically classify a requirement's category.

    Category is derived from the requirement's own wording and evidence, never
    from the model, so it cannot drift between runs.
    """
    blob = normalize_text(f"{name} {description} {source_text}")
    if _eligibility_class(blob) != "NONE":
        return "ELIGIBILITY"
    if any(h in blob for h in _WORK_CONDITION_HINTS):
        return "WORK_CONDITION"
    if any(h in blob for h in _EDUCATION_HINTS):
        return "EDUCATION"
    if any(h in blob for h in _EXPERIENCE_HINTS) or _DURATION_RE.search(blob):
        return "EXPERIENCE"
    if any(h in blob for h in _SOFT_HINTS):
        return "SOFT_SIGNAL"
    if any(h in blob for h in _DOMAIN_HINTS):
        return "DOMAIN"
    return "TECHNICAL"


def normalize_requirement_name(name: str) -> str:
    """Fold casing, whitespace, punctuation, Unicode, possessives and aliases.

    Deliberately conservative: only controlled technology aliases fold, so
    ``Python`` and ``Python programming`` remain distinct.
    """
    cleaned = normalize_text(name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    canonical = canonical_tech(cleaned)
    # canonical_tech only returns a mapped label when one exists; otherwise it
    # returns the normalised string unchanged.
    return re.sub(r"\s+", " ", (canonical or cleaned)).strip()


def extract_explicit_duration(text: str) -> float | None:
    """Return a duration only when the text states one explicitly."""
    if not text:
        return None
    match = _DURATION_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def validate_importance(importance: str, name: str, source_text: str,
                        description: str) -> tuple[str, list[str]]:
    """Validate importance against the requirement's own evidence.

    ``REQUIRED`` is only permitted when the requirement's source text carries
    mandatory-qualification language. This is deterministic, auditable, and
    prevents a merely prominent technology from being asserted as mandatory.
    """
    adjustments: list[str] = []
    value = (importance or "UNKNOWN").upper()
    if value not in ("REQUIRED", "PREFERRED", "SOFT_SIGNAL", "INFORMATIONAL",
                     "UNKNOWN"):
        adjustments.append(f"unknown importance {value!r} -> UNKNOWN")
        value = "UNKNOWN"

    evidence = normalize_text(f"{source_text} {description}")
    has_preference = any(m in evidence for m in _PREFERENCE_MARKERS)
    has_strong = any(m in evidence for m in _STRONG_MANDATORY_MARKERS)
    has_weak = any(m in evidence for m in _WEAK_MANDATORY_MARKERS)

    # Preference language is unambiguous and is checked first: "nice to have"
    # contains the word "have", which must not read as mandatory.
    if value == "REQUIRED":
        if evidence and not (has_strong or has_weak):
            adjustments.append(
                "REQUIRED downgraded to PREFERRED: no mandatory language in "
                "the requirement's own source text"
            )
            value = "PREFERRED"
        elif evidence and has_preference and not has_strong:
            adjustments.append(
                "REQUIRED downgraded to PREFERRED: explicit preference language "
                "and no unambiguous mandatory language"
            )
            value = "PREFERRED"
    elif value == "PREFERRED":
        if evidence and has_strong and not has_preference:
            adjustments.append(
                "PREFERRED upgraded to REQUIRED: unambiguous mandatory language "
                "present in the requirement's own source text"
            )
            value = "REQUIRED"

    if value in ("UNKNOWN", "INFORMATIONAL"):
        blob = normalize_text(f"{name} {evidence}")
        if any(h in blob for h in _SOFT_HINTS):
            adjustments.append("UNKNOWN -> SOFT_SIGNAL: behavioural expectation")
            value = "SOFT_SIGNAL"
        elif evidence:
            # V3.3: resolve an undecided importance deterministically from the
            # requirement's own evidence instead of letting the model's
            # indecision vary between runs. Mandatory language wins; explicit
            # preference language next; otherwise treat as preference, which is
            # the conservative direction (a requirement is never inflated to
            # mandatory by ambiguity).
            if has_preference and not has_strong:
                adjustments.append(
                    "UNKNOWN -> PREFERRED: preference language present in the "
                    "requirement's own source text"
                )
                value = "PREFERRED"
            elif has_strong or has_weak:
                adjustments.append(
                    "UNKNOWN -> REQUIRED: mandatory language present in the "
                    "requirement's own source text"
                )
                value = "REQUIRED"
            elif has_preference:
                adjustments.append(
                    "UNKNOWN -> PREFERRED: preference language present in the "
                    "requirement's own source text"
                )
                value = "PREFERRED"
            else:
                adjustments.append(
                    "UNKNOWN -> PREFERRED: no mandatory or preference language "
                    "in the requirement's own source text"
                )
                value = "PREFERRED"
    return value, adjustments


def _dedupe_key(req: CanonicalRequirement) -> tuple:
    """Identity for collapsing duplicates.

    Deliberately EXCLUDES ``years_required`` from the collapse key only when the
    two values are absent; a stated duration always keeps requirements distinct.
    """
    name = normalize_requirement_name(req.name)
    return (
        name,
        req.category,
        req.importance,
        req.type,
        req.years_required,
        _eligibility_class(req.source_text),
        _work_condition_class(req.source_text),
    )


def _quote_present(quote: str, document: str) -> bool:
    """True when a quoted fragment appears in the posting text."""
    q = normalize_text(quote)
    d = normalize_text(document)
    if not q or not d:
        return False
    if q in d:
        return True
    # Tolerate whitespace/punctuation drift inside a long quote.
    tokens = [t for t in re.split(r"[^a-z0-9+#]+", q) if t]
    if not tokens:
        return False
    hit = 0
    doc_tokens = re.split(r"[^a-z0-9+#]+", d)
    window = max(4, len(tokens) - 2)
    for start in range(0, max(1, len(doc_tokens) - window + 1)):
        chunk = set(doc_tokens[start:start + window])
        hit = sum(1 for t in tokens if t in chunk)
        if hit / len(tokens) >= 0.9:
            return True
    return False


def canonicalize(requirements, *, type_hint: str = "OTHER",
                 require_evidence: bool = True,
                 source_document: str = "") -> tuple[list[CanonicalRequirement],
                                                     list[str]]:
    """Normalise, validate and deduplicate an extracted requirement list.

    When ``source_document`` is supplied, a requirement's quoted evidence must
    actually occur in the posting; a quote the model invented does not count as
    evidence.

    Returns ``(canonical_requirements, notes)``.
    """
    notes: list[str] = []
    out: list[CanonicalRequirement] = []
    seen: dict[tuple, CanonicalRequirement] = {}

    for item in requirements:
        name = _field(item, "name") or ""
        if not str(name).strip():
            notes.append("dropped: requirement with no name")
            continue

        description = (_field(item, "description") or "")
        source_text = (_field(item, "source_text") or "").strip()

        evidence_ok = True
        if require_evidence and not source_text:
            # No evidence for why this requirement exists: record and keep the
            # requirement, flagged, rather than silently accepting or dropping.
            evidence_ok = False
            notes.append(f"no source evidence supplied for {name!r}")
        elif source_text and source_document and not _quote_present(
            source_text, source_document
        ):
            # The quote does not occur in the posting: the model restated or
            # invented it. Keep the requirement but refuse to treat the quote as
            # evidence, so importance validation cannot lean on invented text.
            evidence_ok = False
            source_text = ""
            notes.append(
                f"source evidence for {name!r} not found in the job text; "
                "importance cannot be justified from invented evidence"
            )

        declared_years = _field(item, "years_required")
        if declared_years is not None:
            try:
                declared_years = float(declared_years)
            except (TypeError, ValueError):
                declared_years = None

        explicit = extract_explicit_duration(
            f"{name} {description} {source_text}")
        years = declared_years if declared_years is not None else explicit
        if declared_years is None and explicit is not None:
            notes.append(f"duration recovered from source text for {name!r}")
        if declared_years is not None and explicit is not None and \
                abs(declared_years - explicit) > 0.01:
            years = explicit
            notes.append(
                f"declared duration {declared_years:g} contradicted by source "
                f"text duration {explicit:g} for {name!r}; source text wins"
            )

        category = _field(item, "category") or ""
        if category.upper() not in REQUIREMENT_CATEGORIES:
            category = infer_category(name, description, source_text)

        importance, adjustments = validate_importance(
            _field(item, "importance", "UNKNOWN"), name, source_text, description)
        importance = getattr(importance, "value", importance)

        candidate = CanonicalRequirement(
            name=normalize_requirement_name(name) or str(name).strip(),
            category=category.upper(),
            importance=importance,
            type=type_hint,
            years_required=years,
            source_text=source_text or description,
            evidence_ok=evidence_ok,
            adjustments=adjustments,
        )

        key = _dedupe_key(candidate)
        if key in seen:
            existing = seen[key]
            existing.merged_sources += 1
            if len(candidate.source_text) > len(existing.source_text):
                existing.source_text = candidate.source_text
            notes.append(f"deduplicated {candidate.name!r} "
                         f"(now {existing.merged_sources} sources)")
            continue

        seen[key] = candidate
        out.append(candidate)

    return out, notes


__all__ = [
    "REQUIREMENT_CATEGORIES",
    "CanonicalRequirement",
    "canonicalize",
    "extract_explicit_duration",
    "infer_category",
    "normalize_requirement_name",
    "validate_importance",
]
