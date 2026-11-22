"""The matching engine.

Simple, deterministic and explainable. Every dimension produces both a score
and the line items that justify it, so a user can see *why* a job was scored
the way it was.
"""

from __future__ import annotations

from .config import DEFAULT_SETTINGS, MatchSettings
from .normalize import (
    degree_level,
    education_is_open_ended,
    location_tokens,
    normalise,
    remote_class,
    seniority_of,
    seniority_rank,
    token_overlap,
    tokenise,
)
from .types import (
    EDUCATION,
    EXPERIENCE,
    LOCATION,
    OTHER,
    PREFERRED,
    REQUIRED,
    SKILL,
    UNKNOWN_IMPORTANCE,
    CandidateProfile,
    DimensionScore,
    JobProfile,
    MatchItem,
    MatchOutcome,
    Requirement,
)

_WORK_AUTH_MARKERS = (
    "work authorization",
    "work authorisation",
    "right to work",
    "visa sponsorship",
    "security clearance",
    "citizen",
    "residents",
)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _importance_weight(importance: str) -> float:
    if importance == REQUIRED:
        return 1.0
    if importance == PREFERRED:
        return 0.45
    if importance in ("SOFT_SIGNAL", "INFORMATIONAL"):
        # Aspirational boilerplate ("team player", "self-starter") must not
        # materially penalise a candidate. Shown as an unknown, never a gap.
        return 0.05
    return 0.65


def _skill_names_match(required: str, held: str, settings: MatchSettings) -> tuple[float, bool]:
    """Return (score, is_exact) comparing a required skill against a held skill."""
    canonical_required = settings.canonical_name(required)
    canonical_held = settings.canonical_name(held)
    if normalise(canonical_required) == normalise(canonical_held):
        return 1.0, True
    overlap = token_overlap(canonical_required, canonical_held)
    if overlap >= 0.99:
        # Require similar token set sizes to treat as exact match.
        # This avoids "machine learning" matching "machine learning engineering" as exact.
        ta = tokenise(canonical_required)
        tb = tokenise(canonical_held)
        if ta and tb:
            ratio = len(ta & tb) / max(len(ta), len(tb))
            if ratio >= 0.7:
                return 1.0, True
        return overlap * settings.partial_skill_credit, False
    if overlap > 0:
        return overlap * settings.partial_skill_credit, False
    return 0.0, False


class MatchingEngine:
    """Scores a candidate profile against a job profile."""

    def __init__(self, settings: MatchSettings | None = None) -> None:
        self.settings = settings or DEFAULT_SETTINGS

    # ------------------------------------------------------------------ public

    def match(
        self, candidate: CandidateProfile, job: JobProfile
    ) -> tuple[MatchOutcome, dict[str, DimensionScore]]:
        matched: list[MatchItem] = []
        gaps: list[MatchItem] = []
        blockers: list[MatchItem] = []
        unknowns: list[MatchItem] = []

        technical = self._score_technical(candidate, job, matched, gaps, unknowns)
        experience = self._score_experience(candidate, job, matched, gaps, unknowns)
        education = self._score_education(candidate, job, matched, gaps, blockers, unknowns)
        location = self._score_location(candidate, job, matched, gaps, blockers, unknowns)
        other = self._score_other(candidate, job, matched, gaps, blockers, unknowns)

        weights = self.settings.weights.normalised()
        overall = _clamp(
            technical.score * weights.technical
            + experience.score * weights.experience
            + education.score * weights.education
            + location.score * weights.location
            + other.score * weights.other
        )

        confidence = self._confidence(candidate, job, (technical, experience, education, location, other))
        recommendation = self.settings.policy.decide(overall, bool(blockers))
        explanation = self._explain(
            job, overall, recommendation, technical, experience, education, location, other, blockers
        )

        outcome = MatchOutcome(
            technical_score=technical.score,
            experience_score=experience.score,
            education_score=education.score,
            location_score=location.score,
            other_score=other.score,
            overall_score=overall,
            recommendation=recommendation,
            confidence=confidence,
            matched=matched,
            gaps=gaps,
            blockers=blockers,
            unknowns=unknowns,
            explanation=explanation,
        )
        dimensions = {
            "technical": technical,
            "experience": experience,
            "education": education,
            "location": location,
            "other": other,
        }
        return outcome, dimensions

    # ------------------------------------------------------------------ skills

    def _score_technical(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        matched: list[MatchItem],
        gaps: list[MatchItem],
        unknowns: list[MatchItem],
    ) -> DimensionScore:
        skill_reqs = [r for r in job.requirements if r.type == SKILL]
        if not skill_reqs:
            return DimensionScore(
                name="technical",
                score=self.settings.unknown_requirement_score,
                notes=["No skill requirements were extracted for this job."],
            )

        if not candidate.skills:
            unknowns.append(
                MatchItem(
                    category=SKILL,
                    name="Candidate skill inventory",
                    detail="No skills confirmed on the career profile yet.",
                    importance=UNKNOWN_IMPORTANCE,
                )
            )
            return DimensionScore(name="technical", score=0.0, notes=["Candidate has no recorded skills."])

        total_weight = 0.0
        earned = 0.0
        for req in skill_reqs:
            weight = _importance_weight(req.importance)
            total_weight += weight
            best_score, best_name = 0.0, ""
            for held in candidate.skills:
                score, _exact = _skill_names_match(req.name, held.name, self.settings)
                if score > best_score:
                    best_score, best_name = score, held.name

            if best_score >= 0.999:
                earned += weight
                matched.append(
                    MatchItem(
                        category=SKILL,
                        name=req.name,
                        detail=(
                            f"Matches confirmed skill '{best_name}'."
                            if best_name.lower() != req.name.lower()
                            else "Confirmed on your profile."
                        ),
                        importance=req.importance,
                    )
                )
            elif best_score > 0:
                # Partial overlap: credited but never presented as a full match.
                earned += weight * best_score
                gaps.append(
                    MatchItem(
                        category=SKILL,
                        name=req.name,
                        detail=f"Partial overlap with '{best_name}'. Not a confirmed match.",
                        importance=req.importance,
                    )
                )
            elif req.importance == REQUIRED:
                gaps.append(
                    MatchItem(
                        category=SKILL,
                        name=req.name,
                        detail="Required, but not present on your confirmed profile.",
                        importance=req.importance,
                    )
                )
            else:
                unknowns.append(
                    MatchItem(
                        category=SKILL,
                        name=req.name,
                        detail=(
                            f"{req.importance.title()} skill. You have not confirmed it — "
                            "add it if your experience genuinely covers it."
                        ),
                        importance=req.importance,
                    )
                )

        score = _clamp(100.0 * earned / total_weight) if total_weight else 0.0
        return DimensionScore(name="technical", score=score)

    # -------------------------------------------------------------- experience

    def _score_experience(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        matched: list[MatchItem],
        gaps: list[MatchItem],
        unknowns: list[MatchItem],
    ) -> DimensionScore:
        exp_reqs = [r for r in job.requirements if r.type == EXPERIENCE]
        candidate_years = candidate.years_of_experience
        if candidate_years is None and candidate.experience:
            candidate_years = self._estimate_years(candidate)

        title_score = self._title_similarity(candidate, job)
        years_score: float | None = None

        for req in exp_reqs:
            if req.years_required is not None and candidate_years is not None:
                ratio = candidate_years / req.years_required if req.years_required > 0 else 1.0
                years_score = _clamp(ratio * 100.0)
                if ratio >= 1.0:
                    matched.append(
                        MatchItem(
                            category=EXPERIENCE,
                            name=req.name or "Experience duration",
                            detail=(
                                f"You have ~{candidate_years:g} years; "
                                f"{req.years_required:g}+ requested."
                            ),
                            importance=req.importance,
                        )
                    )
                else:
                    gaps.append(
                        MatchItem(
                            category=EXPERIENCE,
                            name=req.name or "Experience duration",
                            detail=(
                                f"You have ~{candidate_years:g} years; "
                                f"{req.years_required:g}+ requested."
                            ),
                            importance=req.importance,
                        )
                    )
            elif req.years_required is not None and candidate_years is None:
                unknowns.append(
                    MatchItem(
                        category=EXPERIENCE,
                        name=req.name or "Experience duration",
                        detail=f"{req.years_required:g}+ years requested; your total is unknown.",
                        importance=req.importance,
                    )
                )
            elif req.years_required is None:
                # An experience requirement that states no duration cannot be
                # scored numerically. It must still be reported: previously it
                # appeared in no list at all, so an extracted requirement was
                # invisible to the user and to the strategy layer. Absence of a
                # duration is an evidence boundary, not a satisfied requirement.
                unknowns.append(
                    MatchItem(
                        category=EXPERIENCE,
                        name=req.name or "Experience requirement",
                        detail=(
                            "This requirement states no specific duration, so it "
                            "cannot be scored numerically. It is not established "
                            "in your recorded evidence and is not treated as met."
                        ),
                        importance=req.importance,
                    )
                )

        if not exp_reqs and candidate_years is None:
            unknowns.append(
                MatchItem(
                    category=EXPERIENCE,
                    name="Total years of experience",
                    detail="Not recorded on your profile and not stated by the job.",
                    importance=UNKNOWN_IMPORTANCE,
                )
            )

        title_component = 50.0 + title_score * 50.0
        if years_score is not None:
            score = _clamp(title_component * 0.5 + years_score * 0.5)
        elif candidate_years is not None:
            # No duration requirement: neutral, slight credit for documented tenure.
            score = _clamp(title_component * 0.8 + 20.0 * 0.2)
        else:
            score = _clamp(title_component * 0.8)

        return DimensionScore(name="experience", score=score)

    def _title_similarity(self, candidate: CandidateProfile, job: JobProfile) -> float:
        if not job.title:
            return 0.0
        targets = [job.title, *candidate.preferred_roles]
        if candidate.professional_title:
            targets.append(candidate.professional_title)
        held_titles = [e.title for e in candidate.experience if e.title]

        best = 0.0
        for target in targets:
            best = max(best, token_overlap(target, job.title))
            for held in held_titles:
                best = max(best, token_overlap(target, held))

        settings = self.settings
        job_level = seniority_of(job.title)
        if job_level and held_titles:
            candidate_levels = [seniority_of(t) for t in held_titles]
            candidate_levels.append(seniority_of(candidate.professional_title))
            job_rank = seniority_rank(job_level, settings.seniority_levels)
            candidate_ranks = [
                r
                for r in (seniority_rank(lvl, settings.seniority_levels) for lvl in candidate_levels)
                if r is not None
            ]
            if job_rank is not None and candidate_ranks:
                delta = max(candidate_ranks) - job_rank
                level_score = _clamp(100.0 - max(0.0, delta) * 22.0 - max(0.0, -delta) * 10.0)
                best = max(best, level_score / 100.0)

        settings_floor = settings.title_similarity_partial
        if best < settings_floor:
            return 0.0
        if best >= settings.title_similarity_match:
            return 1.0
        span = settings.title_similarity_match - settings_floor
        return _clamp((best - settings_floor) / span) if span > 0 else 0.0

    @staticmethod
    def _estimate_years(candidate: CandidateProfile) -> float | None:
        """Rough tenure estimate from recorded experience (first start -> today)."""
        from datetime import date

        years: list[int] = []
        for exp in candidate.experience:
            start = _parse_year(exp.start_date)
            if start is None:
                continue
            end = _parse_year(exp.end_date) if not exp.is_current else date.today().year
            years.append(max(0, (end or start) - start))
        return float(sum(years)) if years else None

    # --------------------------------------------------------------- education

    def _score_education(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        matched: list[MatchItem],
        gaps: list[MatchItem],
        blockers: list[MatchItem],
        unknowns: list[MatchItem],
    ) -> DimensionScore:
        edu_reqs = [r for r in job.requirements if r.type == EDUCATION]
        if not edu_reqs:
            return DimensionScore(
                name="education",
                score=self.settings.unknown_requirement_score,
                notes=["No education requirements were extracted."],
            )

        if not candidate.education:
            unknowns.append(
                MatchItem(
                    category=EDUCATION,
                    name="Your education",
                    detail="No education recorded on your profile.",
                    importance=UNKNOWN_IMPORTANCE,
                )
            )
            for req in edu_reqs:
                if req.importance == REQUIRED:
                    unknowns.append(
                        MatchItem(
                            category=EDUCATION,
                            name=req.name,
                            detail="Required by the job, but your education is not recorded.",
                            importance=req.importance,
                        )
                    )
            return DimensionScore(name="education", score=self.settings.unknown_requirement_score)

        candidate_levels = [
            level
            for level in (degree_level(f"{e.degree} {e.field}") for e in candidate.education)
            if level is not None
        ]
        max_level = max(candidate_levels) if candidate_levels else None

        weighted_total = 0.0
        earned = 0.0
        for req in edu_reqs:
            weight = _importance_weight(req.importance)
            weighted_total += weight
            text = f"{req.name} {req.description}"
            if education_is_open_ended(text) or not degree_level(text):
                earned += weight * 0.9
                unknowns.append(
                    MatchItem(
                        category=EDUCATION,
                        name=req.name or "Education",
                        detail="Requirement is not specific enough to verify automatically.",
                        importance=req.importance,
                    )
                )
                continue

            required_level = degree_level(text)
            if required_level is None or max_level is None:
                earned += weight * 0.6
                unknowns.append(
                    MatchItem(
                        category=EDUCATION,
                        name=req.name or "Education",
                        detail="Could not determine your degree level.",
                        importance=req.importance,
                    )
                )
                continue

            if max_level >= required_level:
                earned += weight
                matched.append(
                    MatchItem(
                        category=EDUCATION,
                        name=req.name or "Education",
                        detail="Your recorded education meets this requirement.",
                        importance=req.importance,
                    )
                )
            else:
                if req.importance == REQUIRED:
                    blockers.append(
                        MatchItem(
                            category=EDUCATION,
                            name=req.name or "Education",
                            detail="Required degree level is above your highest recorded level.",
                            importance=req.importance,
                        )
                    )
                    gaps.append(
                        MatchItem(
                            category=EDUCATION,
                            name=req.name or "Education",
                            detail="Not met by your recorded education.",
                            importance=req.importance,
                        )
                    )
                else:
                    gaps.append(
                        MatchItem(
                            category=EDUCATION,
                            name=req.name or "Education",
                            detail="Preferred requirement not met by your recorded education.",
                            importance=req.importance,
                        )
                    )

        score = _clamp(100.0 * earned / weighted_total) if weighted_total else 0.0
        return DimensionScore(name="education", score=score)

    # ---------------------------------------------------------------- location

    def _score_location(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        matched: list[MatchItem],
        gaps: list[MatchItem],
        blockers: list[MatchItem],
        unknowns: list[MatchItem],
    ) -> DimensionScore:
        job_remote = remote_class(job.remote_status)
        candidate_pref = remote_class(candidate.remote_preference) if candidate.remote_preference else "UNKNOWN"
        if candidate.remote_preference and normalise(candidate.remote_preference) == "any":
            candidate_pref = "ANY"

        score: float | None = None

        if job_remote == "UNKNOWN":
            unknowns.append(
                MatchItem(
                    category=LOCATION,
                    name="Work mode",
                    detail="The job does not state whether it is remote, hybrid or on-site.",
                    importance=UNKNOWN_IMPORTANCE,
                )
            )
            score = 70.0
        else:
            if job_remote == "REMOTE":
                if candidate_pref in {"REMOTE", "ANY", "UNKNOWN"}:
                    matched.append(
                        MatchItem(
                            category=LOCATION,
                            name="Remote work",
                            detail="Fully remote role; matches your preference.",
                            importance=UNKNOWN_IMPORTANCE,
                        )
                    )
                    score = 100.0
                else:
                    gaps.append(
                        MatchItem(
                            category=LOCATION,
                            name="Remote work",
                            detail="Role is remote but you prefer on-site/hybrid.",
                            importance=PREFERRED,
                        )
                    )
                    score = 70.0
            elif job_remote == "ONSITE":
                if candidate_pref == "REMOTE":
                    gaps.append(
                        MatchItem(
                            category=LOCATION,
                            name="On-site requirement",
                            detail="Role is on-site and you prefer fully remote.",
                            importance=REQUIRED,
                        )
                    )
                    score = 35.0
                elif candidate_pref == "HYBRID":
                    gaps.append(
                        MatchItem(
                            category=LOCATION,
                            name="On-site requirement",
                            detail="Role is on-site; you prefer hybrid.",
                            importance=REQUIRED,
                        )
                    )
                    score = 55.0
                else:
                    score = 85.0

        if job.location and candidate.location:
            job_tokens = location_tokens(job.location)
            cand_tokens = location_tokens(candidate.location)
            if job_tokens & cand_tokens:
                matched.append(
                    MatchItem(
                        category=LOCATION,
                        name="Location",
                        detail=f"'{job.location}' overlaps with your location '{candidate.location}'.",
                        importance=UNKNOWN_IMPORTANCE,
                    )
                )
                # Only boost score for location overlap if there is no severe
                # remote-preference conflict (e.g. candidate wants REMOTE, job is ONSITE).
                severe_conflict = (
                    job_remote == "ONSITE" and candidate_pref == "REMOTE"
                )
                if not severe_conflict:
                    score = max(score or 0.0, 95.0) if score is not None else 95.0
            elif job_remote == "REMOTE":
                pass  # A remote role is not blocked by location.
            else:
                blocked = self._is_hard_location_block(candidate, job)
                item = MatchItem(
                    category=LOCATION,
                    name="Location",
                    detail=f"Job is in '{job.location}'; you are in '{candidate.location}'.",
                    importance=REQUIRED if blocked else PREFERRED,
                )
                if blocked:
                    blockers.append(item)
                    gaps.append(item)
                    score = min(score if score is not None else 100.0, 20.0)
                else:
                    gaps.append(item)
                    score = min(score if score is not None else 100.0, 55.0)

        preferred_hit = False
        for pref in candidate.preferred_locations:
            if pref and token_overlap(pref, job.location) >= 0.99:
                preferred_hit = True
                break
        if preferred_hit:
            matched.append(
                MatchItem(
                    category=LOCATION,
                    name="Preferred location",
                    detail=f"'{job.location}' is one of your preferred locations.",
                    importance=UNKNOWN_IMPORTANCE,
                )
            )
            severe_conflict = (
                job_remote == "ONSITE" and candidate_pref == "REMOTE"
            )
            if not severe_conflict:
                score = max(score or 0.0, 98.0)

        if score is None:
            unknowns.append(
                MatchItem(
                    category=LOCATION,
                    name="Location",
                    detail="Neither location is stated, so this could not be assessed.",
                    importance=UNKNOWN_IMPORTANCE,
                )
            )
            score = 65.0

        for req in (r for r in job.requirements if r.type == LOCATION):
            lowered = normalise(f"{req.name} {req.description}")
            if not lowered:
                continue
            if any(marker in lowered for marker in _WORK_AUTH_MARKERS):
                # Work authorisation needs candidate data the profile does not model yet.
                unknowns.append(
                    MatchItem(
                        category=OTHER,
                        name=req.name or "Work authorisation",
                        detail=(
                            "The job states a work-authorisation condition. "
                            "Your profile does not record this yet — verify manually."
                        ),
                        importance=req.importance,
                    )
                )

        return DimensionScore(name="location", score=score)

    @staticmethod
    def _is_hard_location_block(candidate: CandidateProfile, job: JobProfile) -> bool:
        for req in (r for r in job.requirements if r.type == LOCATION):
            if req.importance != REQUIRED:
                continue
            text = normalise(f"{req.name} {req.description}")
            if "must" in text or "required" in text or "based in" in text or "relocat" in text:
                return True
        return False

    # ------------------------------------------------------------------- other

    def _score_other(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        matched: list[MatchItem],
        gaps: list[MatchItem],
        blockers: list[MatchItem],
        unknowns: list[MatchItem],
    ) -> DimensionScore:
        other_reqs = [r for r in job.requirements if r.type == OTHER]
        components: list[tuple[float, float]] = []

        if job.salary_min and candidate.minimum_salary:
            if job.salary_max and job.salary_max < candidate.minimum_salary:
                gaps.append(
                    MatchItem(
                        category=OTHER,
                        name="Salary",
                        detail=(
                            f"Role tops out below your minimum of "
                            f"{candidate.minimum_salary:,.0f}."
                        ),
                        importance=REQUIRED,
                    )
                )
                components.append((15.0, 1.0))
            else:
                matched.append(
                    MatchItem(
                        category=OTHER,
                        name="Salary",
                        detail=(
                            f"Posted range {job.salary_min:,.0f}-{job.salary_max or 0:,.0f} "
                            "meets your minimum."
                        ),
                        importance=UNKNOWN_IMPORTANCE,
                    )
                )
                components.append((100.0, 1.0))
        elif job.salary_min or job.salary_max:
            unknowns.append(
                MatchItem(
                    category=OTHER,
                    name="Salary",
                    detail="A range is posted but your minimum is not set.",
                    importance=UNKNOWN_IMPORTANCE,
                )
            )
            components.append((70.0, 0.7))
        else:
            unknowns.append(
                MatchItem(
                    category=OTHER,
                    name="Salary",
                    detail="Salary not stated.",
                    importance=UNKNOWN_IMPORTANCE,
                )
            )
            components.append((70.0, 0.4))

        if job.employment_type and candidate.preferred_roles:
            for req in other_reqs:
                if "employment type" in normalise(req.name):
                    if token_overlap(req.description, job.employment_type) >= 0.99:
                        matched.append(
                            MatchItem(
                                category=OTHER,
                                name="Employment type",
                                detail=f"Role is {job.employment_type}.",
                                importance=req.importance,
                            )
                        )

        if other_reqs:
            for req in other_reqs:
                text = normalise(f"{req.name} {req.description}")
                if not text or "employment type" in normalise(req.name):
                    continue
                if req.importance == REQUIRED:
                    gaps.append(
                        MatchItem(
                            category=OTHER,
                            name=req.name,
                            detail="Additional requirement that the profile cannot verify.",
                            importance=req.importance,
                        )
                    )
                    components.append((40.0, _importance_weight(req.importance)))
                else:
                    unknowns.append(
                        MatchItem(
                            category=OTHER,
                            name=req.name,
                            detail=req.description or "Additional requirement.",
                            importance=req.importance,
                        )
                    )
                    components.append((75.0, _importance_weight(req.importance)))
        else:
            components.append((70.0, 0.3))

        total_weight = sum(w for _, w in components)
        if total_weight <= 0:
            return DimensionScore(name="other", score=70.0)
        score = _clamp(sum(s * w for s, w in components) / total_weight)
        return DimensionScore(name="other", score=score)

    # ------------------------------------------------------------- confidence

    def _confidence(
        self,
        candidate: CandidateProfile,
        job: JobProfile,
        dimensions: tuple[DimensionScore, ...],
    ) -> float:
        checks = 0.0
        if candidate.skills:
            checks += 0.3
        if candidate.experience:
            checks += 0.25
        if candidate.education:
            checks += 0.15
        if candidate.location:
            checks += 0.1
        if candidate.years_of_experience is not None:
            checks += 0.1
        if job.requirements:
            checks += 0.1

        unknown_penalty = sum(1 for d in dimensions if not d.notes) * 0.0
        for dimension in dimensions:
            if dimension.notes and "not extracted" in " ".join(dimension.notes).lower():
                unknown_penalty += 0.05

        raw = _clamp(checks - unknown_penalty, 0.0, 1.0)
        settings = self.settings
        return round(
            _clamp(
                settings.confidence_floor + raw * (settings.confidence_ceiling - settings.confidence_floor)
            ),
            3,
        )

    # ------------------------------------------------------------ explanation

    @staticmethod
    def _explain(
        job: JobProfile,
        overall: float,
        recommendation: str,
        technical: DimensionScore,
        experience: DimensionScore,
        education: DimensionScore,
        location: DimensionScore,
        other: DimensionScore,
        blockers: list[MatchItem],
    ) -> str:
        header = (
            f"{job.title or 'This role'} at {job.company or 'the company'} "
            f"scores {overall:.0f}/100 overall, which maps to {recommendation}."
        )
        if blockers:
            names = ", ".join(b.name for b in blockers)
            return (
                f"{header} A hard blocker is present ({names}), so the recommendation is SKIP "
                "regardless of the numeric score. Review the blockers below."
            )

        lines = [header]
        ranked = sorted(
            (
                (technical, 40),
                (experience, 25),
                (location, 10),
                (education, 10),
                (other, 15),
            ),
            key=lambda pair: -pair[0].score,
        )
        strongest = [d for d, _ in ranked[:2] if d.score == ranked[0][0].score]
        if len(strongest) > 1:
            names = " and ".join(d.name.capitalize() for d in strongest)
            lines.append(
                f"Strongest dimensions are {names} at {ranked[0][0].score:.0f}/100."
            )
        else:
            lines.append(
                f"Strongest dimension is {ranked[0][0].name.capitalize()} "
                f"at {ranked[0][0].score:.0f}/100."
            )
        weakest = ranked[-1]
        lines.append(
            f"Weakest dimension is {weakest[0].name.capitalize()} at {weakest[0].score:.0f}/100."
        )
        return " ".join(lines)


def _parse_year(value: str) -> int | None:
    import re

    match = re.search(r"(19|20)\d{2}", value or "")
    return int(match.group(0)) if match else None


def match_candidate_to_job(
    candidate: CandidateProfile,
    job: JobProfile,
    settings: MatchSettings | None = None,
) -> MatchOutcome:
    """Convenience wrapper returning only the outcome."""
    outcome, _ = MatchingEngine(settings).match(candidate, job)
    return outcome


__all__ = [
    "MatchingEngine",
    "match_candidate_to_job",
    "MatchOutcome",
    "DimensionScore",
    "MatchItem",
    "CandidateProfile",
    "JobProfile",
    "Requirement",
    "SKILL",
    "EXPERIENCE",
    "EDUCATION",
    "LOCATION",
    "OTHER",
    "REQUIRED",
    "PREFERRED",
    "UNKNOWN_IMPORTANCE",
]
