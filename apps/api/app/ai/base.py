"""AI provider interface.

Business logic depends only on :class:`AIProvider`. Implementations must return
Pydantic-validated models; raw model text is never handed to callers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.schemas import (
    CVAnalysis,
    ExtractedCV,
    ExtractedJobRequirements,
    ProfileSummary,
    StrategyContext,
    StrategyNarrative,
    TailoredCVContent,
)


class AIProviderError(RuntimeError):
    """Raised when a provider cannot produce valid structured output."""


class AIProvider(ABC):
    """The complete set of AI capabilities the product needs."""

    name: str = "abstract"

    @abstractmethod
    def extract_cv(self, cv_text: str) -> ExtractedCV:
        """Extract structured career information from raw CV text."""

    @abstractmethod
    def extract_job_requirements(self, job_description: str) -> ExtractedJobRequirements:
        """Extract explicit requirements from a job description."""

    @abstractmethod
    def analyze_cv_for_job(
        self,
        profile: ProfileSummary,
        job_description: str,
        job_title: str,
        company: str | None,
    ) -> CVAnalysis:
        """Identify relevant, de-emphasised and missing material for a role."""

    @abstractmethod
    def tailor_cv(
        self,
        profile: ProfileSummary,
        job_description: str,
        job_title: str,
        analysis: CVAnalysis | None = None,
        constraints: str = "",
    ) -> TailoredCVContent:
        """Produce tailored CV content using only confirmed candidate evidence.

        ``constraints`` carries V2 strategy guidance (emphasis and do-not-claim
        lists). It is guidance for generation quality, never a safety control.
        """

    @abstractmethod
    def generate_cover_letter(
        self,
        profile: ProfileSummary,
        job_description: str,
        job_title: str,
        company: str | None,
        constraints: str = "",
    ) -> str:
        """Produce a role-specific cover letter grounded in confirmed evidence."""

    @abstractmethod
    def compose_strategy_narrative(self, context: StrategyContext) -> StrategyNarrative:
        """Write the decision summary for an already-computed strategy (V2).

        The provider receives a fully deterministic analysis and may only
        phrase it. It must not introduce a candidate fact, change the decision,
        or assert eligibility. Every returned sentence is re-validated by
        ``services.strategy.validate_strategy``.
        """


__all__ = ["AIProvider", "AIProviderError"]
