"""Vacancy freshness assessment for discovered jobs.

Task 25 found that posting dates are often missing (9 of 24 sampled
vacancies) and Task 23 established that ``Job.expires_at`` is written but
never consumed. This module gives ``expires_at`` an explicit, documented
meaning and derives a presentation-only freshness status from it:

- ``posted_at`` + 30 days (set at discovery time) is the end of the window
  in which the record is treated as a current opportunity. It is **not**
  employer-confirmed closure and **not** a retention/deletion marker —
  nothing is ever deleted on expiry.
- Comparisons are UTC throughout. Naive datetimes are assumed to be UTC
  (legacy rows store naive ``discovered_at``); invalid values fail
  conservatively to ``unknown``, never to ``current``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

CURRENT = "current"
STALE = "stale"
UNKNOWN = "unknown"

# Labels that must never be produced: only the employer can confirm closure.
_FORBIDDEN_LABELS = ("closed", "active", "open", "accepting applications", "new")


@dataclass(frozen=True)
class Freshness:
    """Presentation-only freshness of a discovery record."""

    status: str
    reason: str


def coerce_aware(value: datetime | None) -> datetime | None:
    """Return an aware UTC datetime, or None for missing/invalid input.

    Naive datetimes are assumed to be UTC rather than server-local time.
    Anything that is not a datetime at all is rejected.
    """
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def assess_freshness(
    posted_at: datetime | None,
    expires_at: datetime | None,
    now: datetime | None = None,
) -> Freshness:
    """Assess freshness without ever inferring employer-confirmed closure.

    - ``current``: a known expiration lies in the future.
    - ``stale``: a known expiration has passed ("Possibly stale" in the UI).
    - ``unknown``: no usable expiration (e.g. no posting date was supplied).
    """
    moment = coerce_aware(now) or datetime.now(timezone.utc)
    expiry = coerce_aware(expires_at)
    posted = coerce_aware(posted_at)
    if expiry is None:
        if posted is not None:
            return Freshness(
                UNKNOWN,
                f"Posted {posted.date().isoformat()}. Expiration is unknown, "
                "so freshness cannot be assessed.",
            )
        return Freshness(
            UNKNOWN,
            "Posting date unavailable, so freshness cannot be assessed.",
        )
    posted_note = (
        f"Posted {posted.date().isoformat()}." if posted is not None else "Posted date unknown."
    )
    if expiry > moment:
        return Freshness(
            CURRENT,
            f"{posted_note} Within the discovery window.",
        )
    return Freshness(
        STALE,
        f"{posted_note} Past the discovery window; the listing may be stale. "
        "Verify at the original vacancy before applying.",
    )


__all__ = [
    "CURRENT",
    "STALE",
    "UNKNOWN",
    "Freshness",
    "assess_freshness",
    "coerce_aware",
]
