"""Job discovery service.

This service orchestrates the end-to-end job discovery workflow:
1. Search for jobs via external providers (e.g., JSearch)
2. Normalize and persist discovered jobs
3. Extract requirements using the existing extraction pipeline
4. Match against the confirmed candidate profile
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import get_ai_provider
from app.models import Importance, Job, JobRequirement, MatchResult
from app.services import extraction as extraction_service
from app.services.freshness import assess_freshness
from app.services.jsearch import search_jsearch_jobs
from app.services.search_relevance import classify_search_relevance
from app.services.validation import classify_requirement


class JobDiscoveryError(Exception):
    """Base exception for job discovery errors."""

    pass


class JobDiscoveryService:
    """Service for discovering and matching external job vacancies."""

    def __init__(self, db: Session):
        self.db = db

    def discover_jobs(
        self,
        candidate_id: int,
        query: str,
        country: str = "ng",
        location: str | None = None,
        remote_only: bool = False,
        max_results: int = 20,
        cv_profile_id: int | None = None,
    ) -> list[dict]:
        """Discover and match jobs for a candidate.

        Args:
            candidate_id: ID of the candidate
            query: Search query (e.g., "software engineer")
            country: ISO 3166-1 alpha-2 country code (e.g., "ng" for Nigeria)
            location: Optional location filter (city, region)
            remote_only: Only return remote jobs
            max_results: Maximum number of results to return
            cv_profile_id: Match against this confirmed CV profile instead of the
                shared Candidate record. Only the job-search parameters are ever
                sent to the provider; candidate evidence never leaves the system.

        Returns:
            List of discovered jobs with match information
        """
        # Build search query
        search_query = query
        if location:
            search_query = f"{query} in {location}"

        # Remote-only search for Benin uses Remotive's public feed. A city
        # should not be appended to the role keywords for global remote roles.
        jobs = self._search_jobs(
            query=query if country.lower() == "bj" and remote_only else search_query,
            country=country,
            max_results=max_results,
            remote_only=remote_only,
            location=location,
        )

        # Limit results
        jobs = jobs[:max_results]

        # Process each job: normalize, persist, extract, match
        results = []
        seen_external_ids: set[str] = set()
        search_query = query
        if location:
            search_query = f"{query} in {location}"

        for job_data in jobs:
            source = getattr(job_data, "source", "jsearch")
            provider_id = job_data.provider_job_id or ""
            external_id = f"{source}:{provider_id}"
            if external_id in seen_external_ids:
                continue
            seen_external_ids.add(external_id)

            try:
                result = self._process_job(
                    candidate_id, job_data, search_query, country, query, cv_profile_id
                )
                if result:
                    results.append(result)
            except Exception as e:
                # One unpersistable job must not poison the session for the
                # rest: a failed flush leaves the transaction unusable until
                # rollback, so without this every later job in the same
                # request fails too and the whole search returns nothing.
                self.db.rollback()
                # Log error but continue with other jobs
                print(f"Error processing job {provider_id}: {e}")

        return results

    def _search_jobs(self, query: str, country: str, max_results: int = 20,
                     remote_only: bool = False, location: str | None = None) -> list:
        """Search for jobs: JSearch first, Indeed fallback when JSearch is empty.

        Indeed.com covers Benin Republic, which JSearch does not. We only call
        Indeed when JSearch returned nothing, so a populated JSearch result set
        never costs Indeed quota. The Indeed errors are the JSearch error
        subclasses so the /jobs/discover route maps them to proper statuses.
        """
        from app.services.jsearch import JSEARCH_MAX_PAGES, JSEARCH_PAGE_SIZE

        # JSearch doesn't serve Benin. For remote-only roles, search the
        # no-key Remotive source and filter by declared geographic eligibility.
        # This does not claim any result is physically in Benin or that the
        # candidate is legally entitled to accept a position.
        if country.lower() == "bj" and remote_only:
            import asyncio
            from app.services.remotive import search_remotive_jobs

            return asyncio.run(search_remotive_jobs(
                query=query, country=country, max_results=max_results,
                remote_only=True,
            ))

        # Personal-use, keyless API with explicitly permitted non-commercial reuse.
        # Only accept source-confirmed Benin work locations, not remote-only roles.
        # Unlike the older Indeed fallback, there is no paid provider request.
        if country.lower() == "bj" and not remote_only:
            import asyncio
            from app.services.benin_local import search_benin_local_jobs

            return asyncio.run(search_benin_local_jobs(
                query=query.split(" in ")[0] if location else query,
                location=location, max_results=max_results,
            ))

        num_pages = max(1, min(JSEARCH_MAX_PAGES, -(-max(1, max_results) // JSEARCH_PAGE_SIZE)))
        # Use the synchronous version for now
        import asyncio
        jobs = asyncio.run(search_jsearch_jobs(
            query=query,
            country=country,
            num_pages=num_pages,
            remote_only=remote_only,
        ))
        if not jobs:
            from app.services.indeed import search_indeed_jobs

            jobs = asyncio.run(search_indeed_jobs(
                query=query,
                country=country,
                max_results=max_results,
                remote_only=remote_only,
            ))
        return jobs

    def _process_job(self, candidate_id: int, job_data, search_query: str = "", country: str = "ng",
                     query: str = "", cv_profile_id: int | None = None) -> dict | None:
        """Process a single job: persist, extract, match."""
        # Check if job already exists (by provider_job_id)
        existing_job = self._find_existing_job(job_data.provider_job_id, getattr(job_data, "source", "jsearch"))
        if existing_job:
            job = existing_job
        else:
            job = self._create_job_from_jsearch(job_data, search_query, country)
            # Flush to make the job visible to subsequent duplicate checks in the same transaction
            self.db.flush()

        # Extract requirements if not already done
        if not job.requirements_extracted:
            self._extract_and_persist_requirements(job)

        # Match against the selected candidate evidence
        match_result = self._match_job(candidate_id, job, cv_profile_id)

        # Search relevance is computed from the *current* search query (the
        # bare role text, not the location-decorated provider query), never
        # from a query persisted when the job was first discovered.
        relevance = classify_search_relevance(query, job.title)
        freshness = assess_freshness(job.posted_at, job.expires_at)

        # Duplicate review is read-only and advisory: same-external_id rows
        # are the same record and never flag each other.
        from app.services.duplicates import review_job

        duplicate = review_job(job, self.db)

        # Build response
        return {
            "job": self._job_to_dict(job),
            "match": self._match_to_dict(match_result) if match_result else None,
            "search_relevance": {"label": relevance.label, "reason": relevance.reason},
            "freshness": {"status": freshness.status, "reason": freshness.reason},
            "duplicate_review": {
                "status": duplicate.status,
                "reason": duplicate.reason,
                "related_job_ids": list(duplicate.related_job_ids),
            },
        }

    def _find_existing_job(self, provider_job_id: str, source: str = "jsearch") -> Job | None:
        """Match one provider's ID, never collide with another provider's ID."""
        external_id = f"{source}:{provider_job_id}"
        return self.db.execute(
            select(Job).where(Job.external_id == external_id)
        ).scalars().first()

    def _create_job_from_jsearch(self, job_data, search_query: str = "", country: str = "ng") -> Job:
        """Create a Job record from JSearch data."""
        source = getattr(job_data, "source", "jsearch")
        external_id = f"{source}:{job_data.provider_job_id}"

        job = Job(
            title=job_data.title,
            company=job_data.company,
            location=job_data.location,
            url=job_data.apply_url,
            source=source,
            source_id=job_data.provider_job_id,
            external_id=external_id,
            is_discovered=True,
            description=job_data.description,
            employment_type=job_data.employment_type,
            remote_status=job_data.remote_status,
            salary_min=job_data.salary_min,
            salary_max=job_data.salary_max,
            posted_at=job_data.posted_at,
            discovered_at=datetime.now(UTC),
            expires_at=job_data.posted_at + timedelta(days=30) if job_data.posted_at else None,
            search_query={"query": search_query, "country": country},
            requirements_extracted=False,
        )
        self.db.add(job)
        self.db.flush()
        return job

    def _extract_and_persist_requirements(self, job: Job) -> None:
        """Extract requirements and persist them."""
        provider = get_ai_provider()
        result = extraction_service.extract_requirements(
            provider,
            job.description or "",
            model="offline",
        )

        if result.meta.status in ("FAILED", "EMPTY_CONFIRMED"):
            # Check if the failure is due to empty/insufficient description
            # which should be treated as EMPTY_CONFIRMED rather than FAILED
            if result.meta.status == "EMPTY_CONFIRMED" or result.meta.error_code in ("NO_REQUIREMENTS_FOUND", "EMPTY_SOURCE"):
                job.extraction_status = "EMPTY_CONFIRMED"
                job.requirements_extracted = True
                self.db.commit()
                return
            job.extraction_status = "FAILED"
            job.extraction_error_code = result.meta.error_code
            self.db.commit()
            return

        extracted = result.requirements

        # Replace previously extracted requirements
        for existing in list(job.requirements):
            self.db.delete(existing)
        self.db.flush()


        def _imp(name: str, description: str | None, importance: str) -> str:
            return classify_requirement(name, description or "", importance)

        for skill in result.requirements.required_skills:
            self.db.add(JobRequirement(
                job_id=job.id,
                requirement_type="SKILL",
                name=skill,
                description=f"Required: {skill}",
                importance=Importance.REQUIRED.value,
            ))
        for skill in result.requirements.preferred_skills:
            self.db.add(JobRequirement(
                job_id=job.id,
                requirement_type="SKILL",
                name=skill,
                description=f"Preferred: {skill}",
                importance=Importance.PREFERRED.value,
            ))
        for req in result.requirements.experience_requirements:
            self.db.add(JobRequirement(
                job_id=job.id,
                requirement_type="EXPERIENCE",
                name=req.name[:255],
                description=req.description,
                importance=req.importance.value,
                years_required=req.years_required,
            ))
        for req in result.requirements.education_requirements:
            self.db.add(JobRequirement(
                job_id=job.id,
                requirement_type="EDUCATION",
                name=req.name[:255],
                description=req.description,
                importance=req.importance.value,
            ))
        for req in result.requirements.location_requirements:
            self.db.add(JobRequirement(
                job_id=job.id,
                requirement_type="LOCATION",
                name=req.name[:255],
                description=req.description,
                importance=req.importance.value,
            ))
        for req in result.requirements.other_requirements:
            self.db.add(JobRequirement(
                job_id=job.id,
                requirement_type="OTHER",
                name=req.name[:255],
                description=req.description,
                importance=req.importance.value,
            ))

        # Mark extraction as successful
        job.extraction_status = "SUCCESS"
        job.requirements_extracted = True
        self.db.commit()

    def _match_job(
        self, candidate_id: int, job: Job, cv_profile_id: int | None = None
    ) -> MatchResult | None:
        """Match a job against the selected candidate evidence.

        ``cv_profile_id`` is handed straight to the shared matching service,
        which resolves it through the profile-eligibility gate. Omitting it is
        the unchanged legacy path: the shared Candidate record.
        """
        from app.models import Candidate

        candidate = self.db.execute(
            select(Candidate).where(Candidate.id == candidate_id)
        ).scalars().first()

        if not candidate:
            return None

        from app.services.matching import run_match

        return run_match(self.db, candidate, job, cv_profile_id=cv_profile_id)

    def _job_to_dict(self, job: Job) -> dict:
        """Convert Job to dictionary for API response."""
        return {
            "id": job.id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "source": job.source,
            "source_id": job.source_id,
            "external_id": job.external_id,
            "is_discovered": job.is_discovered,
            "description": job.description,
            "employment_type": job.employment_type,
            "remote_status": job.remote_status,
            "salary_min": job.salary_min,
            "salary_max": job.salary_max,
            "posted_at": job.posted_at.isoformat() if job.posted_at else None,
            "discovered_at": job.discovered_at.isoformat() if job.discovered_at else None,
            # Required by JobOut. Omitting these made every non-empty discovery
            # response fail validation with a 500.
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "requirements_extracted": job.requirements_extracted,
            "extraction_status": job.extraction_status,
            "requirements": [
                {
                    "id": req.id,
                    "requirement_type": req.requirement_type,
                    "name": req.name,
                    "description": req.description,
                    "importance": req.importance,
                    "years_required": req.years_required,
                }
                for req in job.requirements
            ],
        }

    def _match_to_dict(self, match: MatchResult) -> dict:
        """Convert MatchResult to dictionary."""
        import json
        return {
            "id": match.id,
            "candidate_id": match.candidate_id,
            "job_id": match.job_id,
            "technical_score": match.technical_score,
            "experience_score": match.experience_score,
            "education_score": match.education_score,
            "location_score": match.location_score,
            "other_score": match.other_score,
            "overall_score": match.overall_score,
            "recommendation": match.recommendation,
            "confidence": match.confidence,
            "matched_items": json.loads(match.matched_items) if match.matched_items else [],
            "gap_items": json.loads(match.gap_items) if match.gap_items else [],
            "blocker_items": json.loads(match.blocker_items) if match.blocker_items else [],
            "unknown_items": json.loads(match.unknown_items) if match.unknown_items else [],
            "explanation": match.explanation,
            "cv_profile_id": match.cv_profile_id,
            "created_at": match.created_at.isoformat() if match.created_at else None,
        }


# Convenience function for API use
def discover_jobs(
    db: Session,
    candidate_id: int,
    query: str,
    country: str = "ng",
    location: str | None = None,
    remote_only: bool = False,
    max_results: int = 20,
    cv_profile_id: int | None = None,
) -> list[dict]:
    """Discover and match jobs for a candidate."""
    service = JobDiscoveryService(db)
    return service.discover_jobs(
        candidate_id=candidate_id,
        query=query,
        country=country,
        location=location,
        remote_only=remote_only,
        max_results=max_results,
        cv_profile_id=cv_profile_id,
    )
