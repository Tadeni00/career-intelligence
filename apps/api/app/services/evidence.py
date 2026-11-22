"""Confirmed-evidence model and claim classification.

Claims are *derived* from the confirmed profile and CareerEvidence records. The
user never annotates sentences. Each claim carries a category, a set of
supporting terms, and an explicit "support strength" so the validator can judge
semantic scope rather than shared keywords.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field

from app.schemas import ProfileSummary
from app.services.normalization import (
    canonical_tech,
    normalize_text,
    normalize_title,
    sentence_tokens,
    tokens,
)

# --- categories (spec section 5) -------------------------------------------


class EvidenceCategory(enum.StrEnum):
    IDENTITY = "IDENTITY"
    EMPLOYMENT = "EMPLOYMENT"
    EDUCATION = "EDUCATION"
    SKILL = "SKILL"
    TECHNOLOGY = "TECHNOLOGY"
    RESPONSIBILITY = "RESPONSIBILITY"
    ACHIEVEMENT = "ACHIEVEMENT"
    METRIC = "METRIC"
    PROJECT = "PROJECT"
    CLIENT = "CLIENT"
    INDUSTRY = "INDUSTRY"
    ELIGIBILITY = "ELIGIBILITY"
    CONTACT = "CONTACT"


class ClaimClass(enum.StrEnum):
    SUPPORTED = "SUPPORTED"
    SUPPORTED_BY_ALIAS = "SUPPORTED_BY_ALIAS"
    SUPPORTED_BY_NORMALIZATION = "SUPPORTED_BY_NORMALIZATION"
    PLAUSIBLE_BUT_UNVERIFIED = "PLAUSIBLE_BUT_UNVERIFIED"
    STRENGTHENED = "STRENGTHENED"
    UNSUPPORTED = "UNSUPPORTED"
    CONTRADICTORY = "CONTRADICTORY"
    SUSPICIOUS = "SUSPICIOUS"
    UNKNOWN = "UNKNOWN"
    NON_FACTUAL = "NON_FACTUAL"


class ClaimSeverity(enum.StrEnum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFORMATIONAL = "INFORMATIONAL"


# Classifications that must never be downgraded to review-only.
HARD_FAILURE_CLASSES = {
    ClaimClass.UNSUPPORTED,
    ClaimClass.STRENGTHENED,
    ClaimClass.CONTRADICTORY,
    ClaimClass.SUSPICIOUS,
}

# Classifications that are accepted outright.
ACCEPTED_CLASSES = {
    ClaimClass.SUPPORTED,
    ClaimClass.SUPPORTED_BY_ALIAS,
    ClaimClass.SUPPORTED_BY_NORMALIZATION,
    ClaimClass.NON_FACTUAL,
}


# --- term vocabularies ------------------------------------------------------

# Tokens that legitimately appear in prose and carry no evidence weight.
GENERIC_TOKENS: frozenset[str] = frozenset({
    # CV scaffolding
    "experience", "experienced", "professional", "skills", "skill", "summary",
    "profile", "education", "project", "projects", "team", "teams", "work",
    "worked", "working", "years", "year", "including", "include", "includes",
    "using", "use", "used", "across", "within", "role", "job", "company",
    "candidate", "and", "the", "for", "with", "from", "that", "this", "will",
    "have", "has", "had", "was", "were", "are", "but", "not", "you", "your",
    "our", "we", "who", "all", "new", "own", "built", "build", "developed",
    "develop", "created", "create", "delivered", "delivery", "improved",
    "improve", "increase", "increased", "reduced", "reduce", "support",
    "supported", "manage", "managed", "leading", "led", "helped", "focused",
    "focus", "plus", "well", "also", "etc", "able", "ability", "strong",
    "excellent", "proven", "results", "result", "data", "science",
    "engineering", "engineer", "scientist", "specialist", "developer",
    "manager", "senior", "junior", "mid", "level", "based", "location",
    # reporting / narrative
    "report", "reports", "reporting", "insight", "insights", "findings",
    "analysis", "analytical", "stakeholders", "stakeholder", "business",
    "decisions", "decision", "making", "process", "processes", "quality",
    "accurate", "accuracy", "reliable", "reliability", "effective",
    "efficiency", "actionable", "recommendations", "clear", "communicate",
    "communication", "collaborate", "collaboration", "detail", "oriented",
    "organised", "organized", "multiple", "tasks", "proactive", "mindset",
    # common filler adjectives/adverbs that are not evidentiary
    "recent", "current", "various", "several", "many", "most", "other",
    "others", "such", "same", "both", "each", "any", "than", "then", "when",
    "where", "while", "overall", "key", "main", "regular",
    "successfully", "effectively", "significantly", "substantially",
    "extensively", "demonstrated", "demonstrate", "ensuring",
    "ensured", "ensure", "provides", "provided", "provide", "helping",
    # NOTE: frequency/scope intensifiers (routinely, consistently, frequently,
    # extensively, actively) are deliberately NOT generic - they must survive
    # into the strengthening check.
    # first-person / correspondence boilerplate (never evidentiary)
    "i", "me", "my", "mine", "us", "ours", "myself", "ourselves",
    "am", "is", "be", "been", "being",
    "dear", "hiring", "regards", "kind", "sincerely", "yours", "truly",
    "faithfully", "best", "warm", "thank", "thanks", "please", "welcome",
    "applying", "apply", "opportunity", "discuss", "discussion", "conversation",
    "excited", "eager", "keen", "interest", "interested", "enjoy", "enjoyed",
    "looking", "forward", "hearing", "grateful", "thankful", "attach",
    "attached", "resume", "portfolio", "cv", "letter", "herewith", "pleasure",
})

# Interaction verbs describe correspondence, not candidate capability. They must
# not make a sentence "factual" (V1.2 precision: "I would welcome the chance to
# discuss the role" asserts nothing).
INTERACTION_VERBS = frozenset({
    "discuss", "discussed", "welcome", "welcomed", "apply", "applied",
    "thank", "thanked", "contact", "contacted", "reach", "reached",
    "enquire", "inquire", "correspond", "write", "wrote",
    "read", "reviewing", "attach", "attached", "submit", "submitted",
    "speaking", "spoke", "meet", "meeting", "call", "called", "email",
    "interested", "considering", "note", "noticed", "mention", "mentioned",
})

# Verbs that assert responsibility/action; a sentence containing one is treated
# as a factual candidate claim rather than pure commentary.
ACTION_VERBS = frozenset({
    "built", "build", "developed", "develop", "created", "create", "designed",
    "design", "led", "lead", "managed", "manage", "delivered", "deliver",
    "implemented", "implement", "maintained", "maintain", "automated",
    "launched", "launch", "owned", "own", "drove", "drive", "established",
    "introduced", "scaled", "optimised", "optimized", "performed", "conducted",
    "analysed", "analyzed", "executed", "collected", "processed", "cleaned",
    "validated", "generated", "produced", "prepared", "reviewed", "coached",
    "mentored", "mentoring", "taught", "trained", "guided", "supported",
    "collaborated", "partnered", "authored", "engineered", "structured",
    "documented", "presented", "investigated", "researched",
    "forecasted", "segmented", "tracked", "monitored", "audited", "tested",
    "deployed", "integrated", "migrated", "configured", "spearheaded",
})

# Only these make a sentence a candidate-specific factual assertion.
EVIDENCE_ACTION_VERBS = ACTION_VERBS - INTERACTION_VERBS

METRIC_RE = re.compile(
    r"(?:[$€£¥₦]\s?\d[\d,.]*)|"
    r"(?:\b\d[\d,.]*\s*(?:%|percent|per cent|x\b|million|billion|thousand|k\b))|"
    r"(?:\b\d[\d,.]*\s*(?:bn|mm|k)\b)|"
    r"(?:\b\d[\d,.]+\s*(?:records|rows|transactions|customers|users|cases|"
    r"documents|entries|observations|samples|clients|projects|reports)\b)",
    re.I,
)

ELIGIBILITY_PATTERNS = [
    r"\bauthoris?z?ed to work\b",
    r"\bright to work\b",
    r"\bwork authoris?z?ation\b",
    r"\bwork permit\b",
    r"\bno sponsorship (?:is )?required\b",
    r"\bdo(?:es)? not require sponsorship\b",
    r"\brequire(?:s)? (?:no )?(?:visa )?sponsorship\b",
    r"\bwork(?:ing)? eligib(?:le|ility)\b",
    r"\beligib(?:le|ility) to work\b",
    r"\bsecurity clearance\b",
    r"\bcitizen(?:ship)?\b",
    r"\bpermanent resident\b",
    r"\bvisa status\b",
    r"\bvisa[- ]sponsorship\b",
    r"\bleg(?:al|ally) (?:entitled|eligible)\b",
]
ELIGIBILITY_RE = re.compile("|".join(ELIGIBILITY_PATTERNS), re.I)

# Named counterparties introduced beyond the evidenced "cross-functional teams".
# Deliberately a curated noun list: a free-text "with X to Y" pattern produced
# heavy false positives in V1.1 review, so only specific role/client nouns count.
SPECIFIC_ROLES_RE = re.compile(
    r"\b(?:product owners?|engineering(?:ers)?|devops engineers?|sre(?:s)?|"
    r"qa engineers?|product managers?|compliance teams?|designers?|architects?|"
    r"data engineers?|ml engineers?|marketing teams?|recruitment teams?|"
    r"external partners?|clients?|customers?)\b",
    re.I,
)
# Generic collective nouns that ARE supported by ordinary professional evidence.
_GENERIC_COUNTERPARTIES = {
    "teams", "team", "stakeholders", "stakeholder", "clients", "client",
    "customers", "customer", "partners", "partner", "colleagues", "peers",
    "cross", "functional", "learners", "students", "fellows", "mentors",
    "managers", "leaders", "business", "users", "internal", "non", "technical",
    "engineering", "leadership", "recruitment", "field",
    "marketers",
}

_URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"(?:\+\d[\d\s().-]{6,}\d)")


# Function words carry no evidentiary content in any sentence.
FUNCTION_TOKENS: frozenset[str] = frozenset({
    "to", "as", "at", "by", "of", "in", "on", "or", "if", "then", "than", "so",
    "but", "nor", "yet", "into", "onto", "from", "with", "without", "within",
    "would", "could", "should", "shall", "will", "can", "may", "might", "must",
    "do", "does", "did", "done", "have", "has", "had", "get", "got", "make",
    "made", "take", "took", "give", "gave", "come", "came", "go", "went",
    "bring", "brings", "bringing", "brought", "put", "keep", "kept", "let",
    "allow", "allows", "help", "helps", "helped", "ensure", "ensures",
    "aim", "aims", "aimed", "seek", "seeks", "sought",
    "across", "among", "amongst", "through", "throughout", "over", "under",
    "between", "about", "against", "toward", "towards", "upon", "per",
    "also", "more", "most", "less", "least", "much", "many", "few", "some",
    "any", "each", "every", "both", "either", "neither", "one", "two",
    "first", "second", "next", "last", "same", "other", "another", "such",
    # articles, copulas and degree-holding verbs
    "a", "an", "the", "hold", "holds", "holding", "held", "earned", "obtained", "graduated", "completed", "studied", "studying", "degree",
    "bachelor", "bachelors", "master", "masters", "msc", "bsc", "phd",
})

GENERIC_TOKENS = GENERIC_TOKENS | FUNCTION_TOKENS

# --- V1.2 precision vocabularies ------------------------------------------
# Professional adjectives used decoratively. Their presence is not evidence of
# fabrication (spec section 10, step 2); they indicate weak qualifier wording at
# most, never a factual assertion on their own.
BENIGN_QUALIFIERS = frozenset({
    "effective", "strong", "proven", "solid", "reliable", "robust", "sound",
    "rigorous", "practical", "valuable", "meaningful", "significant",
    "professional", "analytical", "collaborative", "communicative",
    "motivated", "capable", "oriented", "organised", "organized", "dedicated",
    "committed", "proactive", "resourceful", "adaptable", "flexible",
    "positive", "enthusiastic", "driven", "focused", "structured",
    "comprehensive", "consistent", "accurate", "clear", "concise", "actionable",
    # generic connective / abstract vocabulary that carries no factual weight
    "background", "foundation", "commitment", "mentorship", "concept",
    "concepts", "core", "matter", "matters", "involved", "involves",
    "require", "requires", "required", "contribute", "contributes",
    "contributed", "deliver", "delivers", "delivering", "drive", "drives",
    "guarantee", "integrating", "reinforcing", "enabling", "diverse",
    "experiences", "experience", "colleagues", "everywhere", "across",
    "efficient", "quality", "excellent", "usable", "repeatable",
    # frequency/degree adverbs: describe habit, not capability strength
    "daily", "weekly", "monthly", "yearly", "quarterly", "regularly",
    "normally", "typically", "generally", "occasionally", "independently",
    "thoroughly", "carefully", "closely", "directly", "collaboratively",
    "chance", "opportunity", "invitation", "consideration", "conversation",
})

# Deliberate paraphrase equivalences. Each group asserts that its members carry
# materially the same factual meaning. This is NOT general synonym expansion:
# entries are explicit and testable.
# Commentary about the employer, the role, or the candidate's interest. Spec
# section 10 step 2 explicitly excludes "generic statements about working,
# learning, interest" from candidate-specific factual claims.
_INTENT_TOKENS: frozenset[str] = frozenset({
    "excited", "eager", "welcome", "welcomed", "opportunity", "considering",
    "interested", "interest", "looking", "look", "forward", "hearing",
    "discussion", "discuss", "discussing", "grateful", "thankful", "please",
    "find", "attached", "resume", "cv", "portfolio", "applying", "apply",
    "applied", "regards", "sincerely", "kind", "best", "yours", "thank",
    "thanks", "dear", "hiring", "team", "teams", "chance", "meet", "speak",
    "how", "quickly", "background", "straightforward", "willing", "rest",
    "honest", "overstate", "much", "far", "more", "less", "show", "showcase",
    "highlight", "mention", "note", "add", "value", "join", "joining", "next",
    "fit", "match", "matches", "suit", "worth", "worthwhile", "later",
    "future", "writing", "write", "wrote", "express", "expressing", "drawn",
    "attracted", "aligns", "aligned", "alignment", "resonates", "mission",
    "vision", "values", "culture", "why", "keen", "delighted", "enthusiasm",
    "motivation", "aim", "aspire", "contribute", "invite", "invited",
    "position", "employer", "organisation", "organization", "requirements",
    "role", "needs", "need", "deserves", "impressed", "impressive",
})

PARAPHRASE_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"conducted", "performed", "carried", "executed", "ran"}),
    frozenset({"analyse", "analyzed", "analysis", "analysing", "analyzing"}),
    frozenset({"build", "built", "develop", "developed", "constructed", "created"}),
    frozenset({"make", "made", "produce", "produced", "generate", "generated"}),
    frozenset({"clean", "cleaned", "cleanse", "purify"}),
    frozenset({"validate", "validated", "verification", "verified"}),
    frozenset({"support", "supported", "supporting", "aided", "assisted", "backed"}),
    frozenset({"dashboard", "dashboards", "report", "reports", "reporting"}),
    frozenset({"pipeline", "pipelines", "workflow", "workflows"}),
    frozenset({"client", "clients", "customer", "customers", "stakeholder",
               "stakeholders"}),
    frozenset({"automate", "automated", "automation", "streamline"}),
    frozenset({"mentor", "mentored", "mentoring", "coach", "coached", "train",
               "trained", "teach", "taught"}),
    frozenset({"visualise", "visualized", "visualize", "visualisation",
               "visualization", "chart", "charts"}),
    frozenset({"statistic", "statistics", "statistical", "quantitative"}),
    frozenset({"predict", "predicted", "prediction", "predictive", "forecast"}),
)

_PARAPHRASE_INDEX: dict[str, frozenset[str]] = {}
for _group in PARAPHRASE_GROUPS:
    for _member in _group:
        _PARAPHRASE_INDEX[_member] = _group


def paraphrase_match(token: str, support: set[str]) -> bool:
    """True when a token has an evidenced paraphrase equivalent."""
    group = _PARAPHRASE_INDEX.get(token)
    if not group:
        return False
    return bool((group - {token}) & support)


# --- claim model ------------------------------------------------------------


@dataclass
class EvidenceItem:
    """One confirmed fact usable as support for a generated claim."""

    category: EvidenceCategory
    label: str
    text: str
    support: set[str] = field(default_factory=set)
    numeric: set[str] = field(default_factory=set)
    role: str = ""  # e.g. "employer" / "position" within a category

    def supports_token(self, token: str) -> bool:
        return token in self.support


@dataclass
class Claim:
    text: str
    category: EvidenceCategory | None
    classification: ClaimClass
    reason: str = ""
    tokens: set[str] = field(default_factory=set)
    metric_values: set[str] = field(default_factory=set)
    # --- V1.2 traceability (spec section 9) -------------------------------
    severity: ClaimSeverity = ClaimSeverity.INFORMATIONAL
    matched_evidence: list[str] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    action: str = ""

    def to_trace(self) -> dict:
        return {
            "claim": self.text[:300],
            "category": self.category.value if self.category else None,
            "classification": self.classification.value,
            "severity": self.severity.value,
            "matched_evidence": self.matched_evidence[:5],
            "missing_terms": self.missing_terms[:8],
            "reason": self.reason,
            "action": self.action,
        }


def _mk(category: EvidenceCategory, label: str, text: str) -> EvidenceItem:
    body = f"{label} {text or ''}"
    return EvidenceItem(
        category=category,
        label=label,
        text=text or "",
        support=tokens(body) - GENERIC_TOKENS,
        numeric={m.group(0).lower().replace(" ", "") for m in METRIC_RE.finditer(body)},
    )


@dataclass
class EvidenceIndex:
    items: list[EvidenceItem] = field(default_factory=list)

    def add(self, item: EvidenceItem) -> None:
        self.items.append(item)

    # -- lookups ----------------------------------------------------------
    def employers(self) -> set[str]:
        return {
            normalize_title(i.label)
            for i in self.items
            if i.category is EvidenceCategory.EMPLOYMENT and i.role == "employer"
        }

    def titles(self) -> set[str]:
        return {
            normalize_title(i.label)
            for i in self.items
            if i.category is EvidenceCategory.EMPLOYMENT and i.role == "position"
        }

    def institutions(self) -> set[str]:
        return {
            normalize_title(i.label)
            for i in self.items
            if i.category is EvidenceCategory.EDUCATION
        }

    def degrees(self) -> set[str]:
        return {
            normalize_title(i.label)
            for i in self.items
            if i.category is EvidenceCategory.EDUCATION
        }

    def technologies(self) -> set[str]:
        return {
            canonical_tech(i.label)
            for i in self.items
            if i.category in (EvidenceCategory.TECHNOLOGY, EvidenceCategory.SKILL)
        }

    def all_support(self) -> set[str]:
        out: set[str] = set()
        for item in self.items:
            out |= item.support
        return out

    def all_numeric(self) -> set[str]:
        out: set[str] = set()
        for item in self.items:
            out |= item.numeric
        return out

    def has_eligibility(self) -> bool:
        return any(i.category is EvidenceCategory.ELIGIBILITY for i in self.items)

    def eligibility_text(self) -> str:
        return " ".join(
            i.text for i in self.items if i.category is EvidenceCategory.ELIGIBILITY
        )

    def contacts(self) -> dict[str, str]:
        out: dict[str, str] = {}
        for item in self.items:
            if item.category is EvidenceCategory.CONTACT:
                out[item.label] = item.text
        return out


def build_index(profile: ProfileSummary, extra_evidence: list[str] | None = None) -> EvidenceIndex:
    """Derive the confirmed-evidence index from the profile."""
    idx = EvidenceIndex()

    # Identity
    for label, value in (
        ("name", profile.name),
        ("professional title", profile.professional_title or ""),
        ("location", profile.location or ""),
    ):
        if value:
            idx.add(_mk(EvidenceCategory.IDENTITY, label, str(value)))

    # The confirmed professional summary is itself evidence. Omitting it made
    # legitimate claims phrased from the summary look unsupported.
    if profile.summary:
        idx.add(_mk(EvidenceCategory.ACHIEVEMENT, "professional summary",
                    str(profile.summary)))

    # Stated total experience (supports "6 years of experience" style claims)
    if profile.years_of_experience:
        idx.add(_mk(EvidenceCategory.IDENTITY, "years of experience",
                    f"{profile.years_of_experience:g} years"))

    # Contact (only when confirmed on the profile)
    for label, value in (("email", profile.email), ("phone", profile.phone)):
        if value:
            idx.add(_mk(EvidenceCategory.CONTACT, label, str(value)))

    # Employment — one item per fact so employers() and titles() stay distinct
    for exp in profile.experience:
        idx.add(EvidenceItem(
            category=EvidenceCategory.EMPLOYMENT,
            label=exp.company,
            text=exp.title,
            role="employer",
            support=(tokens(f"{exp.company} {exp.title} {exp.description or ''}")
                     - GENERIC_TOKENS),
        ))
        idx.add(EvidenceItem(
            category=EvidenceCategory.EMPLOYMENT,
            label=exp.title,
            text=exp.company,
            role="position",
            support=(tokens(f"{exp.title} {exp.company} {exp.description or ''}")
                     - GENERIC_TOKENS),
        ))

    # Education
    for edu in profile.education:
        idx.add(_mk(EvidenceCategory.EDUCATION, edu.institution,
                    f"{edu.degree or ''} {edu.field or ''} {edu.description or ''}"))
        if edu.degree:
            idx.add(_mk(EvidenceCategory.EDUCATION, edu.degree, edu.field or ""))

    # Skills / technologies
    for skill in profile.skills:
        category = (
            EvidenceCategory.TECHNOLOGY
            if canonical_tech(skill.name) and _looks_like_technology(skill.name)
            else EvidenceCategory.SKILL
        )
        idx.add(_mk(category, skill.name, skill.notes or ""))
        idx.add(_mk(EvidenceCategory.SKILL, skill.name, skill.category or ""))

    # Projects
    for project in profile.projects:
        idx.add(_mk(EvidenceCategory.PROJECT, project.name,
                    f"{project.description or ''} {' '.join(project.technologies)}"))

    # Free-text evidence rows (e.g. eligibility recorded as evidence)
    for row in extra_evidence or []:
        idx.add(_mk(EvidenceCategory.ELIGIBILITY, "eligibility", row))

    return idx


def _looks_like_technology(name: str) -> bool:
    tech_tokens = {
        "python", "sql", "excel", "power", "bi", "tableau", "pandas", "numpy",
        "matplotlib", "seaborn", "spss", "git", "github", "postgres", "postgresql",
        "aws", "azure", "gcp", "docker", "kubernetes", "spark", "airflow",
        "tensorflow", "pytorch", "sklearn", "scikit", "learn", "mlflow",
        "lightgbm", "xgboost", "catboost", "fastapi", "django", "flask",
        "react", "typescript", "javascript", "r", "scala", "java", "hadoop",
        "dask", "ray", "kubeflow", "looker",
    }
    return bool(tokens(name) & tech_tokens)


# --- sentence classification ----------------------------------------------


_GREETING_RE = re.compile(
    r"^\s*(?:dear\b|to whom it may concern\b|hello\b|hi\b)", re.I)
_CLOSING_RE = re.compile(
    r"^\s*(?:kind\s+regards|best\s+regards|yours\s+(?:sincerely|faithfully|truly)"
    r"|sincerely|regards|thank you|thanks|with thanks|"
    r"sincerely\s+your|your sincerely)\b", re.I)


_GAP_DISCLOSURE_RE = re.compile(
    r"\b(?:thinner on|weaker on|little experience|limited experience with|"
    r"less experience (?:with|in)|not (?:yet )?(?:experienced|familiar) (?:with|in)|"
    r"have not (?:worked|used)|haven't (?:worked|used)|no (?:direct )?experience (?:with|in)|"
    r"my background is (?:thinner|weaker)|gap in my|strengthen this|close (?:it|this|that))\b",
    re.I,
)


def _is_non_factual(sentence: str) -> bool:
    """Sentences that assert nothing candidate-specific."""
    lowered = normalize_text(sentence)
    if not lowered:
        return True
    # Greeting and sign-off lines are correspondence structure, not claims.
    if _GREETING_RE.match(sentence) or _CLOSING_RE.match(sentence):
        return True
    # Explicit admissions of absence assert the *opposite* of a claim, so they
    # cannot overstate capability. ("my background is thinner on Kubernetes")
    if _GAP_DISCLOSURE_RE.search(sentence):
        return True
    st = set(sentence_tokens(sentence))
    if not st:
        return True
    if st & EVIDENCE_ACTION_VERBS:
        return False
    factual_markers = {
        "years", "experience", "worked", "degree", "university", "certified",
        "authorized", "authorised", "eligible", "proficient", "specialise",
        "specialize",
    }
    if st & factual_markers:
        return False
    # Pure first-person intent/enthusiasm with no candidate fact.
    return (st - GENERIC_TOKENS) <= _INTENT_TOKENS


def classify_sentence(
    sentence: str,
    idx: EvidenceIndex,
    *,
    category_hint: EvidenceCategory | None = None,
    job_terms: set[str] | None = None,
) -> Claim:
    """Classify one generated sentence against confirmed evidence.

    ``job_terms`` are vocabulary supplied by the posting. Words that come from
    the job description are not treated as candidate claim-strengthening.
    """
    job_terms = job_terms or set()
    text = sentence.strip()
    st = set(sentence_tokens(text))
    support = idx.all_support()

    if _is_non_factual(text):
        return Claim(text, None, ClaimClass.NON_FACTUAL,
                     "no candidate-specific assertion", st,
                     severity=ClaimSeverity.INFORMATIONAL)

    # --- eligibility (checked first: highest risk) -----------------------
    if ELIGIBILITY_RE.search(text):
        if idx.has_eligibility():
            return Claim(text, EvidenceCategory.ELIGIBILITY, ClaimClass.SUPPORTED,
                         "explicit eligibility evidence on record", st,
                         severity=ClaimSeverity.INFORMATIONAL,
                         matched_evidence=["eligibility record"])
        return Claim(text, EvidenceCategory.ELIGIBILITY, ClaimClass.UNSUPPORTED,
                     "eligibility claim with no evidence on the confirmed profile",
                     st, severity=ClaimSeverity.CRITICAL,
                     action="Remove the eligibility claim or record evidence.")

    # --- metrics ---------------------------------------------------------
    metrics = {m.group(0).lower().replace(" ", "") for m in METRIC_RE.finditer(text)}
    if metrics:
        known = idx.all_numeric()
        invented = {m for m in metrics if m not in known}
        if invented:
            return Claim(text, EvidenceCategory.METRIC, ClaimClass.UNSUPPORTED,
                         f"metric not present in confirmed evidence: "
                         f"{sorted(invented)}", st,
                         severity=ClaimSeverity.HIGH,
                         action="Remove or replace this claim.")
        return Claim(text, EvidenceCategory.METRIC, ClaimClass.SUPPORTED,
                     "all metrics evidenced", st,
                     severity=ClaimSeverity.INFORMATIONAL,
                     matched_evidence=sorted(known)[:3])

    significant = st - GENERIC_TOKENS
    if not significant:
        return Claim(text, None, ClaimClass.NON_FACTUAL, "no evidentiary content", st)

    # Commentary about the employer, the role, or the candidate's interest
    # contains no candidate-specific fact (spec section 10, step 2). Guarded by
    # "no evidenced term present" so a real claim that merely names the company
    # is still validated normally.
    if not (significant & support) and significant <= (
        _INTENT_TOKENS | job_terms | BENIGN_QUALIFIERS
    ):
        return Claim(text, None, ClaimClass.NON_FACTUAL,
                     "commentary or intent about the employer/role, not a "
                     "candidate-specific assertion", st,
                     severity=ClaimSeverity.INFORMATIONAL)

    # --- strengthened collaboration / counterparties ---------------------
    named = {normalize_title(m.group(0)) for m in SPECIFIC_ROLES_RE.finditer(text)}
    named = {n for n in named if n and n not in _GENERIC_COUNTERPARTIES}
    if named:
        unevidenced = {n for n in named if not _role_evidenced(n, support)}
        if unevidenced:
            return Claim(text, EvidenceCategory.CLIENT,
                         ClaimClass.STRENGTHENED,
                         f"introduces unevidenced counterparties: "
                         f"{sorted(unevidenced)[:4]}", st,
                         severity=ClaimSeverity.HIGH,
                         action="Name only counterparties evidenced in your profile.")

    # --- contact details in generated prose ------------------------------
    if _EMAIL_RE.search(text) or _PHONE_RE.search(text) or _URL_RE.search(text):
        confirmed = set(idx.contacts().values())
        found = set(_EMAIL_RE.findall(text)) | set(_PHONE_RE.findall(text))
        found |= set(_URL_RE.findall(text))
        unconfirmed = {
            f for f in found
            if normalize_text(f) not in {normalize_text(c) for c in confirmed}
        }
        if unconfirmed:
            return Claim(text, EvidenceCategory.CONTACT, ClaimClass.UNSUPPORTED,
                         f"contact detail not on profile: {sorted(unconfirmed)[:3]}",
                         st, severity=ClaimSeverity.CRITICAL,
                         action="Remove invented contact details.")

    # --- scope escalation ------------------------------------------------
    strengthened_terms = _strengthening_terms(significant, support) - job_terms
    if strengthened_terms:
        return Claim(text, EvidenceCategory.RESPONSIBILITY, ClaimClass.STRENGTHENED,
                     f"scope escalations not evidenced: "
                     f"{sorted(strengthened_terms)[:5]}", st,
                     severity=ClaimSeverity.HIGH,
                     action="Soften the wording to match your recorded experience.")

    # --- core support: reason-based triage (V1.2 precision) --------------
    # Instead of a single overlap ratio, classify *why* each token is missing.
    # Benign qualifiers and evidenced paraphrases are accepted; unexplained
    # content splits between hard failure and review depending on what it is.
    missing = significant - support - job_terms
    if not missing:
        return Claim(text, category_hint, ClaimClass.SUPPORTED,
                     "every significant term is present in the evidence", st,
                     severity=ClaimSeverity.INFORMATIONAL,
                     matched_evidence=_best_evidence(text, idx, top=3))

    benign_missing = {t for t in missing if t in BENIGN_QUALIFIERS}
    paraphrased = {t for t in missing if paraphrase_match(t, support)}
    # Intent/commentary vocabulary (interest in the role, fit, aspiration) is
    # not a candidate-specific assertion (spec section 10, step 2), so it is
    # explained away rather than reported as missing evidence.
    unexplained = missing - benign_missing - paraphrased - (missing & _INTENT_TOKENS)

    # An unevidenced technology is an explicit fabrication (spec section 5) and is
    # checked BEFORE the coverage gate so it can never be accepted as paraphrase.
    tech_missing = {t for t in unexplained if t in _KNOWN_TECH_TOKENS}
    if tech_missing:
        return Claim(text, category_hint, ClaimClass.UNSUPPORTED,
                     f"technologies not present in confirmed evidence: "
                     f"{sorted(tech_missing)[:5]}", st,
                     severity=ClaimSeverity.HIGH,
                     matched_evidence=_best_evidence(text, idx, top=2),
                     missing_terms=sorted(unexplained)[:8],
                     action="Remove or replace this technology claim.")

    # Coverage gate (spec section 10, step 5). When the great majority of the
    # significant content is evidenced and nothing unsafe is introduced, the
    # sentence is a paraphrase - accept it rather than sending the reviewer to
    # triage wording. Explicit fabrication signals (technology, intensifier,
    # contact, eligibility, metric) are checked independently below and still
    # hard-fail regardless of coverage.
    coverage = len(significant - missing) / max(1, len(significant))
    if unexplained and coverage >= 0.70:
        return Claim(text, category_hint, ClaimClass.SUPPORTED_BY_NORMALIZATION,
                     f"{coverage:.0%} of the significant wording is evidenced; "
                     f"residual wording {sorted(unexplained)[:4]} reads as "
                     "paraphrase rather than a new fact", st,
                     severity=ClaimSeverity.INFORMATIONAL,
                     matched_evidence=_best_evidence(text, idx, top=3))

    if not unexplained:
        if paraphrased and benign_missing:
            return Claim(text, category_hint, ClaimClass.SUPPORTED_BY_NORMALIZATION,
                         "supported after normalisation: paraphrased wording "
                         f"{sorted(paraphrased)[:3]} and benign qualifiers "
                         f"{sorted(benign_missing)[:3]}", st,
                         severity=ClaimSeverity.INFORMATIONAL,
                         matched_evidence=_best_evidence(text, idx, top=3))
        if paraphrased:
            return Claim(text, category_hint, ClaimClass.SUPPORTED_BY_NORMALIZATION,
                         f"supported after normalisation; paraphrased wording "
                         f"{sorted(paraphrased)[:3]}", st,
                         severity=ClaimSeverity.INFORMATIONAL,
                         matched_evidence=_best_evidence(text, idx, top=3))
        return Claim(text, category_hint, ClaimClass.SUPPORTED_BY_NORMALIZATION,
                     "only decorative professional qualifiers differ from the "
                     f"evidence: {sorted(benign_missing)[:4]}", st,
                     severity=ClaimSeverity.INFORMATIONAL,
                     matched_evidence=_best_evidence(text, idx, top=3))

    # Fabrication is only called when a clear majority of the remaining content
    # is substantive and unexplained. Anything weaker is genuine ambiguity and
    # must route to review rather than be asserted as fabrication.
    entity_missing = {t for t in unexplained if _looks_entityish(t, text)}
    threshold = max(2, (len(unexplained) * 3) // 5)
    if entity_missing and len(entity_missing) >= threshold:
        return Claim(text, category_hint, ClaimClass.UNSUPPORTED,
                     f"specific terms absent from evidence: {sorted(entity_missing)[:5]}",
                     st, severity=ClaimSeverity.HIGH,
                     matched_evidence=_best_evidence(text, idx, top=2),
                     missing_terms=sorted(unexplained)[:8],
                     action="Remove or replace this claim.")

    # Otherwise the statement is candidate-specific but cannot be mapped safely.
    return Claim(text, category_hint, ClaimClass.PLAUSIBLE_BUT_UNVERIFIED,
                 f"candidate-specific wording not found verbatim in evidence: "
                 f"{sorted(unexplained)[:5]}", st,
                 severity=ClaimSeverity.LOW,
                 matched_evidence=_best_evidence(text, idx, top=2),
                 missing_terms=sorted(unexplained)[:8],
                 action="Review wording against the source evidence.")


_KNOWN_TECH_TOKENS = frozenset({
    "catboost", "lightgbm", "xgboost", "pytorch", "tensorflow", "sklearn",
    "scikit", "spark", "kubernetes", "docker", "terraform", "aws", "azure",
    "gcp", "airflow", "mlflow", "kubeflow", "dask", "ray", "hadoop", "scala",
    "kafka", "postgres", "mysql", "mongodb", "redis", "elasticsearch",
    "tableau", "looker", "qlik", "powerbi", "excel", "spss", "r", "matlab",
    "java", "golang", "rust", "typescript", "react", "node", "flask", "django",
})


def _looks_entityish(token: str, original_text: str = "") -> bool:
    """True only for tokens denoting a *specific* thing.

    Specific entities (a named technology, a product, a counterparty role, or a
    proper noun) that are absent from evidence support a fabrication call.
    Abstract nouns ("roadmap", "infrastructure", "platform") do not - they are
    ambiguity and belong in review, per spec section 8.
    """
    if token in BENIGN_QUALIFIERS or token in FUNCTION_TOKENS:
        return False
    if token in ACTION_VERBS or token in INTERACTION_VERBS:
        return False
    if _PARAPHRASE_INDEX.get(token):
        return False
    if token in _KNOWN_TECH_TOKENS:
        return True
    if normalize_title(token) in _GENERIC_COUNTERPARTIES:
        return False
    # Proper noun (capitalised) inside the original sentence.
    if original_text and token in {
        normalize_text(w) for w in re.findall(r"\b[A-Z][A-Za-z]{2,}\b", original_text)
    }:
        return True
    return False


def _best_evidence(text: str, idx: EvidenceIndex, top: int = 3) -> list[str]:
    """Return short evidence labels that best cover a claim, for traceability."""
    claim_tokens = tokens(text) - GENERIC_TOKENS
    if not claim_tokens:
        return []
    scored: list[tuple[int, str]] = []
    for item in idx.items:
        overlap = len(claim_tokens & item.support)
        if overlap:
            scored.append((overlap, item.label or item.text[:60]))
    scored.sort(key=lambda pair: -pair[0])
    return [label for _, label in scored[:top]]


# Words that intensify scope beyond the evidenced base verb.
_INTENSIFIERS = frozenset({
    # frequency / scope escalation
    "routinely", "consistently", "frequently", "extensively", "significantly",
    "substantially", "largely", "heavily", "widely", "always", "never",
    "advanced", "expert", "expertise", "deep", "proficient", "specialist",
    "production", "large", "heterogeneous", "massive", "complex", "real-time",
    "high", "designed", "executed", "architected", "owned", "spearheaded",
    "directed", "reliable", "ensured", "guaranteed", "fully", "entirely",
    # seniority / audience escalation (spec section 5)
    "leadership", "senior", "executive", "board", "executives",
    "authoritative", "strategic", "organisation", "organization",
    "global", "international",
    # ongoing-ownership escalation: "built" -> "built and maintained"
    "maintaining", "tracking", "monitoring", "overseeing", "oversaw",
    "owning", "responsible", "accountable", "solely", "single-handedly",
    # outcome verbs that assert effect the evidence does not establish
    "sharpened", "sharpen", "monitor", "spot", "spotted",
    "improved", "improvement", "strengthened", "strengthen", "raised",
    "increased", "decreased", "boosted", "enhanced", "accelerated",
})


def _role_evidenced(role: str, support: set[str]) -> bool:
    """True when a named counterpart role is already present in the evidence."""
    parts = set(role.split())
    if not parts:
        return True
    return bool(parts & support)


def _strengthening_terms(significant: set[str], support: set[str]) -> set[str]:
    """Return intensifier/escalation tokens that appear but are not evidenced."""
    return {t for t in significant & _INTENSIFIERS if t not in support}


__all__ = [
    "ACTION_VERBS",
    "Claim",
    "ClaimClass",
    "EvidenceCategory",
    "EvidenceIndex",
    "EvidenceItem",
    "GENERIC_TOKENS",
    "build_index",
    "classify_sentence",
]
