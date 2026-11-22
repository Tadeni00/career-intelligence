"""Which CV profile an application is tracked under.

An application represents one person's pursuit of one vacancy, not one per
profile evaluated. This module holds the single rule that decides its profile
provenance, so that ``POST /applications``, ``PUT /applications/{id}`` and the
discovery shortlist endpoint all behave identically instead of each inventing a
slightly different answer.

None always means "the shared Candidate record". Provenance is never invented,
and an ambiguity is reported rather than guessed.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Candidate, CoverLetter, MatchResult, TailoredCV
from app.services import cv_profile as profile_service


def artefact_profiles(
    db: Session,
    match_id: int | None,
    tailored_cv_id: int | None,
    cover_letter_id: int | None,
) -> set[int]:
    """Profile identifiers asserted by the artefacts already linked.

    A null in the set means an artefact that carries no profile provenance (a
    legacy match or document, or no artefact at all). That is weaker evidence,
    not contradictory evidence: it cannot establish a profile but it cannot
    refute one either.
    """
    found: set[int] = set()
    if match_id is not None:
        row = db.get(MatchResult, match_id)
        if row is not None:
            found.add(row.cv_profile_id)
    if tailored_cv_id is not None:
        row = db.get(TailoredCV, tailored_cv_id)
        if row is not None:
            found.add(row.cv_profile_id)
    if cover_letter_id is not None:
        row = db.get(CoverLetter, cover_letter_id)
        if row is not None:
            found.add(row.cv_profile_id)
    return found


def resolve_application_profile(
    db: Session,
    candidate: Candidate,
    requested: int | None,
    existing: int | None,
    match_id: int | None,
    tailored_cv_id: int | None,
    cover_letter_id: int | None,
) -> int | None:
    """Decide which CV profile an application is tracked under.

    ``existing`` is the provenance already recorded, or None when creating.

    Rules, in order:

    1. An explicitly requested profile is validated for ownership, confirmation
       and archival through the shared eligibility service.
    2. The target is the requested profile, otherwise the existing one.
    3. Every artefact that names a profile must agree with the target. A
       disagreement is a conflict; it is never resolved in favour of whichever
       value was supplied.
    4. Existing provenance is never overwritten by a different profile.
    5. With no target and no existing provenance, provenance is inferred only
       when the artefacts name exactly one profile and none of them contradict
       it. Otherwise it stays null.
    """
    asserted = artefact_profiles(db, match_id, tailored_cv_id, cover_letter_id)
    concrete = {p for p in asserted if p is not None}

    if requested is not None:
        profile_service.resolve_confirmed_profile(db, candidate, requested)

    target = requested if requested is not None else existing

    if target is not None and concrete and concrete != {target}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"The linked artefacts belong to CV profile(s) {sorted(concrete)}, "
                f"which conflicts with profile {target}."
            ),
        )

    if existing is not None and requested is not None and requested != existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"This application is already tracked under CV profile {existing} "
                f"and cannot be reassigned to {requested}."
            ),
        )

    if target is None and len(concrete) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The linked artefacts belong to different CV profiles "
                f"{sorted(concrete)}. Name the profile explicitly."
            ),
        )

    if target is None and len(concrete) == 1 and not (asserted - concrete):
        return next(iter(concrete))
    return target


def shortlist_profile_conflict(
    existing_profile_id: int | None, requested_profile_id: int | None
) -> None:
    """Reject a shortlist whose profile disagrees with the recorded one.

    Idempotency is preserved: repeating a shortlist under the *same* profile,
    or repeating a legacy shortlist against a legacy application, is fine. Only
    a genuine disagreement is a conflict, and the recorded provenance is never
    rewritten to accommodate it.
    """
    if existing_profile_id == requested_profile_id:
        return
    if existing_profile_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An application for this vacancy already exists and is tracked "
                "under the shared Candidate record. It cannot be reassigned to "
                f"CV profile {requested_profile_id}; update the existing "
                "application instead."
            ),
        )
    if requested_profile_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "An application for this vacancy already exists under CV profile "
                f"{existing_profile_id}. Supply that profile to shortlist it "
                "again, or update the existing application."
            ),
        )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=(
            f"An application for this vacancy already exists under CV profile "
            f"{existing_profile_id} and cannot be reassigned to "
            f"{requested_profile_id}."
        ),
    )


__all__ = [
    "artefact_profiles",
    "resolve_application_profile",
    "shortlist_profile_conflict",
]
