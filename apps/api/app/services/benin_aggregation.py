"""Conservative cross-provider duplicate suppression for Benin-local search.

Only collapse records with the same normalized employer, title and city.
Separate IDs are still preserved on every *retained* job so matching and
shortlisting remain source-bound. This deliberately does not attempt fuzzy
matching, which risks hiding unrelated vacancies.
"""
from __future__ import annotations

import re
import unicodedata

from app.services.jsearch import JSearchJob


def _normalized(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


def _city(location: str) -> str:
    # A source may report "Cotonou" or "Cotonou, Bénin".
    # Do not collapse two jobs when their first local place differs.
    return _normalized(location.split(",", 1)[0])


def combine_benin_local_jobs(
    primary: list[JSearchJob], secondary: list[JSearchJob], max_results: int
) -> list[JSearchJob]:
    """Combine, dedupe conservatively, then cap the final unique result set."""
    unique: list[JSearchJob] = []
    seen_ids: set[tuple[str, str]] = set()
    seen_fingerprints: set[tuple[str, str, str]] = set()

    for job in [*primary, *secondary]:
        identity = (job.source, job.provider_job_id)
        title = _normalized(job.title)
        company = _normalized(job.company)
        city = _city(job.location)
        fingerprint = (company, title, city)
        if identity in seen_ids:
            continue
        # Never merge on title only; require all three strong fields.
        if all(fingerprint) and fingerprint in seen_fingerprints:
            continue
        unique.append(job)
        seen_ids.add(identity)
        if all(fingerprint):
            seen_fingerprints.add(fingerprint)
        if len(unique) >= max_results:
            break
    return unique
