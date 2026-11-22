"""Tunable matching configuration.

All weights, thresholds and alias rules live here so no score constant is
scattered through the codebase. Values may be overridden from application
settings (see ``apps/api/app/core/config.py``).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

Recommendation = Literal["APPLY", "APPLY_WITH_TAILORING", "STRETCH", "SKIP"]

RECOMMENDATION_ORDER: list[str] = ["APPLY", "APPLY_WITH_TAILORING", "STRETCH", "SKIP"]

# Canonical skill vocabulary. Keys are canonical names, values map lowercase
# surface variants (and aliases) onto the canonical name.
DEFAULT_SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "Python": ("python", "python3", "py"),
    "SQL": ("sql", "sql queries", "ansi sql", "t-sql"),
    "PostgreSQL": ("postgresql", "postgres", "psql", "pg"),
    "MySQL": ("mysql", "mariadb"),
    "MongoDB": ("mongodb", "mongo"),
    "FastAPI": ("fastapi", "fast api"),
    "Django": ("django",),
    "Flask": ("flask",),
    "React": ("react", "react.js", "reactjs"),
    "TypeScript": ("typescript", "ts"),
    "JavaScript": ("javascript", "js", "ecmascript"),
    "Docker": ("docker", "dockerfile"),
    "Kubernetes": ("kubernetes", "k8s"),
    "Terraform": ("terraform", "iac", "infrastructure as code"),
    "AWS": ("aws", "amazon web services", "ec2", "s3", "lambda"),
    "Azure": ("azure", "microsoft azure"),
    "GCP": ("gcp", "google cloud", "google cloud platform"),
    "Spark": ("spark", "apache spark", "pyspark", "databricks"),
    "Airflow": ("airflow", "apache airflow"),
    "Machine Learning": ("machine learning", "ml", "machine-learning"),
    "Deep Learning": ("deep learning", "neural networks", "dl"),
    "Statistics": ("statistics", "statistical analysis", "stats", "biostatistics"),
    "Data Science": ("data science", "data scientist", "data analytics"),
    "Machine Learning Engineering": (
        "machine learning engineering",
        "ml engineering",
        "mlops",
        "ml ops",
        "model deployment",
        "model serving",
    ),
    "Artificial Intelligence": ("artificial intelligence", "ai"),
    "Natural Language Processing": ("natural language processing", "nlp"),
    "Computer Vision": ("computer vision", "cv"),
    "Model Evaluation": (
        "model evaluation",
        "model validation",
        "offline evaluation",
        "evals",
        "a/b testing",
    ),
    "A/B Testing": ("a/b testing", "ab testing", "experimentation", "split testing"),
    "Data Engineering": ("data engineering", "etl", "elt", "data pipelines"),
    "Pandas": ("pandas",),
    "NumPy": ("numpy",),
    "scikit-learn": ("scikit-learn", "sklearn", "scikit learn"),
    "PyTorch": ("pytorch", "torch"),
    "TensorFlow": ("tensorflow", "keras", "tf"),
    "Power BI": ("power bi", "powerbi"),
    "Tableau": ("tableau",),
    "Excel": ("excel", "microsoft excel", "advanced excel"),
    "Git": ("git", "github", "gitlab", "version control"),
    "CI/CD": ("ci/cd", "cicd", "continuous integration", "continuous delivery"),
    "Linux": ("linux", "unix"),
    "Data Modelling": ("data modeling", "data modelling", "dimensional modeling"),
    "Communication": ("communication", "stakeholder management", "presenting"),
    "Leadership": ("leadership", "mentoring", "team lead"),
    "Domain Modelling": ("domain modeling", "domain-driven design", "ddd"),
}


@dataclass(frozen=True)
class MatchWeights:
    """Relative contribution of each dimension to the overall score."""

    technical: float = 0.40
    experience: float = 0.25
    education: float = 0.10
    location: float = 0.10
    other: float = 0.15

    def normalised(self) -> MatchWeights:
        total = (
            self.technical
            + self.experience
            + self.education
            + self.location
            + self.other
        )
        if total <= 0:
            raise ValueError("Match weights must sum to a positive value")
        return replace(
            self,
            technical=self.technical / total,
            experience=self.experience / total,
            education=self.education / total,
            location=self.location / total,
            other=self.other / total,
        )


@dataclass(frozen=True)
class RecommendationPolicy:
    """Decision policy mapping an overall score onto a recommendation."""

    apply_threshold: float = 80.0
    apply_with_tailoring_threshold: float = 65.0
    stretch_threshold: float = 50.0

    def decide(self, overall_score: float, has_blocker: bool) -> str:
        if has_blocker:
            return "SKIP"
        if overall_score >= self.apply_threshold:
            return "APPLY"
        if overall_score >= self.apply_with_tailoring_threshold:
            return "APPLY_WITH_TAILORING"
        if overall_score >= self.stretch_threshold:
            return "STRETCH"
        return "SKIP"


@dataclass(frozen=True)
class MatchSettings:
    """Everything tunable about the matching engine."""

    weights: MatchWeights = field(default_factory=MatchWeights)
    policy: RecommendationPolicy = field(default_factory=RecommendationPolicy)
    skill_aliases: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(DEFAULT_SKILL_ALIASES)
    )
    # How much a partial (token overlap) skill match is credited.
    partial_skill_credit: float = 0.7
    # Similarity at/above which two free-text role titles count as a match.
    title_similarity_match: float = 0.60
    title_similarity_partial: float = 0.35
    # Score granted for a dimension whose job-side requirement is unknown.
    unknown_requirement_score: float = 70.0
    # Confidence floor/ceiling derived from profile completeness.
    confidence_floor: float = 0.35
    confidence_ceiling: float = 0.95
    # Roles considered "senior" for level matching purposes.
    seniority_levels: tuple[str, ...] = (
        "intern",
        "junior",
        "associate",
        "mid",
        "intermediate",
        "senior",
        "staff",
        "principal",
        "lead",
        "head",
        "director",
    )

    def canonical_name(self, raw: str) -> str:
        """Return the canonical skill name for a raw string, else the clean raw value."""
        cleaned = raw.strip()
        if not cleaned:
            return ""
        key = cleaned.lower()
        for canonical, aliases in self.skill_aliases.items():
            if canonical.lower() == key:
                return canonical
            if key in {a.lower() for a in aliases}:
                return canonical
        return cleaned


DEFAULT_SETTINGS = MatchSettings(weights=MatchWeights().normalised())
