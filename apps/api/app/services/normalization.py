"""Deterministic text normalisation for evidence comparison.

The V1 validation showed systematic false positives caused by comparing raw
strings: a model writing "Self‑Directed" (U+2011 non-breaking hyphen) against a
profile holding "Self-Directed" (ASCII hyphen) was flagged as an invented
position. This module canonicalises such differences *before* comparison, and
provides a small, explicit technology alias layer.

An alias means "these two labels denote the same known item". It never means
"these are merely similar", so the list stays deliberately small.
"""

from __future__ import annotations

import html as _html
import re
import unicodedata
from html.parser import HTMLParser

# --- canonical forms ---------------------------------------------------------
# U+2010..U+2015 cover hyphen, non-breaking hyphen, figure dash, en/em dash.
_DASHES = dict.fromkeys(
    [
        0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015,
        0x2212, 0xFE58, 0xFE63, 0xFF0D,
    ],
    "-",
)
# Various spaces, including U+00A0, U+2000-200A, U+202F, U+205F, U+3000, U+2007.
_SPACES = dict.fromkeys(
    [0x00A0, 0x1680, 0x2000, 0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006,
     0x2007, 0x2008, 0x2009, 0x200A, 0x202F, 0x205F, 0x3000, 0x180E],
    " ",
)
_QUOTES = {
    0x2018: "'", 0x2019: "'", 0x201A: "'", 0x201B: "'",
    0x201C: '"', 0x201D: '"', 0x201E: '"', 0x201F: '"',
    0x2032: "'", 0x2033: '"',
}
_PUNCT = {
    0x00B7: ".", 0x2022: "*", 0x00A0: " ", 0x2007: " ", 0x2026: "...",
    0x2039: "<", 0x203A: ">",
}

_TRANSLATION = {**_DASHES, **_SPACES, **_QUOTES, **_PUNCT}

# Parenthetical/decorative qualifiers that should not make two otherwise
# identical job titles compare as different: "(NYSC)" vs "- NYSC".
_TITLE_NOISE_RE = re.compile(
    r"\((?:ny sc|ny|intern|internship|remote|contract|full[- ]?time|part[- ]?time)\)",
    re.I,
)
_TITLE_NOISE_DASH_RE = re.compile(
    r"\s[-–—]\s*(?:ny|ny sc|intern|internship|remote|contract|full[- ]?time|part[- ]?time)\s*$",
    re.I,
)

# --- explicit technology/skill aliases --------------------------------------
# Same known item, different label. Kept small and auditable on purpose.
TECH_ALIASES: dict[str, tuple[str, ...]] = {
    "microsoft excel": ("excel", "ms excel", "microsoft office excel"),
    "power bi": ("powerbi", "microsoft power bi", "powerbi desktop"),
    "postgresql": ("postgres", "psql", "pg"),
    "scikit-learn": ("sklearn", "scikit learn"),
    "machine learning": ("ml",),
    "artificial intelligence": ("ai",),
    "natural language processing": ("nlp",),
    "tableau": ("tableau desktop",),
    "javascript": ("js",),
    "typescript": ("ts",),
    "kubernetes": ("k8s",),
    "github": ("gh",),
}

_REVERSE_ALIASES: dict[str, str] = {}
for _canonical, _labels in TECH_ALIASES.items():
    _REVERSE_ALIASES[_canonical] = _canonical
    for _label in _labels:
        _REVERSE_ALIASES[_label] = _canonical

_WORD_RE = re.compile(r"[a-z0-9+#]+")


_NUMBER_WORDS = {
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5",
    "six": "6", "seven": "7", "eight": "8", "nine": "9", "ten": "10",
    "eleven": "11", "twelve": "12",
}

# Spelling variants denote the same fact; canonicalising them prevents a
# British/American difference from being reported as missing evidence.
_SPELLING = {
    "modelling": "modeling", "modelled": "modeled", "labelled": "labeled",
    "analysing": "analyzing", "analysed": "analyzed", "analyse": "analyze",
    "organisation": "organization", "organisations": "organizations",
    "organised": "organized", "organising": "organizing",
    "specialise": "specialize", "specialised": "specialized",
    "specialising": "specializing", "centre": "center", "centres": "centers",
    "programme": "program", "behaviour": "behavior", "favour": "favor",
    "utilise": "utilize", "utilised": "utilized", "normalise": "normalize",
    "summarise": "summarize", "standardise": "standardize",
}


def normalize_text(text: str | None) -> str:
    """Canonicalise a string for comparison (not for display)."""
    if not text:
        return ""
    value = unicodedata.normalize("NFKC", text)
    value = value.translate(_TRANSLATION)
    # Collapse repeated dashes/spaces introduced by substitution.
    value = re.sub(r"-{2,}", "-", value)
    value = re.sub(r"\s{2,}", " ", value)
    value = value.strip().lower()
    # Drop the possessive so "Monzo's" and "Monzo" compare equal. Otherwise
    # every possessive leaks a spurious "s" token into the evidence diff.
    value = re.sub(r"['\u2019]s\b", "", value)
    # Equivalent number words: "six years of experience" == "6 years".
    value = re.sub(r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|"
                   r"eleven|twelve)\b",
                   lambda m: _NUMBER_WORDS[m.group(0)], value)
    value = re.sub(r"\w+",
                   lambda m: _SPELLING.get(m.group(0), m.group(0)), value)
    return value.strip()


def canonical_tech(label: str | None) -> str:
    """Return the canonical technology label for comparison."""
    normalized = normalize_text(label)
    if not normalized:
        return ""
    return _REVERSE_ALIASES.get(normalized, normalized)


def normalize_title(title: str | None) -> str:
    """Normalise a job title, ignoring parenthetical/dashed role qualifiers."""
    value = normalize_text(title)
    value = _TITLE_NOISE_RE.sub(" ", value)
    value = _TITLE_NOISE_DASH_RE.sub(" ", value)
    value = re.sub(r"[^a-z0-9+# ]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def tokens(text: str | None) -> set[str]:
    return {t for t in _WORD_RE.findall(normalize_text(text))}


def sentence_tokens(text: str | None) -> list[str]:
    return _WORD_RE.findall(normalize_text(text))


def same_entity(a: str | None, b: str | None) -> bool:
    """True when two labels denote the same entity after normalisation/aliasing."""
    if not a or not b:
        return False
    if normalize_title(a) == normalize_title(b):
        return True
    return canonical_tech(a) == canonical_tech(b)


def strip_dash_for_compare(value: str) -> str:
    return normalize_text(value).replace("-", "").replace(" ", "")


# --- markup ------------------------------------------------------------------

# Elements whose *content* is not job text. Their contents are dropped rather
# than read, so a stray <script> or inline <style> block can never become a
# requirement.
_HTML_DROP_CONTENT = frozenset(
    {"script", "style", "noscript", "template", "svg", "head", "iframe"}
)

# Opening form of the same set, used to tell "this description really was empty"
# apart from "an element swallowed everything".
_HTML_DROP_START_RE = re.compile(
    r"<\s*/?\s*(?:" + "|".join(sorted(_HTML_DROP_CONTENT)) + r")[\s>/]",
    re.IGNORECASE,
)

# Elements that imply a line break in the visible text. Preserving these keeps
# list items and paragraphs from merging into one another, which is what lets a
# requirement boundary survive.
_HTML_BREAKS = frozenset(
    {
        "p", "div", "br", "li", "ul", "ol", "dl", "dt", "dd", "tr", "table",
        "section", "article", "header", "footer", "nav", "aside", "main",
        "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "hr",
    }
)

_TAGLIKE_RE = re.compile(r"</?[A-Za-z][^<>]*>")

# Job descriptions are frequently captured by tooling that strips every ">".
# Such text contains no well-formed tag at all, so a parser cannot see where a
# tag ends. These two expressions scan for a tag and for the *quoted* attributes
# that may follow it, and _terminate_tags closes the tag where it ends.
#
# The tag name is matched lowercase-only and an attribute must carry "=". Both
# restrictions are what keep prose safe: "<pAfter starting" yields tag "p" plus
# the word "After", and "<pWe'are hiring" yields tag "p" plus "We'are".
_TAG_NAME_RE = re.compile(r"[a-z][a-z0-9-]*")
_ATTR_RE = re.compile(
    r"""[a-zA-Z_:][a-zA-Z0-9_.:-]*\s*=\s*(?:"[^"]*"|'[^']*'|[^\s<>]*)"""
)

# Attribute fragments that can survive in the visible text when the element
# carrying them did not. Restricted to names that cannot plausibly occur in job
# prose, so ordinary wording is never edited.
_RESIDUAL_ATTR_RE = re.compile(
    r"(?<![A-Za-z0-9_-])"
    r"(?:href|src|style|class|alt|title|target|rel|srcset|width|height|align"
    r"|valign|border|colspan|rowspan|colspan|cellpadding|loading|decoding"
    r"|aria-[\w-]+|data-[\w-]+)"
    r"""\s*=\s*(?:"[^"]*"|'[^']*'|[^\s<>]+)""",
    re.IGNORECASE,
)


def _terminate_tags(value: str) -> str:
    """Insert the ">" that closes tags whose terminator was lost in capture.

    Well-formed tags are passed through untouched. A tag is closed at the ">"
    when one exists, and otherwise at the point where its attribute list ends -
    which is the next tag, a line break, the end of the text, or the first token
    that is not a quoted ``name="value"`` pair.
    """
    out: list[str] = []
    i = 0
    n = len(value)
    while i < n:
        lt = value.find("<", i)
        if lt < 0:
            out.append(value[i:])
            break
        out.append(value[i:lt])
        name = _TAG_NAME_RE.match(value, lt + 1)
        if not name:
            # Not a tag ("5 < 10", "a < b"). Keep the character as text.
            out.append("<")
            i = lt + 1
            continue
        end = name.end()
        while True:
            probe = end
            while probe < n and value[probe] in " \t":
                probe += 1
            if probe < n and value[probe] == ">":
                out.append(value[lt : probe + 1])
                i = probe + 1
                break
            if probe >= n or value[probe] in "<\n":
                out.append(value[lt:end] + ">")
                i = end
                break
            attr = _ATTR_RE.match(value, probe)
            if not attr:
                out.append(value[lt:end] + ">")
                i = end
                break
            end = attr.end()
    return "".join(out)


class _VisibleTextParser(HTMLParser):
    """Collect the visible text of possibly-malformed HTML.

    ``HTMLParser`` is forgiving: it never raises on broken markup, so fragments
    such as ``<p<span style="font-weight: 400;">`` are handled the same as well
    formed documents. Character references are converted as they are seen.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):  # noqa: D102 - stdlib hook
        if tag in _HTML_DROP_CONTENT:
            self._skip_depth += 1
        elif tag in _HTML_BREAKS:
            self._chunks.append("\n")

    def handle_startendtag(self, tag, attrs):  # noqa: D102 - stdlib hook
        if tag in _HTML_BREAKS:
            self._chunks.append("\n")

    def handle_endtag(self, tag):  # noqa: D102 - stdlib hook
        if tag in _HTML_DROP_CONTENT:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _HTML_BREAKS:
            self._chunks.append("\n")

    def handle_data(self, data):  # noqa: D102 - stdlib hook
        if self._skip_depth == 0:
            self._chunks.append(data)

    def text(self) -> str:
        return "".join(self._chunks)


def html_to_text(value: str | None) -> str:
    """Convert possibly-marked-up text into readable plain text.

    Job descriptions are routinely pasted straight from a posting page, so the
    stored text can carry inline styles, block tags, list markup and HTML
    entities. Running this before requirement classification means requirement
    names, descriptions and the 120-character name limit measure real content
    instead of markup.

    The text is first handed to :func:`_terminate_tags`, which repairs tags that
    lost their ">" during capture, and is then read by ``HTMLParser`` - a
    standard-library parser that tolerates malformed markup and decodes
    character references. Script, style and similar elements are dropped whole,
    and block-level elements become line breaks so paragraphs and list items
    keep their boundaries.

    Text containing no "<" at all keeps its stored whitespace, with entities
    decoded, so plain-text descriptions behave as before. Input
    that yields nothing usable returns an empty string; callers must treat that
    as "nothing found" rather than inventing a requirement.
    """
    if not value:
        return ""
    if "<" not in value:
        # Plain text: entities are decoded and any stray attribute fragment is
        # removed. Whitespace is left exactly as stored.
        return _RESIDUAL_ATTR_RE.sub(" ", _html.unescape(value))

    repaired = _terminate_tags(value)
    parser = _VisibleTextParser()
    try:
        parser.feed(repaired)
        parser.close()
        extracted = parser.text()
    except Exception:  # pragma: no cover - HTMLParser is forgiving by design
        # Never lose the description because the parser tripped.
        extracted = _TAGLIKE_RE.sub(" ", repaired)

    if not extracted.strip() and not _HTML_DROP_START_RE.search(repaired):
        # The parse yielded nothing although no element was dropped on purpose.
        # Keep the text rather than reporting an empty description.
        extracted = _TAGLIKE_RE.sub(" ", repaired)

    # Residue from markup the parser passed through verbatim.
    extracted = _TAGLIKE_RE.sub(" ", extracted)
    extracted = _RESIDUAL_ATTR_RE.sub(" ", extracted)
    lines = [
        re.sub(r"[^\S\n]+", " ", line).strip() for line in extracted.split("\n")
    ]
    return "\n".join(line for line in lines if line)


__all__ = [
    "TECH_ALIASES",
    "canonical_tech",
    "html_to_text",
    "normalize_text",
    "normalize_title",
    "same_entity",
    "sentence_tokens",
    "strip_dash_for_compare",
    "tokens",
]
