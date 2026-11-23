"""Search-relevance signal for job discovery results.

Task 25 showed a vacancy can score highly against the candidate profile while
being poorly aligned with the requested role (e.g. a Junior Data Analyst at
83/APPLY during a Data Scientist search). This module adds a small,
deterministic, explainable classification of *query-to-title* alignment that is
presented alongside — never merged into — the candidate-fit match result.

Rules are deliberately conservative: anything that cannot be grounded in the
role mapping below is ``Uncertain``, never a confident verdict.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

ALIGNED = "Aligned"
ADJACENT = "Adjacent"
MISMATCH = "Mismatch"
UNCERTAIN = "Uncertain"

# Role families grounded in the benchmark categories (Data Scientist,
# Data Analyst, Machine Learning Engineer). Phrases are matched as whole
# words/phrases against normalized text; abbreviations need explicit entries
# so that e.g. "html" never matches "ml".
_ROLE_FAMILIES: dict[str, tuple[str, ...]] = {
    "data_scientist": (
        "data scientist",
        "data science",
        "statistician",
        "scientifique des donnees",
        "specialiste en science des donnees",
        "statisticien",
        "statisticienne",
    ),
    "data_analyst": (
        "data analyst",
        "business intelligence analyst",
        "bi analyst",
        "business analyst",
        "reporting analyst",
        "analytics analyst",
        "analyste de donnees",
        "analyste des donnees",
        "analyste de la donnee",
        "analyste decisionnel",
        "analyste decisionnelle",
        "analyste business intelligence",
    ),
    "ml_engineer": (
        "machine learning engineer",
        "ml engineer",
        "mlops engineer",
        "ai engineer",
        "deep learning engineer",
        "nlp engineer",
        "artificial intelligence engineer",
        "ingenieur en apprentissage automatique",
        "ingenieure en apprentissage automatique",
        "ingenieur machine learning",
        "ingenieure machine learning",
        "ingenieur intelligence artificielle",
        "ingenieure intelligence artificielle",
    ),
}

_FAMILY_LABELS: dict[str, str] = {
    "data_scientist": "Data Scientist",
    "data_analyst": "Data Analyst",
    "ml_engineer": "Machine Learning Engineer",
}

# Titles that name real but adjacent data-adjacent roles. These are related
# enough that hiding them would lose useful results, but different enough
# that they must never read as aligned with one of the three families.
_ADJACENT_ROLES: tuple[str, ...] = (
    "data engineer",
    "analytics engineer",
    "software engineer",
    "research scientist",
    "bi developer",
    "etl developer",
    "data engineering",
    "ingenieur des donnees",
    "ingenieure des donnees",
    "developpeur logiciel",
    "developpeuse logiciel",
)

# Title signals that the record is not an identifiable vacancy at all.
_NON_VACANCY_MARKERS: tuple[str, ...] = (
    "course",
    "tutorial",
    "bootcamp",
    "training course",
    "training program",
    "certification program",
    "formation",
    "cours",
    "certification",
)


def _normalize(text: str | None) -> str:
    """Lowercase, unescape entities, and collapse punctuation to spaces."""
    import html as _html

    cleaned = _html.unescape(text or "").casefold()
    cleaned = "".join(
        char for char in unicodedata.normalize("NFKD", cleaned)
        if not unicodedata.combining(char)
    )
    cleaned = re.sub(r"[^a-z0-9+#]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _title_variants(raw_title: str | None) -> list[str]:
    """Normalized title plus a comma-reversed variant.

    Postings such as "Scientist, Data" store the family name backwards; trying
    the segments in reverse order recovers them without any fuzzy matching.
    The split happens before normalization because normalization removes
    commas.
    """
    variants = [_normalize(raw_title)]
    segments = [s.strip() for s in (raw_title or "").split(",") if s.strip()]
    if len(segments) >= 2:
        variants.append(_normalize(" ".join(reversed(segments))))
    return variants


def _families_in(text: str) -> list[str]:
    """Role families whose phrases occur in the normalized text, in mapping order."""
    found: list[str] = []
    for family, phrases in _ROLE_FAMILIES.items():
        for phrase in phrases:
            if re.search(r"\b" + re.escape(phrase) + r"\b", text):
                found.append(family)
                break
    return found


@dataclass(frozen=True)
class SearchRelevance:
    """How well a vacancy title matches the requested role."""

    label: str
    reason: str


def classify_search_relevance(query: str | None, title: str | None) -> SearchRelevance:
    """Classify query-to-title alignment without using match scores or skills.

    Only the current search query and the vacancy title are consulted, so the
    same vacancy may classify differently under different queries — and a
    persisted query from an earlier search can never leak into the verdict.
    """
    normalized_query = _normalize(query)
    normalized_title = _normalize(title)

    if not normalized_query:
        return SearchRelevance(UNCERTAIN, "No search query was provided.")
    if not normalized_title:
        return SearchRelevance(UNCERTAIN, "The vacancy title is missing.")

    query_families = _families_in(normalized_query)
    if not query_families:
        return SearchRelevance(
            UNCERTAIN,
            f"Could not determine the role family of search {query.strip()!r}; "
            "only Data Scientist, Data Analyst and Machine Learning Engineer "
            "queries are mapped.",
        )

    title_variants = _title_variants(title)
    if any(
        re.search(r"\b" + re.escape(marker) + r"\b", variant)
        for variant in title_variants
        for marker in _NON_VACANCY_MARKERS
    ):
        return SearchRelevance(
            MISMATCH, "Title looks like training content, not a job vacancy."
        )

    for variant in title_variants:
        if any(family in _families_in(variant) for family in query_families):
            label = _FAMILY_LABELS[query_families[0]]
            return SearchRelevance(
                ALIGNED, f"Title matches the requested {label} role family."
            )

    if any(
        re.search(r"\b" + re.escape(role) + r"\b", normalized_title)
        for role in _ADJACENT_ROLES
    ):
        return SearchRelevance(
            ADJACENT,
            f"Title names a related but different role than {query.strip()!r}.",
        )

    title_families = _families_in(normalized_title)
    if title_families:
        return SearchRelevance(
            MISMATCH,
            f"Title identifies a {_FAMILY_LABELS[title_families[0]]} role, "
            f"requested {_FAMILY_LABELS[query_families[0]]}.",
        )

    return SearchRelevance(
        UNCERTAIN,
        f"Could not determine the role family of {title.strip()!r}.",
    )


__all__ = [
    "ADJACENT",
    "ALIGNED",
    "MISMATCH",
    "UNCERTAIN",
    "SearchRelevance",
    "classify_search_relevance",
]
