"""Small text normalisation helpers shared by the engine."""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[a-z0-9+#.]+")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "we",
    "with",
    "you",
    "your",
    "will",
    "work",
    "working",
    "experience",
    "years",
    "year",
    "strong",
    "ability",
    "able",
    "using",
    "use",
    "used",
    "role",
    "job",
    "team",
    "teams",
    "across",
    "within",
    "plus",
}

_SENIORITY_MARKERS: dict[str, str] = {
    "intern": "intern",
    "internship": "intern",
    "trainee": "intern",
    "graduate": "junior",
    "junior": "junior",
    "jr": "junior",
    "entry": "junior",
    "associate": "associate",
    "mid": "mid",
    "mid-level": "mid",
    "intermediate": "intermediate",
    "senior": "senior",
    "sr": "senior",
    "staff": "staff",
    "principal": "principal",
    "lead": "lead",
    "head": "head",
    "chief": "director",
    "director": "director",
    "vp": "director",
}


def normalise(text: str) -> str:
    """Lowercase and collapse whitespace/punctuation runs."""
    if not text:
        return ""
    lowered = text.lower().replace("\u00a0", " ")
    cleaned = re.sub(r"[^a-z0-9+#.\- ]+", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def tokenise(text: str, *, drop_stopwords: bool = True) -> set[str]:
    tokens = set(_WORD_RE.findall(normalise(text)))
    if drop_stopwords:
        tokens -= _STOPWORDS
    return {t.strip(".") for t in tokens if t.strip(".")}


def token_overlap(a: str, b: str) -> float:
    """Jaccard-ish overlap of two phrases, scaled to 0..1 and tolerant of subsets.

    A phrase fully contained in the other scores 1.0 on the smaller side so that
    "python" matches "python programming".
    """
    ta, tb = tokenise(a), tokenise(b)
    if not ta or not tb:
        return 0.0
    shared = ta & tb
    if not shared:
        return 0.0
    if shared == ta or shared == tb:
        return 1.0
    return len(shared) / min(len(ta), len(tb))


def seniority_of(text: str) -> str | None:
    """Extract a normalised seniority marker from a title, if present."""
    tokens = re.findall(r"[a-z]+", normalise(text))
    for token in tokens:
        marker = _SENIORITY_MARKERS.get(token)
        if marker:
            return marker
    return None


def seniority_rank(marker: str | None, levels: tuple[str, ...]) -> float | None:
    if not marker or marker not in levels:
        return None
    return float(levels.index(marker))


_DEGREE_LEVELS: list[tuple[float, tuple[str, ...]]] = [
    (5.0, ("phd", "doctorate", "doctoral", "dphil", "ph.d")),
    (4.0, ("master", "msc", "ms", "m.sc", "ma", "m.a", "meng", "mba", "m.eng")),
    (3.0, ("bachelor", "bsc", "bs", "b.sc", "ba", "b.a", "beng", "b.eng", "btech")),
    (2.0, ("associate", "diploma", "certificate", "cert", "hnd", "hnds", "gcse", "a-level")),
]


def degree_level(text: str) -> float | None:
    """Map a degree string onto a comparable level (higher is more advanced)."""
    lowered = normalise(text)
    if not lowered:
        return None
    for level, markers in _DEGREE_LEVELS:
        if any(marker in lowered for marker in markers):
            return level
    return None


_DEGREE_ANY_BELOW = (
    "any degree",
    "any relevant degree",
    "degree or equivalent",
    "or equivalent",
    "any qualification",
)


def education_is_open_ended(text: str) -> bool:
    lowered = normalise(text)
    return any(marker in lowered for marker in _DEGREE_ANY_BELOW)


def remote_class(value: str) -> str:
    """Normalise a remote-status string into REMOTE/HYBRID/ONSITE/UNKNOWN."""
    lowered = normalise(value)
    if not lowered:
        return "UNKNOWN"
    if "not remote" in lowered or "no remote" in lowered or "onsite" in lowered.replace(" ", ""):
        if "hybrid" in lowered:
            return "HYBRID"
        return "ONSITE"
    if "hybrid" in lowered:
        return "HYBRID"
    if "remote" in lowered:
        return "REMOTE"
    if "on-site" in lowered or "on site" in lowered:
        return "ONSITE"
    return "UNKNOWN"


def location_tokens(text: str) -> set[str]:
    return tokenise(text, drop_stopwords=False)
