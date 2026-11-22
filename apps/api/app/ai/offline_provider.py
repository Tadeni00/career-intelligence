"""Deterministic heuristic provider.

Used for local development, demos and tests so the full workflow runs without an
API key. It performs regex/section parsing rather than language generation, and
is deliberately conservative: it extracts what is present and never invents.
"""

from __future__ import annotations

import re

from app.ai.base import AIProvider
from app.models import Importance
from app.schemas import (
    CVAnalysis,
    ExtractedCertification,
    ExtractedCV,
    ExtractedEducation,
    ExtractedExperience,
    ExtractedJobRequirements,
    ExtractedProject,
    ExtractedRequirement,
    ExtractedSkill,
    ProfileSummary,
    StrategyContext,
    StrategyNarrative,
    TailoredCVContent,
    TailoredEducation,
    TailoredExperience,
    TailoredProject,
)
from app.services.evidence import GENERIC_TOKENS
from app.services.normalization import html_to_text

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
_YEARS_RE = re.compile(r"\b(\d{1,2})\+?\s*(?:-\s*\d{1,2})?\s*(?:years?|yrs?)", re.I)
_RANGE_RE = re.compile(
    r"((?:19|20)\d{2})\s*(?:-|–|—|to|until)\s*((?:19|20)\d{2}|present|current|now)",
    re.I,
)

_SECTION_HEADINGS: dict[str, tuple[str, ...]] = {
    "summary": ("summary", "profile", "objective", "about me", "personal statement"),
    "experience": ("experience", "employment", "work history", "career history", "professional experience"),
    "education": ("education", "academic", "qualifications", "academic background"),
    "skills": ("skills", "technical skills", "competencies", "technologies", "expertise"),
    "projects": ("projects", "personal projects", "selected projects", "portfolio"),
    "certifications": ("certifications", "certificates", "licenses", "licences", "accreditations"),
}

# Job-description section headings that indicate a requirements list.
# When a sentence appears under one of these headings, it is treated as an
# implicit requirement even without explicit Required/Preferred markers.
_JOB_REQUIREMENT_HEADINGS: frozenset[str] = frozenset(
    {
        "requirements",
        "requirement",
        "qualifications",
        "qualification",
        "what you need",
        "what we need",
        "skills required",
        "skills and qualifications",
        "must have",
        "must-have",
        "essential criteria",
        "desired skills",
        "desired qualifications",
    }
)

# Headings that indicate non-requirement lists (benefits, marketing, etc.)
_JOB_NON_REQUIREMENT_HEADINGS: frozenset[str] = frozenset(
    {
        "benefits",
        "perks",
        "what we offer",
        "what you get",
        "we offer",
        "compensation",
        "about us",
        "about the company",
        "company overview",
        "our mission",
        "our values",
        "culture",
        "equal opportunity",
        "eeo",
        "diversity",
        "inclusion",
        "application process",
        "how to apply",
        "apply now",
        "privacy",
        "legal",
        "disclaimer",
    }
)

_SKILL_VOCAB: dict[str, str] = {
    "python": "Programming",
    "sql": "Data",
    "postgres": "Data",
    "postgresql": "Data",
    "mysql": "Data",
    "spark": "Data",
    "pandas": "Data",
    "numpy": "Data",
    "machine learning": "Machine Learning",
    "deep learning": "Machine Learning",
    "nlp": "Machine Learning",
    "natural language processing": "Machine Learning",
    "computer vision": "Machine Learning",
    "mlops": "Machine Learning Engineering",
    "statistics": "Statistics",
    "statistical": "Statistics",
    "data science": "Data Science",
    "data engineering": "Data Engineering",
    "fastapi": "Software Engineering",
    "django": "Software Engineering",
    "flask": "Software Engineering",
    "docker": "Cloud",
    "kubernetes": "Cloud",
    "k8s": "Cloud",
    "terraform": "Cloud",
    "aws": "Cloud",
    "azure": "Cloud",
    "gcp": "Cloud",
    "react": "Software Engineering",
    "typescript": "Software Engineering",
    "git": "Tools",
    "pytorch": "Machine Learning",
    "tensorflow": "Machine Learning",
    "sklearn": "Machine Learning",
    "scikit-learn": "Machine Learning",
    "tableau": "Tools",
    "power bi": "Tools",
    "excel": "Tools",
    "linux": "Tools",
}

_DEGREE_WORDS = ("phd", "doctorate", "master", "msc", "bachelor", "bsc", "ms", "bs", "ma", "ba", "mba")

_REQUIRED_MARKERS = (
    "required",
    "must have",
    "must-have",
    "you have",
    "you will need",
    "essential",
    "minimum",
    "at least",
    "we require",
)
_PREFERRED_MARKERS = (
    "preferred",
    "nice to have",
    "nice-to-have",
    "desirable",
    "bonus",
    "plus",
    "a plus",
    "familiarity",
    "ideally",
)

_STOP_SKILL_WORDS = {"and", "or", "the", "a", "an", "of", "in", "with", "to", "for", "experience"}

# Openers that show a profile clause is not a first-person verb phrase. Used by
# the cover-letter builder to decide whether a clause can safely be given the
# subject "I". Heuristic, and deliberately conservative: a clause that starts
# with an unknown word is still treated as a verb phrase.
_NON_VERB_OPENERS = frozenset(
    {
        "a", "an", "the", "this", "that", "these", "those",
        "my", "our", "his", "her", "its", "their",
        "and", "or", "but", "so", "because", "although", "while", "when", "if",
        "in", "at", "on", "for", "with", "to", "from", "by", "as", "of",
        "into", "onto", "over", "under", "through", "across", "about",
        "against", "between", "within", "without", "during", "after",
        "before", "since", "until", "per", "via",
    }
)

# Fragments of HTML/URLs that reach the requirement vocabulary when a posting is
# pasted with markup intact. They can never be meaningful requirements, so they
# are excluded from relevance scoring. This guards only the scorer; the shared
# requirement extractor is deliberately left alone.
_MARKUP_TOKENS = frozenset(
    {"http", "https", "href", "html", "www", "com", "org", "net", "nbsp", "amp"}
)

# Display names for vocabulary keys that do not title-case correctly.
_SKILL_LABELS = {
    "python": "Python",
    "sql": "SQL",
    "postgres": "PostgreSQL",
    "nlp": "Natural Language Processing",
    "gcp": "GCP",
    "aws": "AWS",
    "k8s": "Kubernetes",
    "mlops": "Machine Learning Engineering",
    "sklearn": "scikit-learn",
    "scikit-learn": "scikit-learn",
    "pytorch": "PyTorch",
    "tensorflow": "TensorFlow",
    "power bi": "Power BI",
}

# Professional experience context patterns.
# Used to distinguish genuine experience requirements from narrative/age references
# when a sentence lacks explicit Required/Preferred markers.
_EXPERIENCE_POSITIVE_RE = re.compile(
    r"\b(?:"
    r"years?\s+of\s+(?:\w+\s+)*experience"
    r"|years?\s+experience"
    r"|years?\s+professional\s+experience"
    r"|years?\s+(?:as\s+a\s+|in\s+(?:a\s+)?)(?:machine learning|data|software|engineer|scientist|analyst|developer|manager|lead|senior|principal|ml|ai|deep learning)"
    r"|years?\s+(?:relevant|professional|work|industry)\s+experience"
    r")\b",
    re.IGNORECASE,
)

_EXPERIENCE_NEGATIVE_RE = re.compile(
    r"\b(?:"
    r"\d{1,2}\s*-\s*\d{1,2}\s*year\s*old"
    r"|\d{1,2}\s*year\s*old"
    r"|year\s*old"
    r"|(?:last|past|over\s+the)\s+\d{1,2}\s+years?"
    r"|\d{1,2}\s+years?\s+in\s+(?:the\s+)?(?:uk|us|usa|london|new york|san francisco|remote|market)"
    r"|(?:founded|operating|been|established)\s+(?:for\s+)?\d{1,2}\s+years?"
    r"|\d{1,2}\s+years?\s+(?:at|since)\b"
    r")\b",
    re.IGNORECASE,
)


def _is_professional_experience_context(sentence: str) -> bool:
    """Return True if a years pattern in the sentence refers to professional experience.

    This is only consulted when a sentence lacks explicit Required/Preferred markers.
    Positive patterns (years of experience, years as a role, etc.) indicate a genuine
    requirement. Negative patterns (age references, company history, location tenure)
    indicate narrative text that should not become an experience requirement.
    """
    low = sentence.lower()
    if _EXPERIENCE_NEGATIVE_RE.search(low):
        return False
    if _EXPERIENCE_POSITIVE_RE.search(low):
        return True
    return False


class OfflineProvider(AIProvider):
    name = "offline"

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _lines(text: str) -> list[str]:
        return [line.strip() for line in (text or "").splitlines()]

    @staticmethod
    def _split_sections(text: str) -> dict[str, list[str]]:
        """Split CV text into sections keyed by the heading vocabulary above."""
        sections: dict[str, list[str]] = {key: [] for key in _SECTION_HEADINGS}
        sections["_preamble"] = []
        current = "_preamble"

        for line in OfflineProvider._lines(text):
            lowered = line.lower().strip(" -—•*:|#").strip()
            if not lowered or len(line) > 80:
                if current != "_preamble":
                    sections[current].append(line)
                elif line:
                    sections["_preamble"].append(line)
                continue
            matched = None
            for key, headings in _SECTION_HEADINGS.items():
                if lowered in headings:
                    matched = key
                    break
            if matched:
                current = matched
                continue
            sections[current].append(line)

        # Text before the first heading is preamble; only keep it if a heading existed.
        if any(sections[k] for k in _SECTION_HEADINGS):
            sections["_preamble"] = []
        return sections

    @staticmethod
    def _split_job_sections(text: str) -> list[tuple[str, list[str]]]:
        """Split job description text into (heading, sentences) sections.

        Recognizes requirement-section headings so that subsequent sentences can
        be treated as implicit requirements. Returns a list of (section_type, sentences)
        where section_type is one of "requirements", "non_requirements", or "other".
        """
        lines = OfflineProvider._lines(text)
        sections: list[tuple[str, list[str]]] = []
        current_heading = "other"
        current_sentences: list[str] = []
        saw_responsibilities = False
        in_requirements_section = False

        def flush() -> None:
            nonlocal current_sentences
            if current_sentences:
                sections.append((current_heading, current_sentences))
                current_sentences = []

        def is_requirement_like(line: str) -> bool:
            low = line.lower()
            # Explicit markers
            if any(m in low for m in _REQUIRED_MARKERS + _PREFERRED_MARKERS):
                return True
            # Skill vocabulary hits
            if OfflineProvider._skills_in(line):
                return True
            # Years of experience pattern
            if re.search(r"\b\d{1,2}\+?\s*(?:-\s*\d{1,2})?\s*(?:years?|yrs?)", low):
                return True
            # Requirement-like phrasing
            if any(kw in low for kw in ("knowledge of", "exposure to", "proficiency", "familiarity", "experience in", "experience with", "background in")):
                return True
            return False

        for line in lines:
            lowered = line.lower().strip(" -—•*:|#").strip()
            if not lowered:
                continue
            # Check for requirement-section heading
            # Match at start of line for precision; avoid mid-sentence matches.
            if any(lowered.startswith(kw) or lowered == kw for kw in _JOB_REQUIREMENT_HEADINGS):
                flush()
                current_heading = "requirements"
                in_requirements_section = True
                continue
            # Check for non-requirement heading
            if any(lowered.startswith(kw) or lowered == kw for kw in _JOB_NON_REQUIREMENT_HEADINGS):
                flush()
                current_heading = "non_requirements"
                in_requirements_section = False
                continue
            # Responsibilities heading
            if lowered.startswith("responsibilities") or lowered.startswith("what you") or lowered.startswith("the role") or lowered.startswith("your impact") or lowered.startswith("duties"):
                flush()
                current_heading = "responsibilities"
                saw_responsibilities = True
                in_requirements_section = False
                continue
            # Generic heading (capitalized, short, ends with colon) - treat as section boundary
            if len(line) < 80 and line.endswith(":") and line[:1].isupper():
                flush()
                current_heading = "other"
                in_requirements_section = False
                continue

            # Transition detection: if we were in responsibilities and see requirement-like content,
            # start a new requirements section.
            if current_heading == "responsibilities" and is_requirement_like(line):
                flush()
                current_heading = "requirements"
                in_requirements_section = True

            # Skip sub-headings within requirements sections (e.g. "What we look for",
            # "Process Improvement & Documentation:", "Pay Grade - L").
            if in_requirements_section:
                low = line.lower()
                # Short, heading-like lines without requirement content
                if (len(line) < 80
                    and (line.endswith(":") or line[0].isupper())
                    and not is_requirement_like(line)
                    and not any(kw in low for kw in ("you have", "you will", "experience", "knowledge", "proficient", "familiar", "strong", "ability", "demonstrate"))):
                    continue

            current_sentences.append(line)

        flush()
        return sections

    @staticmethod
    def _bullets(lines: list[str]) -> list[str]:
        out = []
        for line in lines:
            cleaned = re.sub(r"^[•\-*●▪◦]\s*", "", line).strip()
            if cleaned:
                out.append(cleaned)
        return out

    @staticmethod
    def _find_dates(line: str) -> tuple[str | None, str | None]:
        match = _RANGE_RE.search(line)
        if not match:
            return None, None
        start = match.group(1)
        end = match.group(2)
        if end.lower() in {"present", "current", "now"}:
            return start, None
        return start, end

    # ------------------------------------------------------------------- extract

    def extract_cv(self, cv_text: str) -> ExtractedCV:
        text = cv_text or ""
        sections = self._split_sections(text)
        preamble = sections.get("_preamble", []) or self._lines(text)[:12]
        issues: list[str] = []

        result = ExtractedCV()

        joined = "\n".join(preamble)
        email = _EMAIL_RE.search(joined) or _EMAIL_RE.search(text)
        if email:
            result.email = email.group(0)
        phone = _PHONE_RE.search(joined)
        if phone:
            candidate_phone = phone.group(0).strip()
            if any(ch.isdigit() for ch in candidate_phone):
                result.phone = candidate_phone

        name = self._guess_name(preamble)
        if name:
            result.name = name

        title = self._guess_title(preamble)
        if title:
            result.professional_title = title

        location = self._guess_location(preamble)
        if location:
            result.location = location

        summary_lines = self._bullets(sections["summary"])
        if summary_lines:
            result.summary = " ".join(summary_lines)

        result.experience = self._extract_experience(sections["experience"], issues)
        result.education = self._extract_education(sections["education"])
        result.projects = self._extract_projects(sections["projects"])
        result.skills = self._extract_skills(sections["skills"], text, issues)
        result.certifications = self._extract_certifications(sections["certifications"])
        result.other = self._bullets(sections.get("certifications", []))[:0]

        if not result.experience:
            issues.append("No experience section was recognised in this CV.")
        if not result.education:
            issues.append("No education section was recognised in this CV.")
        if not result.skills:
            issues.append("No skills section was recognised in this CV.")
        if not result.name:
            issues.append("Candidate name could not be identified with confidence.")
        if not result.email:
            issues.append("No email address was found.")
        if not result.location:
            issues.append("Location could not be determined.")
        ambiguous = [e for e in result.experience if not e.start_date or not (e.end_date or e.is_current)]
        if ambiguous:
            issues.append(
                f"{len(ambiguous)} employment entry/entries have ambiguous or missing dates."
            )
        result.issues = issues
        return result

    @staticmethod
    def _guess_name(preamble: list[str]) -> str | None:
        for line in preamble[:6]:
            cleaned = line.strip()
            if not cleaned or "@" in cleaned or cleaned.lower().startswith("cv"):
                continue
            words = cleaned.split()
            if 2 <= len(words) <= 4 and all(w[:1].isalpha() for w in words):
                if any(ch.islower() for ch in cleaned) and any(ch.isupper() for ch in cleaned):
                    return cleaned
        return None

    @staticmethod
    def _guess_title(preamble: list[str]) -> str | None:
        title_words = (
            "engineer",
            "scientist",
            "developer",
            "analyst",
            "manager",
            "architect",
            "consultant",
            "specialist",
            "lead",
            "intern",
            "researcher",
            "programmer",
        )
        for line in preamble[:8]:
            lowered = line.lower()
            if any(word in lowered for word in title_words) and len(line) < 80:
                return line.strip()
        return None

    @staticmethod
    def _guess_location(preamble: list[str]) -> str | None:
        # First try: line is just a location like "Amsterdam, Netherlands"
        pattern = re.compile(r"^[A-Z][a-zA-Z .'-]+,\s*[A-Z][a-zA-Z .'-]+$")
        for line in preamble[:10]:
            candidate = line.strip()
            if pattern.match(candidate) and len(candidate) < 60:
                return candidate
        # Second try: location embedded in a line with other info (e.g. email | phone | location)
        for line in preamble[:10]:
            # Look for "City, Country" or "City, ST" patterns
            match = re.search(
                r"\b([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?),\s*([A-Z][a-zA-Z]+(?:\s[A-Z][a-zA-Z]+)?)\b",
                line,
            )
            if match:
                return f"{match.group(1)}, {match.group(2)}"
        return None

    @staticmethod
    def _extract_experience(lines: list[str], issues: list[str]) -> list[ExtractedExperience]:
        entries: list[ExtractedExperience] = []
        current: ExtractedExperience | None = None
        body: list[str] = []

        def flush() -> None:
            nonlocal current, body
            if current is not None:
                bullets = OfflineProvider._bullets(body)
                current.responsibilities = bullets
                current.description = " ".join(bullets)
                entries.append(current)
            current, body = None, []

        for line in lines:
            if not line:
                continue
            start, end = OfflineProvider._find_dates(line)
            header_like = start is not None or (
                len(line) < 120 and re.search(r"\b(at|@|,)\b|[|]", line) and len(line.split()) <= 12
            )
            if header_like:
                flush()
                cleaned = re.sub(r"\s*[([][^)\]]*[)\]]\s*", " ", line).strip()
                parts = [p.strip() for p in re.split(r"\s*[|@]\s*|\s+at\s+|,\s*", cleaned) if p.strip()]
                parts = [re.sub(r"[^A-Za-z0-9 .'&/+-]", "", p).strip() for p in parts]
                parts = [p for p in parts if p]
                title, company = (parts[0], parts[1]) if len(parts) >= 2 else (
                    (parts[0], "") if parts else (cleaned, "")
                )
                current = ExtractedExperience(
                    company=company or "Unknown",
                    title=title or "Unknown",
                    start_date=start,
                    end_date=end,
                    is_current=end is None,
                )
                continue
            if current is not None:
                body.append(line)
        flush()

        for entry in entries:
            if entry.company == "Unknown" or entry.title == "Unknown":
                issues.append(
                    f"Employer or title could not be parsed for '{entry.title or entry.company}' — please confirm."
                )
        return entries

    @staticmethod
    def _extract_education(lines: list[str]) -> list[ExtractedEducation]:
        entries: list[ExtractedEducation] = []
        for line in OfflineProvider._bullets(lines):
            # Preserve " | " for splitting, then clean other special chars
            cleaned = re.sub(r"[^A-Za-z0-9 ,.'()/\-&|]", " ", line)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
            if len(cleaned) < 4:
                continue
            start, end = OfflineProvider._find_dates(line)
            degree_match = next((d for d in _DEGREE_WORDS if re.search(rf"\b{d}\b", cleaned, re.I)), None)
            # Preserve original case from the text
            if degree_match:
                match = re.search(rf"\b{degree_match}\b", cleaned, re.I)
                degree = match.group(0) if match else degree_match.upper()
            else:
                degree = None
            institution = cleaned
            field = None
            # Split on " | " first (common CV format: "Degree | Institution")
            if " | " in cleaned:
                parts = cleaned.split(" | ", 1)
                degree_part = parts[0].strip()
                institution = parts[1].strip()
                # Check if the first part is actually a degree
                if degree and degree.lower() in degree_part.lower():
                    field = None
                else:
                    # First part might be the field, second is institution
                    field = degree_part
            elif "," in cleaned:
                institution = cleaned.split(",")[0].strip()
                remainder = cleaned.split(",", 1)[1].strip()
                field = remainder or None
            entries.append(
                ExtractedEducation(
                    institution=institution,
                    degree=degree,
                    field=field,
                    start_date=start,
                    end_date=end,
                    description=cleaned,
                )
            )
        return entries

    @staticmethod
    def _extract_projects(lines: list[str]) -> list[ExtractedProject]:
        entries: list[ExtractedProject] = []
        for line in OfflineProvider._bullets(lines):
            name, _, rest = line.partition(":")
            if not rest:
                name, rest = line, ""
            name = name.strip()[:120]
            rest = rest.strip()
            if len(name) < 3:
                continue
            technologies: list[str] = []
            tech_match = re.search(r"\[(.*?)\]|\((.*?)\)", rest)
            if tech_match:
                raw = tech_match.group(1) or tech_match.group(2) or ""
                technologies = [t.strip() for t in re.split(r"[,;/]", raw) if t.strip()]
                rest = (rest[: tech_match.start()] + rest[tech_match.end() :]).strip()
            entries.append(
                ExtractedProject(name=name, description=rest or None, technologies=technologies)
            )
        return entries

    @staticmethod
    def _extract_skills(
        skills_lines: list[str], full_text: str, issues: list[str]
    ) -> list[ExtractedSkill]:
        found: dict[str, ExtractedSkill] = {}
        haystack = " ".join(skills_lines).lower()
        if not haystack.strip():
            haystack = full_text.lower()
        for raw in re.split(r"[,;|/\n]|\band\b", haystack):
            token = raw.strip().strip(" .•-").lower()
            if not token or token in _STOP_SKILL_WORDS or len(token) > 40:
                continue
            for key, category in _SKILL_VOCAB.items():
                if key in token:
                    label = _SKILL_LABELS.get(key, key.title())
                    found.setdefault(label, ExtractedSkill(name=label, category=category))
                    break
        if not found and skills_lines:
            issues.append(
                f"{len(skills_lines)} skill line(s) were present but could not be identified — please add them manually."
            )
        return list(found.values())

    @staticmethod
    def _extract_certifications(lines: list[str]) -> list[ExtractedCertification]:
        entries: list[ExtractedCertification] = []
        for line in OfflineProvider._bullets(lines):
            cleaned = line.strip()
            if len(cleaned) < 3:
                continue
            issuer = None
            if "," in cleaned:
                cleaned, _, issuer = cleaned.partition(",")
                issuer = issuer.strip() or None
            year = re.search(r"(20)\d{2}", cleaned)
            entries.append(
                ExtractedCertification(name=cleaned.strip(), issuer=issuer, date=year.group(0) if year else None)
            )
        return entries

    # ------------------------------------------------------- job requirements

    def extract_job_requirements(self, job_description: str) -> ExtractedJobRequirements:
        # Job descriptions are often pasted straight from a posting page, so the
        # stored text can carry inline styles, block tags, list markup and
        # entities. Clean it once, here, *before* the description is split into
        # sentences and classified: that way requirement names, descriptions and
        # the 120-character name limit measure real content rather than tags, and
        # every downstream branch - skills, years, education, location,
        # eligibility and the generic required/preferred catch-all - sees the
        # same cleaned text. Plain-text descriptions are unaffected apart from
        # entity decoding.
        text = html_to_text(job_description)
        lowered = text.lower()
        result = ExtractedJobRequirements()

        required_skills: list[str] = []
        preferred_skills: list[str] = []
        other_required: list[ExtractedRequirement] = []
        other_preferred: list[ExtractedRequirement] = []

        # Split into sections to distinguish requirement lists from marketing/benefits.
        job_sections = self._split_job_sections(text)

        for section_type, section_lines in job_sections:
            # Skip explicit non-requirement sections (benefits, legal, etc.).
            if section_type == "non_requirements":
                continue

            # In a requirements section, treat sentences as implicit requirements.
            in_requirements_section = section_type == "requirements"

            for line in section_lines:
                # Split line into sentences (handles multi-sentence bullets).
                for sentence in re.split(r"(?<=[.!?])\s+", line):
                    sentence = sentence.strip(" \t-•*")
                    if len(sentence) < 8:
                        continue
                    low = sentence.lower()

                    # Determine importance: explicit markers win; in requirements
                    # section, default to PREFERRED (conservative) unless a
                    # positive experience context suggests REQUIRED.
                    is_required = any(m in low for m in _REQUIRED_MARKERS)
                    is_preferred = any(m in low for m in _PREFERRED_MARKERS) and not is_required
                    if not is_required and not is_preferred and in_requirements_section:
                        # Implicit requirement: default to PREFERRED. If the sentence
                        # contains a strong experience pattern, upgrade to REQUIRED.
                        if _is_professional_experience_context(sentence):
                            is_required = True
                        else:
                            is_preferred = True

                    skills = self._skills_in(sentence)
                    if skills:
                        if is_required:
                            required_skills.extend(skills)
                        elif is_preferred:
                            preferred_skills.extend(skills)
                        # A sentence may list skills AND a years-of-experience requirement
                        # (e.g. "Required: Python, SQL, and 5+ years..."). Check for years
                        # here so the skills branch does not silently swallow it. Other
                        # categories (education, location, eligibility) keep their existing
                        # control flow; the generic catch-all is not reached for this
                        # sentence.
                        if re.search(r"\b\d{1,2}\+?\s*(?:-\s*\d{1,2})?\s*(?:years?|yrs?)", low):
                            if is_required or is_preferred or _is_professional_experience_context(sentence):
                                match = _YEARS_RE.search(low)
                                years = float(match.group(1)) if match else None
                                requirement = ExtractedRequirement(
                                    name=sentence[:120],
                                    description=sentence,
                                    importance=Importance.REQUIRED if is_required else Importance.PREFERRED,
                                    years_required=years,
                                )
                                result.experience_requirements.append(requirement)
                        continue
                    if re.search(r"\b\d{1,2}\+?\s*(?:-\s*\d{1,2})?\s*(?:years?|yrs?)", low):
                        if is_required or is_preferred or _is_professional_experience_context(sentence):
                            match = _YEARS_RE.search(low)
                            years = float(match.group(1)) if match else None
                            requirement = ExtractedRequirement(
                                name=sentence[:120],
                                description=sentence,
                                importance=Importance.REQUIRED if is_required else Importance.PREFERRED,
                                years_required=years,
                            )
                            result.experience_requirements.append(requirement)
                        continue
                    # Catch "year(s) of experience" without a specific number
                    # (e.g. "year of experience in data analysis") when in a requirements
                    # section or with professional context.
                    if in_requirements_section and re.search(r"\byears?\s+of\s+experience\b", low):
                        requirement = ExtractedRequirement(
                            name=sentence[:120],
                            description=sentence,
                            importance=Importance.REQUIRED if is_required else Importance.PREFERRED,
                            years_required=None,
                        )
                        result.experience_requirements.append(requirement)
                        continue
                    if any(word in low for word in ("degree", "bachelor", "master", "phd", "university", "education:")):
                        result.education_requirements.append(
                            ExtractedRequirement(
                                name=sentence[:120],
                                description=sentence,
                                importance=Importance.REQUIRED if is_required else Importance.PREFERRED,
                            )
                        )
                        continue
                    # Exclude compensation/benefits marketing lines that happen to mention
                    # location or remote but are not genuine location constraints.
                    is_compensation_line = any(
                        kw in low
                        for kw in (
                            "salary",
                            "£",
                            "$",
                            "€",
                            "compensation",
                            "pay range",
                            "base pay",
                            "incentive",
                            "benefits",
                            "stipend",
                            "equity",
                            "bonus",
                            "package",
                            "hear from the team",
                            "we offer",
                            "perks",
                        )
                    )

                    if any(
                        marker in low
                        for marker in (
                            "based in",
                            "located in",
                            "office in",
                            "location",
                            "remote",
                            "hybrid",
                            "on-site",
                            "onsite",
                            "relocat",
                        )
                    ) and not is_compensation_line:
                        result.location_requirements.append(
                            ExtractedRequirement(
                                name=sentence[:120],
                                description=sentence,
                                importance=Importance.REQUIRED if is_required else Importance.PREFERRED,
                            )
                        )
                        continue
                    if any(
                        marker in low
                        for marker in (
                            "work authorization",
                            "work authorisation",
                            "right to work",
                            "visa",
                            "security clearance",
                            "citizen",
                            "residents",
                        )
                    ):
                        result.other_requirements.append(
                            ExtractedRequirement(
                                name=sentence[:120],
                                description=sentence,
                                importance=(
                                    Importance.REQUIRED if is_required else Importance.PREFERRED
                                ),
                            )
                        )
                        continue
                    if in_requirements_section:
                        # In a requirements section, sentences without other matches
                        # become generic requirements (OTHER type).
                        requirement = ExtractedRequirement(
                            name=sentence[:120],
                            description=sentence,
                            importance=Importance.REQUIRED if is_required else Importance.PREFERRED,
                        )
                        (other_required if is_required else other_preferred).append(requirement)
                        continue
                    elif is_required or is_preferred:
                        # No requirements section detected, but sentence has explicit
                        # Required/Preferred marker. Preserve legacy behaviour: create
                        # a generic requirement so that simple test descriptions and
                        # unstructured job postings still work.
                        requirement = ExtractedRequirement(
                            name=sentence[:120],
                            description=sentence,
                            importance=Importance.REQUIRED if is_required else Importance.PREFERRED,
                        )
                        (other_required if is_required else other_preferred).append(requirement)

        result.required_skills = self._dedupe(required_skills)
        result.preferred_skills = self._dedupe(preferred_skills)

        # Generic requirements the parser classified above are collected in
        # `other_required` / `other_preferred` but were never assigned onto the
        # result, so every such requirement was silently discarded and
        # `ExtractedJobRequirements.other_requirements` only ever received the
        # eligibility branch above. Write them back, preserving the importance
        # the parser assigned; the fields on the schema are unchanged.
        result.other_requirements.extend(other_required)
        result.other_requirements.extend(other_preferred)
        result.other_requirements = self._dedupe_requirements(result.other_requirements)

        responsibilities: list[str] = []
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
            low = sentence.strip().lower()
            if low.startswith(("responsibilities", "what you'll do", "what you will do", "the role", "your impact")):
                continue
            if any(low.startswith(verb) for verb in ("develop", "build", "design", "lead", "manage", "work with", "partner", "own ")):
                responsibilities.append(sentence.strip()[:300])
        result.responsibilities = self._dedupe(responsibilities)[:15]

        if "salary" not in lowered and ("€" not in text and "$" not in text and "£" not in text):
            result.issues.append("No salary information was stated in this description.")

        if not result.required_skills and not result.experience_requirements:
            result.issues.append(
                "Few explicit requirements were recognised — review the description and add them manually."
            )
        return result

    @staticmethod
    def _skills_in(sentence: str) -> list[str]:
        low = sentence.lower()
        hits: list[str] = []
        for key in _SKILL_VOCAB:
            if re.search(rf"\b{re.escape(key)}\b", low):
                hits.append(_SKILL_LABELS.get(key, key.title()))
        return OfflineProvider._dedupe(hits)

    @staticmethod
    def _dedupe(values: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for value in values:
            key = value.strip().lower()
            if key and key not in seen:
                seen.add(key)
                out.append(value.strip())
        return out

    @staticmethod
    def _dedupe_requirements(
        values: list[ExtractedRequirement],
    ) -> list[ExtractedRequirement]:
        """Drop repeats of the same requirement, keeping the first occurrence.

        A description that repeats a sentence, or states the same requirement
        twice, must not yield two rows downstream. Compared on the normalised
        name so punctuation and casing do not defeat the check.
        """
        seen: set[str] = set()
        out: list[ExtractedRequirement] = []
        for value in values:
            key = re.sub(
                r"[^a-z0-9]+", " ", (value.name or "").strip().lower()
            ).strip()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(value)
        return out

    # ---------------------------------------------------------------- analysis

    def analyze_cv_for_job(
        self,
        profile: ProfileSummary,
        job_description: str,
        job_title: str,
        company: str | None,
    ) -> CVAnalysis:
        analysis = CVAnalysis()
        requirements = self.extract_job_requirements(job_description)
        held = {s.name.lower(): s.name for s in profile.skills}

        for name in list(requirements.required_skills) + list(requirements.preferred_skills):
            if name.lower() in held:
                analysis.relevant_skills.append(held[name.lower()])
        analysis.relevant_skills = self._dedupe(analysis.relevant_skills)

        job_terms = set(re.findall(r"[a-z][a-z+#]{2,}", (job_title or "").lower()))
        for experience in profile.experience:
            blob = f"{experience.title} {experience.description or ''}".lower()
            overlap = job_terms & set(re.findall(r"[a-z][a-z+#]{2,}", blob))
            if overlap or any(s.lower() in blob for s in analysis.relevant_skills):
                analysis.relevant_experience.append(f"{experience.title} @ {experience.company}")

        for project in profile.projects:
            blob = f"{project.name} {project.description or ''}".lower()
            if any(s.lower() in blob for s in analysis.relevant_skills) or (
                job_terms & set(re.findall(r"[a-z][a-z+#]{2,}", blob))
            ):
                analysis.relevant_projects.append(project.name)

        for experience in profile.experience:
            for line in (experience.description or "").split(". "):
                line = line.strip()
                if len(line) > 30 and any(s.lower() in line.lower() for s in analysis.relevant_skills):
                    analysis.evidence_to_emphasize.append(line[:300])
        analysis.evidence_to_emphasize = self._dedupe(analysis.evidence_to_emphasize)[:8]

        relevant_exp = {e.lower() for e in analysis.relevant_experience}
        for experience in profile.experience:
            key = f"{experience.title} @ {experience.company}".lower()
            if key not in relevant_exp:
                analysis.content_to_de_emphasize.append(f"{experience.title} @ {experience.company}")
        relevant_projects = {p.lower() for p in analysis.relevant_projects}
        for project in profile.projects:
            if project.name.lower() not in relevant_projects:
                analysis.content_to_de_emphasize.append(f"Project: {project.name}")

        for skill in requirements.required_skills:
            if skill.lower() not in held:
                analysis.missing_requirements.append(
                    f"{skill} — required but not on your confirmed profile. Do not claim it."
                )
        for skill in requirements.preferred_skills:
            if skill.lower() not in held:
                analysis.missing_requirements.append(
                    f"{skill} — preferred but not on your confirmed profile."
                )
        for requirement in requirements.experience_requirements:
            if requirement.years_required:
                analysis.missing_requirements.append(
                    f"{requirement.years_required:g}+ years requested — confirm whether your "
                    "experience meets this before claiming it."
                )

        for item in analysis.missing_requirements:
            analysis.potential_problems.append(
                f"Claiming '{item.split(' —')[0]}' without supporting evidence would be inaccurate."
            )

        if analysis.relevant_skills:
            analysis.recommended_changes.append(
                "Lead the summary with: " + ", ".join(analysis.relevant_skills[:4]) + "."
            )
        for experience in analysis.relevant_experience[:2]:
            analysis.recommended_changes.append(f"Move '{experience}' higher and expand relevant bullets.")
        for evidence in analysis.evidence_to_emphasize[:3]:
            analysis.recommended_changes.append(f"Emphasise this evidence: {evidence[:160]}")
        for de_emphasised in analysis.content_to_de_emphasize[:3]:
            analysis.recommended_changes.append(
                f"De-emphasise or omit '{de_emphasised}' if space is limited."
            )
        if analysis.missing_requirements:
            analysis.recommended_changes.append(
                "Keep the gaps visible in the application rather than papering over them."
            )
        return analysis

    # ------------------------------------------------------------- tailoring

    def tailor_cv(
        self,
        profile: ProfileSummary,
        job_description: str,
        job_title: str,
        analysis: CVAnalysis | None = None,
        constraints: str = "",
    ) -> TailoredCVContent:
        analysis = analysis or self.analyze_cv_for_job(
            profile, job_description, job_title, None
        )
        content = TailoredCVContent()
        changes: list[str] = []

        # V2 strategy emphasis: promote the confirmed evidence the strategy
        # ranked highest. This reorders real evidence only - it never invents.
        if constraints:
            emphasised = self._emphasis_order(constraints)
            if emphasised:
                content.skills = emphasised + [
                    s for s in (analysis.relevant_skills or [])
                    if s not in emphasised
                ]

        relevant_skills = analysis.relevant_skills or [s.name for s in profile.skills]
        content.skills = [s for s in relevant_skills if s]

        target_terms = set(re.findall(r"[a-z][a-z+#]{2,}", (job_description or "").lower()))
        relevant_exp_ids = set()
        for experience in profile.experience:
            blob = f"{experience.title} {experience.description or ''}".lower()
            if any(s.lower() in blob for s in content.skills) or (
                target_terms & set(re.findall(r"[a-z][a-z+#]{2,}", blob))
            ):
                relevant_exp_ids.add(experience.id)

        ordered = sorted(
            profile.experience, key=lambda e: (e.id not in relevant_exp_ids, -(e.id or 0))
        )
        for experience in ordered:
            bullets = [
                line.strip(" -•*\t")
                for line in re.split(r"(?<=[.])\s+|\n", experience.description or "")
                if len(line.strip()) > 15
            ]
            if experience.id not in relevant_exp_ids and len(bullets) > 3:
                bullets = bullets[:2]
                changes.append(f"Condensed bullets for '{experience.title} @ {experience.company}'.")
            elif experience.id in relevant_exp_ids:
                changes.append(
                    f"Expanded relevant bullets for '{experience.title} @ {experience.company}'."
                )
            content.experience.append(
                TailoredExperience(
                    company=experience.company,
                    title=experience.title,
                    start_date=experience.start_date,
                    end_date=experience.end_date,
                    bullets=self._dedupe(bullets),
                )
            )

        for education in profile.education:
            content.education.append(
                TailoredEducation(
                    institution=education.institution,
                    degree=education.degree,
                    field=education.field,
                    end_date=education.end_date,
                )
            )

        relevant_projects = {p.lower() for p in analysis.relevant_projects}
        for project in profile.projects:
            if relevant_projects and project.name.lower() not in relevant_projects:
                continue
            content.projects.append(
                TailoredProject(
                    name=project.name,
                    description=project.description,
                    technologies=project.technologies,
                )
            )
        if relevant_projects:
            changes.append("Surfaced only the projects relevant to this role.")

        title = profile.professional_title or job_title
        if content.skills:
            summary = (
                f"{title} with {profile.years_of_experience:g} years of experience "
                f"across {', '.join(content.skills[:4])}."
                if profile.years_of_experience
                else f"{title} with experience across {', '.join(content.skills[:4])}."
            )
            if profile.location:
                summary += f" Based in {profile.location}."
            content.summary = summary
            changes.append("Rewrote the summary to lead with role-relevant skills.")

        content.changes_summary = self._dedupe(changes)
        return content

    # --------------------------------------------------------- cover letter

    def _job_requirement_terms(
        self, job_description: str, job_title: str
    ) -> set[str]:
        """Meaningful vocabulary the posting actually asks for.

        Generic words are dropped using the evidence module's existing
        GENERIC_TOKENS list. The previous selector keyed on job-*title* tokens
        alone, and "Data Analyst" shares the token "data" with almost every
        technology posting -- on this profile that single generic word marked
        seven of nine roles relevant, while the candidate held none of that
        posting's skills.
        """
        requirements = self.extract_job_requirements(job_description or "")
        raw: list[str] = [
            *requirements.required_skills,
            *requirements.preferred_skills,
            *(r.name for r in requirements.experience_requirements),
            *(r.name for r in requirements.education_requirements),
            job_title or "",
        ]
        terms: set[str] = set()
        for text in raw:
            for token in re.findall(r"[a-z][a-z+#]{2,}", str(text).lower()):
                if token not in GENERIC_TOKENS and token not in _MARKUP_TOKENS:
                    terms.add(token)
        return terms

    def _ranked_experience(
        self,
        profile: ProfileSummary,
        job_description: str,
        job_title: str,
        relevant_skills: list[str],
    ) -> list[ExtractedExperience]:
        """Order confirmed experience by defensible relevance to this job.

        Two signals, both anchored on the posting's own extracted requirements:

        * how many job-required skills the candidate actually holds appear in
          the record (``relevant_skills`` is already the intersection of the
          posting's requirements with the confirmed profile);
        * how many non-generic requirement terms appear in it.

        A skill named only in the posting contributes nothing to either signal:
        it is not evidence that the candidate has it.

        Records matching neither signal are never called relevant. When nothing
        qualifies the profile's own (reverse-chronological) order is used, which
        asserts nothing about relevance and invents nothing.

        Ordering is total and reproducible -- score descending, then profile
        position ascending -- so equally-scoring records never swap between
        runs, and a clearly relevant earlier role is not displaced by an
        unrelated more recent one.
        """
        terms = self._job_requirement_terms(job_description, job_title)
        held = list(relevant_skills)

        scored: list[tuple[int, int, int, ExtractedExperience]] = []
        for index, experience in enumerate(profile.experience):
            blob = f"{experience.title} {experience.description or ''}".lower()
            skill_hits = sum(1 for s in held if s.lower() in blob)
            term_hits = sum(1 for t in terms if t in blob)
            if skill_hits or term_hits:
                scored.append((skill_hits, term_hits, -index, experience))
        scored.sort(key=lambda item: item[:3], reverse=True)

        # Drop records describing the same underlying activity when a stronger
        # distinct one is already kept, so the letter does not spend two
        # sentences on one body of work.
        kept: list[ExtractedExperience] = []
        kept_blobs: list[str] = []
        for _, _, _, experience in scored:
            blob = re.sub(
                r"[^a-z0-9]+",
                " ",
                f"{experience.title} {experience.description or ''}".lower(),
            ).strip()
            if any(blob in other or other in blob for other in kept_blobs):
                continue
            kept_blobs.append(blob)
            kept.append(experience)

        return kept or list(profile.experience)

    def generate_cover_letter(
        self,
        profile: ProfileSummary,
        job_description: str,
        job_title: str,
        company: str | None,
        constraints: str = "",
    ) -> str:
        analysis = self.analyze_cv_for_job(profile, job_description, job_title, company)
        title = profile.professional_title or "Machine Learning Engineer"
        greeting_name = company or "your team"

        # V2: prefer strategy-emphasised evidence when ordering the body.
        ordered_skills = self._emphasis_order(constraints)
        ordered_skills += [
            s.name for s in profile.skills if s.name not in ordered_skills
        ]

        paragraphs: list[str] = []
        paragraphs.append(
            f"Dear {greeting_name} hiring team,"
        )

        intro = f"I am applying for the {job_title} role."
        if profile.years_of_experience:
            intro += (
                f" I bring {profile.years_of_experience:g} years of experience as "
                f"{profile.professional_title or title}."
            )
        paragraphs.append(intro)

        # Body sentences are assembled from confirmed profile prose only.
        #
        # Every clause keeps the wording the candidate recorded and is given a
        # subject ("At <employer> I ...") so it reads as a sentence instead of a
        # fragment, and no clause is used twice. The previous construction
        # ("Concretely, I would bring: <clause>" / "I have also <clause>") had no
        # subject, produced fragments and ungrammatical forms such as "I have
        # also provide technical guidance", and repeated clauses that had
        # already been stated in the experience paragraph.
        #
        # A clause whose first word is a determiner, pronoun or preposition is
        # not a verb phrase and cannot take a subject, so it is skipped rather
        # than forced into one.
        body: list[str] = []
        used_clauses: set[str] = set()
        # A cover letter is short. Experience is taken in profile order, which is
        # reverse-chronological, and stops once the budget is spent.
        budget = 4

        def _as_clause(raw: str) -> str | None:
            text = (raw or "").strip().rstrip(".").strip()
            if len(text.split()) < 3:
                return None
            key = re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()
            if not key or key in used_clauses:
                return None
            opener = re.split(r"[\s,;:()]+", text, 1)[0].lower()
            if opener in _NON_VERB_OPENERS:
                return None
            used_clauses.add(key)
            return text[0].lower() + text[1:]

        relevant_skills = set(analysis.relevant_skills)
        ranked_experience = self._ranked_experience(
            profile, job_description, job_title, analysis.relevant_skills
        )
        for experience in ranked_experience:
            parts = [
                p.strip()
                for p in (experience.description or "").split(". ")
                if p.strip()
            ]
            if not parts:
                parts = [f"worked as {experience.title}"]
            lead = _as_clause(parts[0])
            if lead is None:
                continue
            relevance = ""
            # Name the job-relevant skills this sentence does not already
            # mention, and only once the sentence has shown it is on-topic.
            if any(s.lower() in lead.lower() for s in relevant_skills):
                extra = [
                    s for s in ordered_skills
                    if s in relevant_skills and s.lower() not in lead.lower()
                ]
                if extra:
                    relevance = f", including {', '.join(extra[:3])}"
            body.append(f"At {experience.company} I {lead}{relevance}.")
            # One further recorded clause from the same role, so the letter shows
            # depth without restating the same sentences.
            if len(body) < budget:
                for part in parts[1:2]:
                    more = _as_clause(part)
                    if more is not None:
                        # The employer was just named in the preceding sentence
                        # and the pair always shares a paragraph, so repeating
                        # "At <employer> I" would only read as duplication.
                        body.append(f"I {more}.")
            if len(body) >= budget:
                break

        # Projects are evidenced separately from employment: naming a project
        # here never implies it was carried out for any employer.
        for project in profile.projects:
            if len(body) >= budget + 1:
                break
            if project.name not in analysis.relevant_projects:
                continue
            parts = [
                p.strip()
                for p in (project.description or "").split(". ")
                if p.strip()
            ]
            if not parts:
                continue
            lead = _as_clause(parts[0])
            if lead is not None:
                body.append(f"In the {project.name} project, I {lead}.")

        for start in range(0, len(body), 2):
            paragraphs.append(" ".join(body[start:start + 2]))

        if analysis.missing_requirements:
            gaps = "; ".join(item.split(" —")[0] for item in analysis.missing_requirements[:3])
            paragraphs.append(
                f"I want to be straightforward about a gap: my background is thinner on {gaps} "
                f"than the rest of my experience, and I would rather flag that than overstate it. "
                f"I would welcome the chance to discuss how quickly I could close it."
            )

        closing = f"I would welcome the opportunity to discuss the {job_title} role."
        if company:
            closing += " Thank you for your time and consideration."
        paragraphs.append(closing)
        paragraphs.append(f"Kind regards,\n{profile.name}")

        return "\n\n".join(paragraphs)

    @staticmethod
    def _emphasis_order(constraints: str) -> list[str]:
        """Extract emphasised evidence labels from the strategy constraint text."""
        match = re.search(r"Prioritise this confirmed evidence:\s*(.+?)\.", constraints)
        if not match:
            return []
        return [part.strip() for part in match.group(1).split(",") if part.strip()]

    # --------------------------------------------------------- strategy (V2)

    def compose_strategy_narrative(self, context: StrategyContext) -> StrategyNarrative:
        """Phrase an already-computed strategy. Adds no new candidate facts."""
        parts: list[str] = []

        strength_names = [s.requirement_name for s in context.strengths[:4]]
        if strength_names:
            parts.append(
                "Strong alignment on " + ", ".join(strength_names) + "."
            )
        else:
            parts.append("No requirement was matched as strong in this comparison.")

        if context.transferable_evidence:
            parts.append(
                "Relevant adjacent evidence is available for "
                + ", ".join(t.requirement_name for t in context.transferable_evidence[:3])
                + "."
            )

        required = [
            g for g in context.gaps
            if g.severity == "REQUIRED_GAP"
        ]
        if required:
            parts.append(
                "The principal limitation is that "
                + ", ".join(g.requirement_name for g in required[:3])
                + " is not established in the confirmed evidence."
            )
        elif context.gaps:
            parts.append(
                "Remaining gaps are preferred rather than mandatory: "
                + ", ".join(g.requirement_name for g in context.gaps[:3])
                + "."
            )

        if context.blockers:
            parts.append(
                "Unresolved blockers: "
                + "; ".join(b.statement for b in context.blockers[:2])
            )

        return StrategyNarrative(decision_summary=" ".join(parts))


__all__ = ["OfflineProvider"]
