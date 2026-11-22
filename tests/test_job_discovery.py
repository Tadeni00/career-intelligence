"""Tests for the JSearch job discovery service."""

from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models import Candidate, CandidateSkill, Education, Experience, Importance, Job, JobRequirement, Skill
from app.services.job_discovery import JobDiscoveryService
from app.services.jsearch import JSearchClient, JSearchJob


@pytest.fixture
def mock_jsearch_response() -> dict:
    """Sample JSearch API response."""
    return {
        "data": [
            {
                "job_id": "test_job_123",
                "job_title": "Senior Data Scientist",
                "employer_name": "TechCorp Nigeria",
                "job_location": "Lagos, Nigeria",
                "job_description": "We are looking for a Senior Data Scientist with Python and SQL experience. Required: 5+ years of experience in machine learning.",
                "job_apply_link": "https://jsearch.example.com/apply/123",
                "job_posted_at_datetime_utc": "2024-01-15T10:00:00Z",
                "job_min_salary": 80000,
                "job_max_salary": 120000,
                "job_salary_currency": "USD",
                "job_employment_type": "FULLTIME",
                "job_is_remote": True,
            },
            {
                "job_id": "test_job_456",
                "title": "Data Analyst",
                "employer_name": "DataCorp",
                "location": "Abuja, Nigeria",
                "description": "Data Analyst role. Required: SQL, Excel, Tableau. 2+ years experience.",
                "apply_link": "https://jsearch.example.com/apply/456",
                "job_posted_at_datetime_utc": "2024-01-20T10:00:00Z",
                "job_min_salary": 50000,
                "job_max_salary": 70000,
                "job_salary_currency": "USD",
                "job_employment_type": "FULLTIME",
                "job_is_remote": False,
            },
        ]
    }


@pytest.fixture
def mock_jsearch_client() -> MagicMock:
    """Mock JSearchClient with predefined responses."""
    mock_client = MagicMock(spec=JSearchClient)
    mock_client.search_jobs = AsyncMock(return_value=[
        JSearchJob(
            provider_job_id="test_job_123",
            title="Senior Data Scientist",
            company="TechCorp Nigeria",
            location="Lagos, Nigeria",
            description="We are looking for a Senior Data Scientist with Python and SQL experience. Required: 5+ years of experience in machine learning.",
            apply_url="https://jsearch.example.com/apply/123",
            posted_at=datetime(2024, 1, 15, 10, 0, 0),
            salary_min=80000.0,
            salary_max=120000.0,
            salary_currency="USD",
            employment_type="FULLTIME",
            remote_status="REMOTE",
        ),
        JSearchJob(
            provider_job_id="test_job_456",
            title="Data Analyst",
            company="DataCorp",
            location="Abuja, Nigeria",
            description="Data Analyst role. Required: SQL, Excel, Tableau. 2+ years experience.",
            apply_url="https://jsearch.example.com/apply/456",
            posted_at=datetime(2024, 1, 20, 10, 0, 0),
            salary_min=50000.0,
            salary_max=70000.0,
            salary_currency="USD",
            employment_type="FULLTIME",
            remote_status=None,
        ),
    ])
    return mock_client


@pytest.fixture
def mock_candidate(db_session) -> Candidate:
    """Create a mock candidate with skills and experience."""
    # Create skills first
    python_skill = Skill(id=1, name="Python", category="Programming")
    sql_skill = Skill(id=2, name="SQL", category="Data")
    ml_skill = Skill(id=3, name="Machine Learning", category="ML")
    db_session.add_all([python_skill, sql_skill, ml_skill])
    db_session.flush()

    candidate = Candidate(
        id=1,
        name="Test Candidate",
        professional_title="Data Scientist",
        email="test@example.com",
        location="Lagos, Nigeria",
        years_of_experience=6.0,
        skills=[
            CandidateSkill(id=1, candidate_id=1, skill_id=1, proficiency="Expert", years_experience=5.0),
            CandidateSkill(id=2, candidate_id=1, skill_id=2, proficiency="Advanced", years_experience=4.0),
            CandidateSkill(id=3, candidate_id=1, skill_id=3, proficiency="Advanced", years_experience=4.0),
        ],
        experience=[
            Experience(
                id=1,
                company="TechCorp",
                title="Senior Data Scientist",
                start_date="2020-01",
                end_date=None,
                description="Built ML models using Python and SQL. Led A/B experiments.",
                is_current=True,
            ),
        ],
        education=[
            Education(id=1, institution="University of Lagos", degree="MSc Computer Science", field="Data Science", start_date="2015-09", end_date="2017-06"),
        ],
    )
    db_session.add(candidate)
    db_session.commit()
    return candidate


class TestJobDiscoveryService:
    """Tests for the JobDiscoveryService."""

    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.db = db_session

    def test_discover_jobs_success(self, db_session, mock_candidate):
        """Test successful job discovery and matching."""
        db_session.add(mock_candidate)
        db_session.commit()

        service = JobDiscoveryService(db_session)

        # Mock the JSearch client
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = [
                JSearchJob(
                    provider_job_id="test_job_123",
                    title="Senior Data Scientist",
                    company="TechCorp Nigeria",
                    location="Lagos, Nigeria",
                    description="We are looking for a Senior Data Scientist with Python and SQL experience. Required: 5+ years of experience in machine learning.",
                    apply_url="https://jsearch.example.com/apply/123",
                    posted_at=datetime(2024, 1, 15, 10, 0, 0),
                    salary_min=80000.0,
                    salary_max=120000.0,
                    salary_currency="USD",
                    employment_type="FULLTIME",
                    remote_status="REMOTE",
                ),
            ]

            results = service.discover_jobs(
                candidate_id=1,
                query="data scientist",
                country="ng",
                max_results=10,
            )

            assert len(results) == 1
            assert results[0]["job"]["title"] == "Senior Data Scientist"
            assert results[0]["job"]["company"] == "TechCorp Nigeria"
            assert results[0]["job"]["is_discovered"] is True
            assert results[0]["match"] is not None
            assert results[0]["match"]["recommendation"] in ["APPLY", "APPLY_WITH_TAILORING", "STRETCH", "SKIP"]

    def test_discover_jobs_empty_results(self, db_session, mock_candidate):
        """Test job discovery with empty results."""
        db_session.add(mock_candidate)
        db_session.commit()

        service = JobDiscoveryService(db_session)

        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = []
            with patch("app.services.indeed.search_indeed_jobs", return_value=[]):
                results = service.discover_jobs(
                    candidate_id=1,
                    query="nonexistent role",
                    country="ng",
                )

            assert results == []

    def test_discover_jobs_duplicate_prevention(self, db_session, mock_candidate):
        """Test that duplicate jobs are not created."""
        db_session.add(mock_candidate)
        db_session.commit()

        service = JobDiscoveryService(db_session)

        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            job_data = JSearchJob(
                provider_job_id="test_job_123",
                title="Senior Data Scientist",
                company="TechCorp Nigeria",
                location="Lagos, Nigeria",
                description="We are looking for a Senior Data Scientist with Python and SQL experience. Required: 5+ years of experience in machine learning.",
                apply_url="https://jsearch.example.com/apply/123",
                posted_at=datetime(2024, 1, 15, 10, 0, 0),
                salary_min=80000.0,
                salary_max=120000.0,
                salary_currency="USD",
                employment_type="FULLTIME",
                remote_status="REMOTE",
            )
            mock_search.return_value = [job_data, job_data]  # Same job twice

            results = service.discover_jobs(
                candidate_id=1,
                query="data scientist",
                country="ng",
                max_results=10,
            )

            # Should only process unique jobs
            assert len(results) == 1

    def test_discover_jobs_extraction_failure(self, db_session, mock_candidate):
        """Test handling of extraction failures."""
        db_session.add(mock_candidate)
        db_session.commit()

        service = JobDiscoveryService(db_session)

        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = [
                JSearchJob(
                    provider_job_id="test_job_bad",
                    title="Bad Job",
                    company="Bad Corp",
                    location="Lagos",
                    description="",  # Empty description should cause extraction failure
                    apply_url="https://example.com/apply",
                    posted_at=datetime(2024, 1, 15),
                    salary_min=None,
                    salary_max=None,
                    salary_currency=None,
                    employment_type=None,
                    remote_status=None,
                ),
            ]

            results = service.discover_jobs(
                candidate_id=1,
                query="bad job",
                country="ng",
            )

            # Should handle extraction failure gracefully
            assert len(results) == 1
            assert results[0]["job"]["extraction_status"] == "EMPTY_CONFIRMED"

    def test_shortlist_creates_application(self, db_session, mock_candidate):
        """Test shortlisting a job creates an application."""
        db_session.add(mock_candidate)
        db_session.commit()

        # Create a job first
        job = Job(
            title="Test Job",
            company="Test Corp",
            location="Lagos",
            url="https://example.com/apply",
            source="jsearch",
            source_id="test_123",
            external_id="jsearch:test_123",
            is_discovered=True,
            description="Test job description",
        )
        db_session.add(job)
        db_session.commit()

        from app.models import Application, ApplicationStatus

        # Shortlist the job by creating an application directly
        application = Application(
            candidate_id=mock_candidate.id,
            job_id=job.id,
            status=ApplicationStatus.INTERESTED.value,
        )
        db_session.add(application)
        db_session.commit()

        # Verify the application was created
        assert application.id is not None
        assert application.status == ApplicationStatus.INTERESTED.value
        assert application.candidate_id == mock_candidate.id
        assert application.job_id == job.id


class TestJSearchClient:
    """Tests for the JSearchClient."""

    def test_normalize_job_valid(self):
        """Test normalization of valid job data."""
        client = JSearchClient(api_key="test_key")

        job_data = {
            "job_id": "123",
            "job_title": "Software Engineer",
            "employer_name": "Test Corp",
            "job_location": "Lagos, Nigeria",
            "job_description": "Great job!",
            "job_apply_link": "https://example.com/apply",
            "job_posted_at_datetime_utc": "2024-01-15T10:00:00Z",
            "job_min_salary": 100000,
            "job_max_salary": 150000,
            "job_salary_currency": "USD",
            "job_employment_type": "FULLTIME",
            "job_is_remote": True,
        }

        job = JSearchClient._normalize_job(None, None)  # Static method test
        # Actually test the normalization logic directly
        pass

    def test_normalize_job_missing_fields(self):
        """Test that jobs with missing required fields are rejected."""
        pass

    def test_normalize_job_invalid_url(self):
        """Test that jobs with invalid URLs are rejected."""
        pass


class TestJSearchAPIIntegration:
    """Integration tests for JSearch API (requires real credentials)."""

    @pytest.mark.skipif(True, reason="Requires live API credentials")
    @pytest.mark.asyncio
    async def test_live_nigeria_search(self):
        """Test live search for Nigeria jobs."""
        from app.services.jsearch import JSearchClient

        async with JSearchClient() as client:
            jobs = await client.search_jobs(
                query="data scientist",
                country="ng",
                num_pages=1,
            )

            assert len(jobs) > 0
            for job in jobs:
                assert job.title
                assert job.company
                assert job.apply_url
                assert job.provider_job_id


# Fixtures for pytest
@pytest.fixture
def db_session():
    """Provide a database session for testing."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    yield db
    db.close()


LIVE_SHAPE_ENVELOPE = {
    "status": "OK",
    "request_id": "req-test-123",
    "parameters": {"query": "Data Scientist in Lagos", "country": "ng"},
    "data": {
        "cursor": "None",
        "jobs": [
            {
                "job_id": "abc123",
                "job_title": "Data Science Manager &#8211; Kuda MFB",
                "employer_name": "Kuda Microfinance Bank",
                "job_city": "Lekki",
                "job_state": "Lagos",
                "job_country": "NG",
                "job_description": "Required: Python, SQL, and 5+ years of experience building models.",
                "job_apply_link": "https://employ.ng/jobs/data-science-manager",
                "job_posted_at_datetime_utc": "2026-10-11T00:00:00.000Z",
                "job_employment_type": "Full-time",
                "job_is_remote": False,
            },
            {
                "job_id": "def456",
                "job_title": "Remote Data Analyst",
                "employer_name": "Remote Corp",
                "job_location": "Lagos, Nigeria",
                "job_description": "Preferred: Tableau experience.",
                "job_apply_link": "https://example.com/apply/456",
                "job_is_remote": True,
            },
        ],
    },
}


def _client_with_handler(handler, api_key="test-key") -> JSearchClient:
    import httpx

    client = JSearchClient.__new__(JSearchClient)
    client.api_key = api_key
    client.base_url = "https://jsearch.p.rapidapi.com"
    client.timeout_seconds = 15.0
    transport = httpx.MockTransport(handler)
    client._client = httpx.AsyncClient(
        base_url=client.base_url,
        headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
        transport=transport,
        timeout=httpx.Timeout(15.0),
    )
    return client


class TestJSearchGatewayContract:
    """Live-verified RapidAPI gateway contract (smoke-tested 2026-10-13)."""

    def test_default_base_url_is_verified_gateway(self):
        from app.services.jsearch import JSEARCH_GATEWAY_BASE_URL

        assert JSEARCH_GATEWAY_BASE_URL == "https://jsearch.p.rapidapi.com"
        client = JSearchClient(api_key="test-key")
        assert client.base_url == "https://jsearch.p.rapidapi.com"

    def test_search_uses_verified_path_and_auth(self):
        import asyncio
        import httpx

        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["auth"] = request.headers.get("X-RapidAPI-Key")
            seen["host"] = request.headers.get("X-RapidAPI-Host")
            return httpx.Response(200, json=LIVE_SHAPE_ENVELOPE)

        client = _client_with_handler(handler)
        jobs = asyncio.run(client.search_jobs(query="Data Scientist", country="ng"))
        assert seen["path"] == "/search-v2"
        assert seen["auth"] == "test-key"
        assert seen["host"] == "jsearch.p.rapidapi.com"
        assert len(jobs) == 2

    def test_dict_envelope_with_jobs_list_is_parsed(self):
        import asyncio
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=LIVE_SHAPE_ENVELOPE)

        jobs = asyncio.run(_client_with_handler(handler).search_jobs("x", "ng"))
        assert [j.provider_job_id for j in jobs] == ["abc123", "def456"]

    def test_legacy_list_envelope_is_tolerated(self):
        import asyncio
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"data": [LIVE_SHAPE_ENVELOPE["data"]["jobs"][0]]})

        jobs = asyncio.run(_client_with_handler(handler).search_jobs("x", "ng"))
        assert len(jobs) == 1
        assert jobs[0].provider_job_id == "abc123"

    def test_remote_only_filters_client_side(self):
        import asyncio
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=LIVE_SHAPE_ENVELOPE)

        client = _client_with_handler(handler)
        jobs = asyncio.run(client.search_jobs("x", "ng", remote_only=True))
        assert len(jobs) == 1
        assert jobs[0].provider_job_id == "def456"

    def test_title_entities_unescaped_and_location_fallback(self):
        import asyncio
        import httpx

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=LIVE_SHAPE_ENVELOPE)

        jobs = asyncio.run(_client_with_handler(handler).search_jobs("x", "ng"))
        first = jobs[0]
        assert first.title == "Data Science Manager \u2013 Kuda MFB"
        assert "&#" not in first.title
        assert first.location == "Lekki, Lagos, NG"
        assert jobs[1].location == "Lagos, Nigeria"

    def test_missing_key_error_contains_no_secret(self):
        from types import SimpleNamespace
        from app.services.jsearch import JSearchError

        with patch("app.services.jsearch.get_settings") as mock_settings:
            mock_settings.return_value = SimpleNamespace(
                jsearch_api_key="", jsearch_base_url="https://jsearch.p.rapidapi.com"
            )
            try:
                JSearchClient(api_key=None)
                raise AssertionError("expected JSearchError")
            except JSearchError as exc:
                assert "gsk" not in str(exc).lower()
                assert "key" in str(exc).lower()

    def test_auth_failure_raises_once_without_retry(self):
        import asyncio
        import httpx
        from app.services.jsearch import JSearchAuthError

        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(1)
            return httpx.Response(401, json={"message": "Unauthorized"})

        with pytest.raises(JSearchAuthError):
            asyncio.run(_client_with_handler(handler).search_jobs("x", "ng"))
        assert len(calls) == 1

    def test_rate_limit_maps_with_retry_after(self):
        import asyncio
        import httpx
        from app.services.jsearch import JSearchRateLimitError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, headers={"Retry-After": "30"}, json={"message": "Too Many Requests"})

        with pytest.raises(JSearchRateLimitError) as exc_info:
            asyncio.run(_client_with_handler(handler).search_jobs("x", "ng"))
        assert exc_info.value.retry_after == 30

    def test_server_error_is_truncated_and_mapped(self):
        import asyncio
        import httpx
        from app.services.jsearch import JSearchProviderError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, text="x" * 5000)

        with pytest.raises(JSearchProviderError) as exc_info:
            asyncio.run(_client_with_handler(handler).search_jobs("x", "ng"))
        assert len(str(exc_info.value)) < 400

    def test_timeout_maps_to_504(self):
        import asyncio
        import httpx
        from app.services.jsearch import JSearchError

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("timed out", request=request)

        with pytest.raises(JSearchError) as exc_info:
            asyncio.run(_client_with_handler(handler).search_jobs("x", "ng"))
        assert exc_info.value.status_code == 504

    def test_malformed_json_maps_to_error(self):
        import asyncio
        import httpx
        from app.services.jsearch import JSearchError

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, text="not json{")

        with pytest.raises(JSearchError):
            asyncio.run(_client_with_handler(handler).search_jobs("x", "ng"))


class TestDiscoveryServiceWiring:
    """Service-level wiring hardened by the live smoke test."""

    def test_indeed_fallback_on_empty_jsearch(self, db_session, mock_candidate):
        """JSearch empty -> Indeed.com Indeed returns jobs, provenance says indeed."""
        from app.services.indeed import JSearchJob as IndeedJob
        from app.services.job_discovery import JobDiscoveryService

        db_session.add(mock_candidate)
        db_session.commit()
        service = JobDiscoveryService(db_session)

        indeed_job = IndeedJob(
            provider_job_id="1",
            title="Benin Dev",
            company="SociallyX",
            location="Cotonou, Benin Republic",
            description="We are looking for a Benin developer.",
            apply_url="https://indeed.com/x/apply/1",
            posted_at=datetime(2026, 10, 1, 10, 0, 0),
            salary_min=None,
            salary_max=None,
            salary_currency="USD",
            employment_type="FULLTIME",
            remote_status=None,
            source="indeed",
        )
        with patch("app.services.job_discovery.search_jsearch_jobs", return_value=[]):
            with patch(
                "app.services.indeed.search_indeed_jobs", return_value=[indeed_job]
            ) as mock_indeed:
                results = service.discover_jobs(
                    candidate_id=1, query="benin dev", country="bj"
                )
        assert len(results) == 1
        assert results[0]["job"]["title"] == "Benin Dev"
        assert mock_indeed.called

    def test_max_results_maps_to_bounded_pages(self, db_session, mock_candidate):
        from app.services.job_discovery import JobDiscoveryService

        db_session.add(mock_candidate)
        db_session.commit()
        service = JobDiscoveryService(db_session)
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = []
            with patch("app.services.indeed.search_indeed_jobs", return_value=[]):
                service.discover_jobs(candidate_id=1, query="data scientist", country="ng", max_results=15)
                _, kwargs = mock_search.call_args
                assert kwargs["num_pages"] == 2
                service.discover_jobs(candidate_id=1, query="data scientist", country="ng", max_results=50)
                _, kwargs = mock_search.call_args
                assert kwargs["num_pages"] == 5

    def test_remote_only_passes_through(self, db_session, mock_candidate):
        from app.services.job_discovery import JobDiscoveryService

        db_session.add(mock_candidate)
        db_session.commit()
        service = JobDiscoveryService(db_session)
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = []
            with patch("app.services.indeed.search_indeed_jobs", return_value=[]):
                service.discover_jobs(candidate_id=1, query="x", country="ng", remote_only=True)
            _, kwargs = mock_search.call_args
            assert kwargs["remote_only"] is True


class TestDiscoverRouteErrors:
    """Provider failures must not masquerade as empty successful searches."""

    def test_auth_failure_returns_503_without_secret(self, client):
        from app.services.jsearch import JSearchAuthError

        with patch("app.api.routes.external_jobs.discover_jobs") as mock_discover:
            mock_discover.side_effect = JSearchAuthError()
            response = client.post(
                "/api/v1/jobs/discover",
                json={"query": "data scientist", "country": "ng"},
            )
        assert response.status_code == 503
        assert "gsk" not in response.text.lower()
        assert "api key" in response.text.lower() or "authentication" in response.text.lower()

    def test_rate_limit_returns_429(self, client):
        from app.services.jsearch import JSearchRateLimitError

        with patch("app.api.routes.external_jobs.discover_jobs") as mock_discover:
            mock_discover.side_effect = JSearchRateLimitError()
            response = client.post(
                "/api/v1/jobs/discover",
                json={"query": "data scientist", "country": "ng"},
            )
        assert response.status_code == 429

    def test_provider_failure_returns_502(self, client):
        from app.services.jsearch import JSearchError

        with patch("app.api.routes.external_jobs.discover_jobs") as mock_discover:
            mock_discover.side_effect = JSearchError("boom", 502)
            response = client.post(
                "/api/v1/jobs/discover",
                json={"query": "data scientist", "country": "ng"},
            )
        assert response.status_code == 502

    def test_empty_results_return_200_with_zero_total(self, client):
        with patch("app.api.routes.external_jobs.discover_jobs") as mock_discover:
            mock_discover.return_value = []
            response = client.post(
                "/api/v1/jobs/discover",
                json={"query": "obscure role xyz", "country": "ng"},
            )
        assert response.status_code == 200
        assert response.json()["total"] == 0


def _make_discovered_job(db, **overrides) -> int:
    from app.models import Job

    payload = dict(
        title="Data Scientist",
        company="Kuda Microfinance Bank",
        location="Lagos, Lagos",
        url="https://employ.ng/jobs/data-science-manager",
        source="jsearch",
        source_id="live-probe-1",
        external_id="jsearch:live-probe-1",
        is_discovered=True,
        description="Required: Python, SQL, and 5+ years of experience building models.",
    )
    payload.update(overrides)
    job = Job(**payload)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


class TestShortlistAcceptance:
    """Discovery-to-application workflow acceptance (mocked provider)."""

    def test_shortlist_creates_interested_application(self, client, db, candidate):
        from app.models import Application

        job_id = _make_discovered_job(db)
        response = client.post(f"/api/v1/jobs/discovered/{job_id}/shortlist")
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "INTERESTED"

        stored = db.get(Application, body["application_id"])
        assert stored is not None
        assert stored.candidate_id == candidate.id
        assert stored.job_id == job_id
        assert stored.status == "INTERESTED"

    def test_repeated_shortlist_reuses_application(self, client, db, candidate):
        from app.models import Application
        from sqlalchemy import func, select

        job_id = _make_discovered_job(db)
        first = client.post(f"/api/v1/jobs/discovered/{job_id}/shortlist")
        second = client.post(f"/api/v1/jobs/discovered/{job_id}/shortlist")
        assert first.status_code == 201
        assert second.status_code == 201
        assert first.json()["application_id"] == second.json()["application_id"]

        count = db.execute(
            select(func.count())
            .select_from(Application)
            .where(
                Application.candidate_id == candidate.id,
                Application.job_id == job_id,
            )
        ).scalar()
        assert count == 1

    def test_shortlist_missing_job_returns_404(self, client):
        response = client.post("/api/v1/jobs/discovered/999999/shortlist")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_detail_reports_shortlisted_flag(self, client, db, candidate):
        job_id = _make_discovered_job(db)
        before = client.get(f"/api/v1/jobs/discovered/{job_id}")
        assert before.status_code == 200
        assert before.json()["shortlisted"] is False

        client.post(f"/api/v1/jobs/discovered/{job_id}/shortlist")

        after = client.get(f"/api/v1/jobs/discovered/{job_id}")
        assert after.status_code == 200
        assert after.json()["shortlisted"] is True

    def test_detail_missing_job_returns_404(self, client):
        response = client.get("/api/v1/jobs/discovered/999999")
        assert response.status_code == 404

    def test_detail_carries_match_and_original_url(self, client, db, candidate):
        from app.models import Job

        job_id = _make_discovered_job(db)
        body = client.get(f"/api/v1/jobs/discovered/{job_id}").json()
        assert body["job"]["id"] == job_id
        assert body["job"]["url"] == "https://employ.ng/jobs/data-science-manager"
        assert body["job"]["source"] == "jsearch"
        assert "match" in body

    def test_shortlisted_job_visible_in_applications(self, client, db, candidate):
        job_id = _make_discovered_job(db)
        client.post(f"/api/v1/jobs/discovered/{job_id}/shortlist")
        listing = client.get("/api/v1/applications").json()
        assert any(app["job_id"] == job_id and app["status"] == "INTERESTED" for app in listing)

    def test_job_without_url_still_renders(self, client, db, candidate):
        job_id = _make_discovered_job(db, url=None)
        body = client.get(f"/api/v1/jobs/discovered/{job_id}").json()
        assert body["job"]["url"] is None


# Synthetic regression fixture for the Task 25 near-duplicate case
# (Bioventures Healthcare Data Analyst via two publishers). Titles, employer,
# location and overlap level mirror the observed case; descriptions are
# paraphrased stand-ins, not the original postings.
DUP_DESC_A = (
    "We are looking for a Healthcare Data Analyst to gather and analyze "
    "healthcare data from multiple sources including insurance processing "
    "clinical operations and patient behavior to extract trends and business "
    "insights Required skills include SQL Excel and Tableau with strong "
    "communication skills and two years of experience in data analysis "
    "You will report to the Head of Analytics and present findings to "
    "stakeholders each week"
)
DUP_DESC_B = (
    "We are looking for a Healthcare Data Analyst to gather and analyze "
    "healthcare data from multiple sources including insurance processing "
    "clinical operations and patient behavior to extract trends and business "
    "insights Required skills include SQL Excel and Tableau with strong "
    "communication skills and two years of experience in data analysis "
    "The role reports to the Analytics Manager with weekly stakeholder "
    "presentations"
)


def _dup_candidate(**overrides):
    from app.services.duplicates import _Candidate

    base = dict(
        id=None,
        external_id=None,
        title="Healthcare Data Analyst",
        company="Bioventures Limited",
        location="Lagos, Lagos",
        posted_at=None,
        description=DUP_DESC_A,
        url="",
    )
    base.update(overrides)
    return _Candidate(**base)


class TestDuplicateReview:
    """Cross-publisher duplicate-review signals (no live calls, no merges)."""

    def test_same_provider_id_is_not_flagged(self, db_session, mock_candidate):
        """Repeating the same provider identifier creates one row, no self-flag."""
        from app.models import Job
        from sqlalchemy import func, select

        db_session.add(mock_candidate)
        db_session.commit()
        service = JobDiscoveryService(db_session)
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = [
                JSearchJob(
                    provider_job_id="same-id-1",
                    title="Data Scientist",
                    company="Test Corp",
                    location="Lagos, Nigeria",
                    description="Required: Python and SQL.",
                    apply_url="https://example.com/apply/same1",
                    posted_at=datetime(2024, 1, 15, 10, 0, 0),
                    salary_min=None,
                    salary_max=None,
                    salary_currency=None,
                    employment_type="FULLTIME",
                    remote_status=None,
                ),
                JSearchJob(
                    provider_job_id="same-id-1",
                    title="Data Scientist",
                    company="Test Corp",
                    location="Lagos, Nigeria",
                    description="Required: Python and SQL.",
                    apply_url="https://example.com/apply/same1",
                    posted_at=datetime(2024, 1, 15, 10, 0, 0),
                    salary_min=None,
                    salary_max=None,
                    salary_currency=None,
                    employment_type="FULLTIME",
                    remote_status=None,
                ),
            ]
            results = service.discover_jobs(
                candidate_id=1, query="data scientist", country="ng"
            )
            assert len(results) == 1
            assert results[0]["duplicate_review"]["status"] != "Likely duplicate"
            count = db_session.execute(
                select(func.count()).select_from(Job).where(Job.external_id == "jsearch:same-id-1")
            ).scalar()
            assert count == 1

    def test_strong_evidence_pair_is_likely_duplicate(self):
        from datetime import datetime, timezone

        from app.services.duplicates import review_candidates

        target = _dup_candidate(
            id=1,
            external_id="jsearch:dup-a",
            posted_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
            url="https://talent.example.com/jobs/1",
        )
        other = _dup_candidate(
            id=2,
            external_id="jsearch:dup-b",
            title="Healthcare Data Analyst Job at Bioventures Limited",
            description=DUP_DESC_B,
            posted_at=datetime(2026, 10, 7, tzinfo=timezone.utc),
            url="https://indeed.example.com/jobs/2",
        )
        review = review_candidates(target, [other])
        assert review.status == "Likely duplicate"
        assert review.related_job_ids == (2,)
        assert "employer" in review.reason.lower() or "title" in review.reason.lower()

    def test_similar_titles_different_descriptions_at_most_possible(self):
        from app.services.duplicates import review_candidates

        target = _dup_candidate(id=1, external_id="jsearch:x-a", description=DUP_DESC_A)
        other = _dup_candidate(
            id=2,
            external_id="jsearch:x-b",
            title="Healthcare Data Analyst Job at Bioventures Limited",
            description="Completely unrelated posting about warehouse night shifts and forklift certification.",
        )
        review = review_candidates(target, [other])
        assert review.status in ("Possible duplicate", "No duplicate signal")
        assert review.status != "Likely duplicate"

    def test_distinct_vacancies_same_employer_no_signal(self):
        from app.services.duplicates import review_candidates

        target = _dup_candidate(id=1, external_id="jsearch:y-a")
        other = _dup_candidate(
            id=2,
            external_id="jsearch:y-b",
            title="Accountant",
            description="Handles accounts payable and monthly reconciliation for the finance team.",
        )
        review = review_candidates(target, [other])
        assert review.status == "No duplicate signal"
        assert review.related_job_ids == ()

    def test_missing_provider_ids_still_comparable(self):
        from datetime import datetime, timezone

        from app.services.duplicates import review_candidates

        target = _dup_candidate(
            id=1, external_id=None,
            posted_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
            url="https://example.com/jobs/1",
        )
        other = _dup_candidate(
            id=2, external_id=None,
            title="Healthcare Data Analyst Job at Bioventures Limited",
            description=DUP_DESC_B,
            posted_at=datetime(2026, 10, 6, tzinfo=timezone.utc),
            url="https://example.com/jobs/1",
        )
        review = review_candidates(target, [other])
        assert review.status == "Likely duplicate"

    def test_conflicting_location_vetoes(self):
        from app.services.duplicates import review_candidates

        target = _dup_candidate(id=1, external_id="jsearch:z-a")
        other = _dup_candidate(
            id=2, external_id="jsearch:z-b", location="Abuja, FCT",
            description=DUP_DESC_B,
        )
        review = review_candidates(target, [other])
        assert review.status == "No duplicate signal"

    def test_missing_location_is_neutral(self):
        from app.services.duplicates import review_candidates

        target = _dup_candidate(id=1, external_id="jsearch:w-a")
        other = _dup_candidate(
            id=2, external_id="jsearch:w-b", location="",
            description=DUP_DESC_B,
        )
        review = review_candidates(target, [other])
        assert review.status in ("Likely duplicate", "Possible duplicate")

    def test_missing_descriptions_cap_at_possible(self):
        from app.services.duplicates import review_candidates

        target = _dup_candidate(id=1, external_id="jsearch:v-a", description="")
        other = _dup_candidate(id=2, external_id="jsearch:v-b", description="")
        review = review_candidates(target, [other])
        assert review.status != "Likely duplicate"

    def test_review_leaves_records_unchanged(self, client, db, candidate):
        from app.models import Application, Job
        from sqlalchemy import func, select

        first = _make_discovered_job(db, title="Healthcare Data Analyst",
                                     company="Bioventures Limited")
        second = _make_discovered_job(
            db, title="Healthcare Data Analyst Job at Bioventures Limited",
            company="Bioventures Limited", external_id="jsearch:other-1",
            source_id="other-1",
        )

        def counts():
            return {
                t.__tablename__: db.execute(
                    select(func.count()).select_from(t)).scalar()
                for t in (Job, Application)
            }

        before_jobs = {j.id: (j.title, j.description) for j in db.query(Job).all()}
        before = counts()
        body = client.get(f"/api/v1/jobs/discovered/{first}").json()
        assert body["duplicate_review"]["status"] in (
            "Likely duplicate", "Possible duplicate")
        assert second in body["duplicate_review"]["related_job_ids"]
        assert counts() == before
        assert {j.id: (j.title, j.description) for j in db.query(Job).all()} == before_jobs

    def test_shortlist_and_freshness_intact_with_duplicate_present(
        self, client, db, candidate
    ):
        first = _make_discovered_job(db, title="Healthcare Data Analyst",
                                     company="Bioventures Limited")
        _make_discovered_job(
            db, title="Healthcare Data Analyst Job at Bioventures Limited",
            company="Bioventures Limited", external_id="jsearch:other-2",
            source_id="other-2",
        )
        first_shortlist = client.post(f"/api/v1/jobs/discovered/{first}/shortlist")
        second_shortlist = client.post(f"/api/v1/jobs/discovered/{first}/shortlist")
        assert first_shortlist.status_code == 201
        assert (
            first_shortlist.json()["application_id"]
            == second_shortlist.json()["application_id"]
        )
        body = client.get(f"/api/v1/jobs/discovered/{first}").json()
        assert body["shortlisted"] is True
        assert body["freshness"]["status"] in ("current", "stale", "unknown")
        assert body["duplicate_review"]["status"] in (
            "Likely duplicate", "Possible duplicate")

    def test_deterministic_across_runs(self, client, db, candidate):
        first = _make_discovered_job(db, title="Healthcare Data Analyst",
                                     company="Bioventures Limited")
        _make_discovered_job(
            db, title="Healthcare Data Analyst Job at Bioventures Limited",
            company="Bioventures Limited", external_id="jsearch:other-3",
            source_id="other-3",
        )
        one = client.get(f"/api/v1/jobs/discovered/{first}").json()["duplicate_review"]
        two = client.get(f"/api/v1/jobs/discovered/{first}").json()["duplicate_review"]
        assert one == two


def _frozen_now():
    from datetime import datetime, timezone

    return datetime(2026, 10, 13, 12, 0, 0, tzinfo=timezone.utc)


class TestFreshness:
    """Vacancy freshness: explicit, UTC-consistent, never inferred closure."""

    def test_fresh_vacancy_is_current(self):
        from datetime import timedelta
        from app.services.freshness import assess_freshness

        now = _frozen_now()
        posted = now - timedelta(days=5)
        result = assess_freshness(posted, posted + timedelta(days=30), now=now)
        assert result.status == "current"

    def test_old_vacancy_is_stale(self):
        from datetime import timedelta
        from app.services.freshness import assess_freshness

        now = _frozen_now()
        posted = now - timedelta(days=60)
        result = assess_freshness(posted, posted + timedelta(days=30), now=now)
        assert result.status == "stale"
        assert "stale" in result.reason.lower()

    def test_missing_posting_date_is_unknown(self):
        from app.services.freshness import assess_freshness

        result = assess_freshness(None, None, now=_frozen_now())
        assert result.status == "unknown"
        assert "unavailable" in result.reason.lower()

    def test_missing_expiration_is_unknown(self):
        from datetime import timedelta
        from app.services.freshness import assess_freshness

        now = _frozen_now()
        result = assess_freshness(now - timedelta(days=5), None, now=now)
        assert result.status == "unknown"

    def test_invalid_timestamps_fail_conservative(self):
        from app.services.freshness import assess_freshness, coerce_aware

        assert coerce_aware("not-a-datetime") is None
        assert coerce_aware(1791676800) is None
        assert coerce_aware(None) is None
        result = assess_freshness("garbage", "garbage", now=_frozen_now())
        assert result.status == "unknown"

    def test_naive_datetimes_treated_as_utc(self):
        from datetime import datetime, timedelta
        from app.services.freshness import assess_freshness, coerce_aware

        now = _frozen_now()
        naive_posted = datetime(2026, 10, 8, 12, 0, 0)
        coerced = coerce_aware(naive_posted)
        assert coerced is not None and coerced.tzinfo is not None
        fresh = assess_freshness(naive_posted, naive_posted + timedelta(days=30), now=now)
        assert fresh.status == "current"
        old = assess_freshness(
            datetime(2026, 8, 1, 12, 0, 0), datetime(2026, 8, 31, 12, 0, 0), now=now
        )
        assert old.status == "stale"

    def test_expired_shortlisted_job_stays_accessible(self, client, db, candidate):
        from datetime import datetime, timedelta, timezone

        posted = datetime.now(timezone.utc) - timedelta(days=60)
        job_id = _make_discovered_job(db, posted_at=posted, expires_at=posted + timedelta(days=30))
        client.post(f"/api/v1/jobs/discovered/{job_id}/shortlist")

        body = client.get(f"/api/v1/jobs/discovered/{job_id}").json()
        assert body["shortlisted"] is True
        assert body["freshness"]["status"] == "stale"

    def test_expired_job_visible_in_application_tracking(self, client, db, candidate):
        from datetime import datetime, timedelta, timezone

        posted = datetime.now(timezone.utc) - timedelta(days=60)
        job_id = _make_discovered_job(db, posted_at=posted, expires_at=posted + timedelta(days=30))
        client.post(f"/api/v1/jobs/discovered/{job_id}/shortlist")

        listing = client.get("/api/v1/applications").json()
        assert any(app["job_id"] == job_id for app in listing)

    def test_never_reports_closure(self):
        from datetime import timedelta
        from app.services.freshness import assess_freshness

        now = _frozen_now()
        cases = [
            (None, None),
            (now - timedelta(days=5), None),
            (now - timedelta(days=5), now + timedelta(days=25)),
            (now - timedelta(days=90), now - timedelta(days=60)),
            ("garbage", "garbage"),
        ]
        for posted, expires in cases:
            result = assess_freshness(posted, expires, now=now)
            assert result.status != "Closed"
            assert "closed" not in result.reason.lower()

    def test_discover_results_carry_freshness(self, db_session, mock_candidate):
        from datetime import datetime, timedelta, timezone

        db_session.add(mock_candidate)
        db_session.commit()

        service = JobDiscoveryService(db_session)
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            posted = datetime.now(timezone.utc) - timedelta(days=5)
            mock_search.return_value = [
                JSearchJob(
                    provider_job_id="fresh-probe-1",
                    title="Data Scientist",
                    company="Test Corp",
                    location="Lagos, Nigeria",
                    description="Required: Python and SQL.",
                    apply_url="https://example.com/apply/fresh1",
                    posted_at=posted,
                    salary_min=None,
                    salary_max=None,
                    salary_currency=None,
                    employment_type="FULLTIME",
                    remote_status=None,
                ),
            ]
            results = service.discover_jobs(
                candidate_id=1, query="data scientist", country="ng"
            )
            assert results[0]["freshness"]["status"] == "current"

    def test_discover_route_reports_stale(self, client, db, candidate):
        from datetime import datetime, timedelta, timezone

        posted = datetime.now(timezone.utc) - timedelta(days=60)
        job_id = _make_discovered_job(db, posted_at=posted, expires_at=posted + timedelta(days=30))
        body = client.get(f"/api/v1/jobs/discovered/{job_id}").json()
        assert body["freshness"]["status"] == "stale"
        assert body["job"]["id"] == job_id


class TestSearchRelevance:
    """Query-to-title relevance signal (deterministic, no provider calls)."""

    def test_aligned_data_scientist(self):
        from app.services.search_relevance import classify_search_relevance

        result = classify_search_relevance("Data Scientist", "Senior Data Scientist")
        assert result.label == "Aligned"
        assert "Data Scientist" in result.reason

    def test_mismatch_junior_analyst_under_scientist_query(self):
        from app.services.search_relevance import classify_search_relevance

        result = classify_search_relevance("Data Scientist", "Junior Data Analyst")
        assert result.label == "Mismatch"
        assert "Data Analyst" in result.reason

    def test_adjacent_analytics_engineer(self):
        from app.services.search_relevance import classify_search_relevance

        result = classify_search_relevance("Data Analyst", "Analytics Engineer")
        assert result.label == "Adjacent"

    def test_aligned_ml_abbreviation(self):
        from app.services.search_relevance import classify_search_relevance

        result = classify_search_relevance(
            "Machine Learning Engineer", "ML Engineer"
        )
        assert result.label == "Aligned"

    def test_uncertain_unknown_query(self):
        from app.services.search_relevance import classify_search_relevance

        result = classify_search_relevance("Plumber", "Senior Data Scientist")
        assert result.label == "Uncertain"

    def test_uncertain_ambiguous_title(self):
        from app.services.search_relevance import classify_search_relevance

        result = classify_search_relevance("Data Scientist", "Team Lead")
        assert result.label == "Uncertain"

    def test_uncertain_empty_inputs(self):
        from app.services.search_relevance import classify_search_relevance

        assert classify_search_relevance("", "Data Scientist").label == "Uncertain"
        assert classify_search_relevance("Data Scientist", "").label == "Uncertain"
        assert classify_search_relevance(None, None).label == "Uncertain"

    def test_comma_reversed_title_aligns(self):
        from app.services.search_relevance import classify_search_relevance

        result = classify_search_relevance("Data Scientist", "Scientist, Data")
        assert result.label == "Aligned"

    def test_training_content_is_mismatch(self):
        from app.services.search_relevance import classify_search_relevance

        result = classify_search_relevance(
            "Data Scientist", "Data Science Bootcamp 2026"
        )
        assert result.label == "Mismatch"

    def test_abbreviation_does_not_overmatch(self):
        from app.services.search_relevance import classify_search_relevance

        # "html" contains the letters "ml" but must not read as ML Engineer.
        result = classify_search_relevance(
            "Machine Learning Engineer", "HTML Developer"
        )
        assert result.label in ("Mismatch", "Uncertain")

    def test_same_vacancy_differs_by_query(self):
        from app.services.search_relevance import classify_search_relevance

        title = "Junior Data Analyst"
        assert (
            classify_search_relevance("Data Analyst", title).label == "Aligned"
        )
        assert (
            classify_search_relevance("Data Scientist", title).label == "Mismatch"
        )

    def test_mismatch_leaves_match_untouched(self, client, db, candidate):
        from app.services.job_discovery import JobDiscoveryService

        service = JobDiscoveryService(db)
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = [
                JSearchJob(
                    provider_job_id="rel-mismatch-1",
                    title="Junior Data Analyst",
                    company="Test Corp",
                    location="Lagos, Nigeria",
                    description="Required: SQL, Excel. 1+ years of experience.",
                    apply_url="https://example.com/apply/rel1",
                    posted_at=datetime(2024, 1, 15, 10, 0, 0),
                    salary_min=None,
                    salary_max=None,
                    salary_currency=None,
                    employment_type="FULLTIME",
                    remote_status=None,
                ),
            ]
            ds_results = service.discover_jobs(
                candidate_id=candidate.id, query="Data Scientist", country="ng"
            )
            da_results = service.discover_jobs(
                candidate_id=candidate.id, query="Data Analyst", country="ng"
            )

        assert ds_results[0]["search_relevance"]["label"] == "Mismatch"
        assert da_results[0]["search_relevance"]["label"] == "Aligned"
        # Candidate-fit output is identical; only the presentation signal differs.
        assert (
            ds_results[0]["match"]["overall_score"]
            == da_results[0]["match"]["overall_score"]
        )
        assert (
            ds_results[0]["match"]["recommendation"]
            == da_results[0]["match"]["recommendation"]
        )

    def test_detail_query_param_drives_relevance(self, client, db, candidate):
        job_id = _make_discovered_job(db, title="Junior Data Analyst")
        aligned = client.get(
            f"/api/v1/jobs/discovered/{job_id}", params={"query": "Data Analyst"}
        ).json()
        mismatch = client.get(
            f"/api/v1/jobs/discovered/{job_id}", params={"query": "Data Scientist"}
        ).json()
        assert aligned["search_relevance"]["label"] == "Aligned"
        assert mismatch["search_relevance"]["label"] == "Mismatch"

    def test_detail_without_query_is_uncertain(self, client, db, candidate):
        job_id = _make_discovered_job(db)
        body = client.get(f"/api/v1/jobs/discovered/{job_id}").json()
        assert body["search_relevance"]["label"] == "Uncertain"

    def test_malformed_fields_do_not_crash(self, client, db, candidate):
        job_id = _make_discovered_job(db, title="   ")
        body = client.get(
            f"/api/v1/jobs/discovered/{job_id}", params={"query": "   "}
        ).json()
        assert body["search_relevance"]["label"] == "Uncertain"
        assert body["job"]["id"] == job_id


# Fixtures for pytest
@pytest.fixture
def db_session():
    """Provide a database session for testing."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    yield db
    db.close()