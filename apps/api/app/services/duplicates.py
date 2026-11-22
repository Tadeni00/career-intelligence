"""Cross-publisher duplicate-review signals for discovered vacancies.

Task 25 found a real near-duplicate: one Bioventures Healthcare Data Analyst
vacancy surfaced through Talent.com and Indeed under different provider
identifiers (description Jaccard 0.889). Provider-identifier deduplication
cannot see that case.

This module only *surfaces* candidates for human review. It never merges,
deletes, rewrites, or blocks anything:

- Same ``external_id`` rows are the same record, not duplicates of each
  other, and are skipped silently.
- ``Likely duplicate`` needs employer agreement, title agreement, *and* at
  least one independent supporting signal (near-identical description,
  identical canonical application URL, or close posting dates).
- ``Possible duplicate`` means employer and title agree but nothing else
  corroborates (or dates conflict).
- Missing information is neutral, except a missing employer or title on the
  target itself, which makes assessment impossible.
- Conflicting locations veto a pair outright: different cities are different
  vacancies even when everything else matches.

Cost control: callers narrow candidates by normalized-employer equality
before any description work happens, descriptions are capped, and everything
is deterministic stdlib code (no embeddings, no new dependencies).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

from app.services.normalization import normalize_text, tokens

LIKELY = "Likely duplicate"
POSSIBLE = "Possible duplicate"
NO_SIGNAL = "No duplicate signal"
UNABLE = "Unable to assess"

_RANK = {NO_SIGNAL: 0, UNABLE: 1, POSSIBLE: 2, LIKELY: 3}

# Corporate suffixes stripped only for the employer-equality gate. This is
# deliberately *not* fuzzy matching: "Acme Ltd" and "Acme Limited" compare
# equal, "Acme" and "Acme Labs" do not.
_EMPLOYER_SUFFIXES = (
    "ltd", "limited", "inc", "incorporated", "llc", "plc", "gmbh", "sarl",
    "pty", "corp", "corporation", "co", "company", "group", "holdings",
)

_TITLE_JACCARD_FLOOR = 0.6
_DESC_STRONG_FLOOR = 0.8
_DESC_CANDIDATE_CHARS = 4000
_DESC_MIN_USABLE = 50
_DATE_CLOSE_DAYS = 14
_DATE_CONFLICT_DAYS = 30


@dataclass(frozen=True)
class DuplicateReview:
    """Review signal for one vacancy; never an identity determination."""

    status: str
    reason: str
    related_job_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class _Candidate:
    id: int | None
    external_id: str | None
    title: str
    company: str
    location: str
    posted_at: datetime | None
    description: str
    url: str


def normalize_employer(name: str | None) -> str:
    """Employer key for the candidate-narrowing gate."""
    words = normalize_text(name).replace(".", " ").split()
    words = [w for w in words if w not in _EMPLOYER_SUFFIXES]
    return " ".join(words)


def canonical_url(url: str | None) -> str:
    """Canonical application URL for equality checks.

    Lowercases the host, drops ``www.``, tracking queries and fragments, and
    trailing slashes. Returns "" when there is nothing usable — an absent URL
    is neutral, never evidence.
    """
    if not url or not isinstance(url, str):
        return ""
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return ""
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/")
    return f"{host}{path}"


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _description_tokens(description: str | None) -> set[str]:
    if not description:
        return set()
    return tokens(description[:_DESC_CANDIDATE_CHARS])


def _as_aware(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        from datetime import timezone

        return value.replace(tzinfo=timezone.utc)
    return value


def _assess_pair(target: _Candidate, other: _Candidate) -> tuple[int, list[str]]:
    """Rank one pair; returns (rank, supporting signal descriptions)."""
    signals: list[str] = []

    employer_a = normalize_employer(target.company)
    employer_b = normalize_employer(other.company)
    if not employer_a or not employer_b or employer_a != employer_b:
        return _RANK[NO_SIGNAL], []

    title_a = tokens(target.title)
    title_b = tokens(other.title)
    if not title_a or not title_b:
        return _RANK[NO_SIGNAL], []
    smaller, larger = sorted((title_a, title_b), key=len)
    title_ok = (len(smaller) >= 2 and smaller <= larger) or _jaccard(title_a, title_b) >= _TITLE_JACCARD_FLOOR
    if not title_ok:
        return _RANK[NO_SIGNAL], []
    signals.append("same employer and matching title")

    location_a = tokens(target.location)
    location_b = tokens(other.location)
    if location_a and location_b:
        smaller_loc, larger_loc = sorted((location_a, location_b), key=len)
        if not (smaller_loc <= larger_loc):
            return _RANK[NO_SIGNAL], []
        signals.append("same location")

    strong = 0
    date_a = _as_aware(target.posted_at)
    date_b = _as_aware(other.posted_at)
    date_conflict = False
    if date_a is not None and date_b is not None:
        gap_days = abs((date_a - date_b).days)
        if gap_days <= _DATE_CLOSE_DAYS:
            strong += 1
            signals.append(f"posted {gap_days} day(s) apart")
        elif gap_days > _DATE_CONFLICT_DAYS:
            date_conflict = True
            signals.append(f"posting dates differ by {gap_days} days")

    url_a = canonical_url(target.url)
    url_b = canonical_url(other.url)
    if url_a and url_b and url_a == url_b:
        strong += 1
        signals.append("identical application URL")

    desc_a = _description_tokens(target.description)
    desc_b = _description_tokens(other.description)
    if len(" ".join(desc_a)) >= _DESC_MIN_USABLE and len(" ".join(desc_b)) >= _DESC_MIN_USABLE:
        similarity = _jaccard(desc_a, desc_b)
        if similarity >= _DESC_STRONG_FLOOR:
            strong += 1
            signals.append(f"descriptions {similarity:.2f} similar")
    # A missing description is neutral: it neither supports nor vetoes.

    if strong >= 1 and not date_conflict:
        return _RANK[LIKELY], signals
    return _RANK[POSSIBLE], signals


def candidate_from_job(job: Any) -> _Candidate:
    """Project the fields the review needs off a Job row (or test double)."""
    return _Candidate(
        id=getattr(job, "id", None),
        external_id=getattr(job, "external_id", None),
        title=getattr(job, "title", None) or "",
        company=getattr(job, "company", None) or "",
        location=getattr(job, "location", None) or "",
        posted_at=getattr(job, "posted_at", None),
        description=getattr(job, "description", None) or "",
        url=getattr(job, "url", None) or "",
    )


def review_candidates(target: _Candidate, others: list[_Candidate]) -> DuplicateReview:
    """Review one vacancy against pre-narrowed candidates (pure, deterministic)."""
    if not tokens(target.title) and not _description_tokens(target.description):
        return DuplicateReview(
            UNABLE,
            "Vacancy has no usable title or description to compare.",
            (),
        )
    best_rank = _RANK[NO_SIGNAL]
    best_ids: list[int] = []
    best_reasons: list[str] = []
    for other in sorted(others, key=lambda c: (c.id is None, c.id)):
        if target.id is not None and other.id == target.id:
            continue
        if (
            target.external_id
            and other.external_id
            and target.external_id == other.external_id
        ):
            # Same record identity, not a duplicate pair.
            continue
        rank, signals = _assess_pair(target, other)
        if rank > best_rank:
            best_rank = rank
            best_ids = [other.id] if other.id is not None else []
            best_reasons = signals
        elif rank == best_rank and rank >= _RANK[POSSIBLE] and other.id is not None:
            best_ids.append(other.id)

    if best_rank == _RANK[LIKELY]:
        return DuplicateReview(
            LIKELY,
            "Strong duplicate evidence: " + "; ".join(best_reasons) + ".",
            tuple(sorted(best_ids)),
        )
    if best_rank == _RANK[POSSIBLE]:
        detail = "; ".join(best_reasons) if best_reasons else "limited corroboration"
        return DuplicateReview(
            POSSIBLE,
            f"Possible duplicate ({detail}); needs human review.",
            tuple(sorted(best_ids)),
        )
    return DuplicateReview(NO_SIGNAL, "No related vacancy found.", ())


def review_job(job: Any, session: Any) -> DuplicateReview:
    """Review one Job row against fellow discovered jobs (read-only).

    Candidate narrowing happens on normalized-employer equality so
    description similarity is only computed for plausible pairs.
    """
    from sqlalchemy import select

    from app.models import Job

    target = candidate_from_job(job)
    if not normalize_employer(target.company):
        return DuplicateReview(
            UNABLE, "Vacancy employer is missing.", ()
        )
    rows = session.execute(select(Job)).scalars().all()
    narrowed = [
        candidate_from_job(row)
        for row in rows
        if row.id != target.id
        and normalize_employer(getattr(row, "company", None)) == normalize_employer(target.company)
    ]
    return review_candidates(target, narrowed)


__all__ = [
    "LIKELY",
    "POSSIBLE",
    "NO_SIGNAL",
    "UNABLE",
    "DuplicateReview",
    "candidate_from_job",
    "canonical_url",
    "normalize_employer",
    "review_candidates",
    "review_job",
]
