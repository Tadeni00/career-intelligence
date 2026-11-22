"""Profile-aware job discovery and shortlisting.

The external provider is mocked throughout; no live call is made. Every fixture
is built inside the isolated test database.
"""

from __future__ import annotations

import io
from datetime import datetime
from unittest.mock import patch

import pytest
from app.models import Application, Candidate, MatchResult
from app.services.jsearch import JSearchJob
from docx import Document

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _docx_bytes(lines: list[str]) -> bytes:
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


CV_A = [
    "Ada Okafor",
    "Senior Machine Learning Engineer",
    "ada@example.com | London, United Kingdom",
    "Machine learning engineer specialising in fraud detection and model evaluation.",
    "Machine Learning Engineer | Fintech Systems | 2020 - Present",
    "Built and deployed classification models for transaction fraud detection.",
    "MSc Data Science | University of Edinburgh",
    "Python, SQL, Machine Learning, Statistics, Docker",
]

CV_B = [
    "Ada Okafor",
    "Junior Reporting Analyst",
    "ada@example.com | Manchester, United Kingdom",
    "Reporting analyst producing weekly dashboards and reporting packs.",
    "Reporting Analyst | Retail Insight | 2023 - Present",
    "Produced weekly sales dashboards in Excel and Tableau every Monday.",
    "BSc Statistics | University of Leeds",
    "Excel, Tableau, Power BI",
]


def _jsearch_job(provider_job_id: str = "probe-1", **overrides) -> JSearchJob:
    payload = dict(
        provider_job_id=provider_job_id,
        title="Senior Machine Learning Engineer",
        company="Fintech Systems",
        location="London, United Kingdom",
        description=(
            "Required: Python, Machine Learning, 5+ years of experience building "
            "and deploying models in production."
        ),
        apply_url=f"https://jobs.example.com/apply/{provider_job_id}",
        posted_at=datetime(2024, 1, 15, 10, 0, 0),
        salary_min=80000.0,
        salary_max=120000.0,
        salary_currency="USD",
        employment_type="FULLTIME",
        remote_status="REMOTE",
    )
    payload.update(overrides)
    return JSearchJob(**payload)


@pytest.fixture
def candidate(db):
    """Shared Candidate evidence, unlike either profile."""
    record = Candidate(
        name="Legacy Candidate",
        professional_title="Legacy Title",
        location="Legacy City",
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def _profile(client, lines, filename, label, *, confirm=True):
    created = client.post(
        "/api/v1/cv-profiles",
        files={"file": (filename, _docx_bytes(lines), _DOCX_MIME)},
        data={"label": label},
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    assert client.post(f"/api/v1/cv-profiles/{pid}/extract").status_code == 200
    if confirm:
        assert client.post(f"/api/v1/cv-profiles/{pid}/confirm", json={}).status_code == 200
    return pid


@pytest.fixture
def profile_a(client):
    return _profile(client, CV_A, "a.docx", "Profile A")


@pytest.fixture
def profile_b(client):
    return _profile(client, CV_B, "b.docx", "Profile B")


def _discover(client, body: dict):
    with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
        mock_search.return_value = [_jsearch_job()]
        return client.post("/api/v1/jobs/discover", json=body), mock_search


# ------------------------------------------------------------------ request


class TestDiscoveredJobSerialization:
    """Regression: POST /jobs/discover used to 500 on any non-empty result.

    Every pre-existing HTTP-level test mocked out discover_jobs entirely, so the
    real serializer was never exercised and _job_to_dict omitted the
    created_at/updated_at that JobOut requires.
    """

    def test_non_empty_discovery_response_serialises(self, client, db, candidate):
        response, _ = _discover(client, {"query": "data scientist", "country": "ng"})
        assert response.status_code == 200, response.text
        job = response.json()["jobs"][0]["job"]
        assert job["created_at"] is not None
        assert job["updated_at"] is not None

    def test_job_payload_meets_the_job_out_contract(self, client, db, candidate):
        from app.schemas import JobOut

        response, _ = _discover(client, {"query": "data scientist", "country": "ng"})
        payload = response.json()["jobs"][0]["job"]
        validated = JobOut.model_validate(payload)
        assert validated.id == payload["id"]
        assert validated.title == payload["title"]

    def test_multiple_results_all_serialise(self, client, db, candidate):
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = [
                _jsearch_job("probe-1"),
                _jsearch_job("probe-2", title="Data Analyst", company="Kuda"),
            ]
            response = client.post(
                "/api/v1/jobs/discover", json={"query": "data", "country": "ng"}
            )
        assert response.status_code == 200, response.text
        assert response.json()["total"] == 2


class TestDiscoveryRequestCompatibility:
    def test_legacy_request_without_profile_still_works(self, client, db, candidate):
        response, _ = _discover(client, {"query": "data scientist", "country": "ng"})
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["total"] == 1
        assert body["jobs"][0]["match"]["cv_profile_id"] is None

    def test_response_shape_is_unchanged(self, client, db, candidate):
        response, _ = _discover(client, {"query": "data scientist", "country": "ng"})
        body = response.json()
        assert set(body) == {"jobs", "total", "query", "country"}
        item = body["jobs"][0]
        for key in (
            "job",
            "match",
            "shortlisted",
            "search_relevance",
            "freshness",
            "duplicate_review",
        ):
            assert key in item, key

    def test_no_profile_content_is_sent_to_the_provider(
        self, client, db, candidate, profile_a
    ):
        """Only search parameters may leave the system."""
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = [_jsearch_job()]
            client.post(
                "/api/v1/jobs/discover",
                json={"query": "data scientist", "country": "ng", "cv_profile_id": profile_a},
            )
        assert mock_search.called
        sent = mock_search.call_args
        flattened = repr(sent)
        for leak in ("Ada", "Okafor", "ada@example.com", "Python", "docker"):
            assert leak not in flattened, leak
        # The only data handed to the provider is the search parameters.
        assert sent.kwargs["query"] == "data scientist"
        assert sent.kwargs["country"] == "ng"

    def test_invalid_country_still_rejected(self, client, db, candidate):
        with patch("app.services.job_discovery.search_jsearch_jobs"):
            response = client.post(
                "/api/v1/jobs/discover", json={"query": "x", "country": "NGA"}
            )
        assert response.status_code == 422 or response.status_code == 400


# -------------------------------------------------------------- provenance


class TestDiscoveryProvenance:
    def test_profile_discovery_stamps_the_profile(self, client, db, candidate, profile_a):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        assert response.status_code == 200, response.text
        assert response.json()["jobs"][0]["match"]["cv_profile_id"] == profile_a

    def test_stored_match_carries_the_profile(self, client, db, candidate, profile_a):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        match_id = response.json()["jobs"][0]["match"]["id"]
        assert db.get(MatchResult, match_id).cv_profile_id == profile_a

    def test_profile_discovery_uses_that_profiles_evidence(
        self, client, db, candidate, profile_b
    ):
        """Profile B lacks the required skills, so the score must reflect that."""
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_b}
        )
        match = response.json()["jobs"][0]["match"]
        assert "Python" not in {i["name"] for i in match["matched_items"]}

    def test_two_profiles_produce_independent_matches(
        self, client, db, candidate, profile_a, profile_b
    ):
        first, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        second, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_b}
        )
        job_id = first.json()["jobs"][0]["job"]["id"]
        assert job_id == second.json()["jobs"][0]["job"]["id"]

        a = first.json()["jobs"][0]["match"]
        b = second.json()["jobs"][0]["match"]
        assert a["id"] != b["id"]
        assert a["cv_profile_id"] == profile_a
        assert b["cv_profile_id"] == profile_b
        # Two rows, both retained.
        assert (
            db.query(MatchResult).filter_by(job_id=job_id).count() == 2
        )

    def test_legacy_and_profile_matches_coexist(
        self, client, db, candidate, profile_a
    ):
        _discover(client, {"query": "data scientist", "country": "ng"})
        _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = db.query(MatchResult).filter_by(cv_profile_id=profile_a).one().job_id
        rows = db.query(MatchResult).filter_by(job_id=job_id).all()
        assert {r.cv_profile_id for r in rows} == {None, profile_a}

    def test_missing_profile_is_rejected(self, client, db, candidate):
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            response = client.post(
                "/api/v1/jobs/discover",
                json={"query": "data scientist", "country": "ng", "cv_profile_id": 999999},
            )
        assert response.status_code == 404
        assert not mock_search.called, "no provider call may be made for a rejected request"

    def test_absent_profile_key_is_the_legacy_path(self, client, db, candidate):
        """An omitted key must behave exactly like omitting the whole request."""
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            mock_search.return_value = [_jsearch_job()]
            response = client.post(
                "/api/v1/jobs/discover", json={"query": "data scientist", "country": "ng"}
            )
            assert mock_search.called
        assert response.status_code == 200, response.text
        assert response.json()["jobs"][0]["match"]["cv_profile_id"] is None

    def test_unowned_profile_is_rejected(self, client, db, candidate, profile_a):
        from app.models import CVProfile

        other = Candidate(name="Someone Else")
        db.add(other)
        db.commit()
        db.refresh(other)
        db.get(CVProfile, profile_a).candidate_id = other.id
        db.commit()

        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            response = client.post(
                "/api/v1/jobs/discover",
                json={"query": "x", "country": "ng", "cv_profile_id": profile_a},
            )
        assert response.status_code == 404
        assert not mock_search.called

    def test_unconfirmed_profile_is_rejected(self, client, db, candidate):
        pending = _profile(client, CV_A, "p.docx", "Pending", confirm=False)
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            response = client.post(
                "/api/v1/jobs/discover",
                json={"query": "x", "country": "ng", "cv_profile_id": pending},
            )
        assert response.status_code == 409
        assert not mock_search.called

    def test_archived_profile_is_rejected(self, client, db, candidate, profile_a):
        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            response = client.post(
                "/api/v1/jobs/discover",
                json={"query": "x", "country": "ng", "cv_profile_id": profile_a},
            )
        assert response.status_code == 409
        assert not mock_search.called

    def test_rejected_profile_creates_no_match(self, client, db, candidate):
        before = db.query(MatchResult).count()
        with patch("app.services.job_discovery.search_jsearch_jobs") as mock_search:
            client.post(
                "/api/v1/jobs/discover",
                json={"query": "x", "country": "ng", "cv_profile_id": 999999},
            )
            assert not mock_search.called
        assert db.query(MatchResult).count() == before


# ------------------------------------------------------- detail provenance


class TestDiscoveredDetailProvenance:
    def test_detail_returns_the_requested_profile_match(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        detail = client.get(
            f"/api/v1/jobs/discovered/{job_id}", params={"cv_profile_id": profile_a}
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["match"]["cv_profile_id"] == profile_a

    def test_detail_never_returns_another_profiles_match(
        self, client, db, candidate, profile_a, profile_b
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]

        detail = client.get(
            f"/api/v1/jobs/discovered/{job_id}", params={"cv_profile_id": profile_b}
        ).json()
        # Profile B was never matched here: no fallback to A's or the legacy row.
        assert detail["match"] is None

    def test_detail_legacy_behaviour_unchanged(self, client, db, candidate, profile_a):
        response, _ = _discover(client, {"query": "data scientist", "country": "ng"})
        job_id = response.json()["jobs"][0]["job"]["id"]
        _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        detail = client.get(f"/api/v1/jobs/discovered/{job_id}").json()
        assert detail["match"]["cv_profile_id"] is None

    def test_detail_serializes_item_collections_as_lists(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        match = client.get(
            f"/api/v1/jobs/discovered/{job_id}", params={"cv_profile_id": profile_a}
        ).json()["match"]
        for key in ("matched_items", "gap_items", "blocker_items", "unknown_items"):
            assert isinstance(match[key], list), key
            for item in match[key]:
                assert set(item) == {"category", "name", "detail", "importance"}

    def test_detail_preserves_url_source_and_signals(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        item = response.json()["jobs"][0]
        assert item["job"]["url"] == "https://jobs.example.com/apply/probe-1"
        assert item["job"]["source"] == "jsearch"
        assert item["job"]["source_id"] == "probe-1"
        assert item["job"]["external_id"] == "jsearch:probe-1"
        assert item["search_relevance"]["label"]
        assert item["search_relevance"]["reason"]
        assert item["freshness"]["status"]
        assert "duplicate_review" in item

        job_id = item["job"]["id"]
        detail = client.get(
            f"/api/v1/jobs/discovered/{job_id}",
            params={"cv_profile_id": profile_a, "query": "data scientist"},
        ).json()
        assert detail["job"]["url"] == "https://jobs.example.com/apply/probe-1"
        # Relevance is the query-to-title signal, independent of the profile, and
        # must still be produced on a profile-scoped request.
        assert detail["search_relevance"]["label"] in {
            "Aligned",
            "Adjacent",
            "Mismatch",
            "Uncertain",
        }
        assert detail["search_relevance"]["reason"]
        assert detail["freshness"]["status"]
        assert detail["freshness"]["reason"]
        assert "duplicate_review" in detail

    def test_detail_unknown_profile_is_404(self, client, db, candidate):
        assert client.get(
            "/api/v1/jobs/discovered/1", params={"cv_profile_id": 999999}
        ).status_code == 404

    def test_detail_unknown_job_is_404(self, client, db, candidate):
        assert client.get("/api/v1/jobs/discovered/999999").status_code == 404


# -------------------------------------------------------------- shortlisting


class TestShortlistProvenance:
    def test_legacy_shortlist_is_unchanged(self, client, db, candidate):
        response, _ = _discover(client, {"query": "data scientist", "country": "ng"})
        job_id = response.json()["jobs"][0]["job"]["id"]

        result = client.post(f"/api/v1/jobs/discovered/{job_id}/shortlist")
        assert result.status_code == 201, result.text
        body = result.json()
        assert body["cv_profile_id"] is None

        stored = db.get(Application, body["application_id"])
        assert stored.cv_profile_id is None
        assert stored.match_id is None

    def test_profile_shortlist_records_the_profile(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        match_id = response.json()["jobs"][0]["match"]["id"]

        result = client.post(
            f"/api/v1/jobs/discovered/{job_id}/shortlist",
            json={"cv_profile_id": profile_a},
        )
        assert result.status_code == 201, result.text
        body = result.json()
        assert body["cv_profile_id"] == profile_a

        stored = db.get(Application, body["application_id"])
        assert stored.cv_profile_id == profile_a
        assert stored.match_id == match_id

    def test_profile_shortlist_links_the_profiles_own_match(
        self, client, db, candidate, profile_a, profile_b
    ):
        first, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        match_a = first.json()["jobs"][0]["match"]["id"]
        _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_b}
        )
        job_id = first.json()["jobs"][0]["job"]["id"]

        body = client.post(
            f"/api/v1/jobs/discovered/{job_id}/shortlist",
            json={"cv_profile_id": profile_a},
        ).json()
        assert db.get(Application, body["application_id"]).match_id == match_a

    def test_shortlist_without_a_profile_match_is_a_conflict(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(client, {"query": "data scientist", "country": "ng"})
        job_id = response.json()["jobs"][0]["job"]["id"]

        result = client.post(
            f"/api/v1/jobs/discovered/{job_id}/shortlist",
            json={"cv_profile_id": profile_a},
        )
        assert result.status_code == 409
        assert db.query(Application).filter_by(job_id=job_id).count() == 0

    def test_repeated_profile_shortlist_is_idempotent(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        url = f"/api/v1/jobs/discovered/{job_id}/shortlist"

        first = client.post(url, json={"cv_profile_id": profile_a})
        second = client.post(url, json={"cv_profile_id": profile_a})
        assert first.status_code == 201
        assert second.status_code == 201
        assert second.json()["message"] == "Already shortlisted"
        assert first.json()["application_id"] == second.json()["application_id"]
        assert db.query(Application).filter_by(job_id=job_id).count() == 1

    def test_repeated_legacy_shortlist_is_idempotent(self, client, db, candidate):
        response, _ = _discover(client, {"query": "data scientist", "country": "ng"})
        job_id = response.json()["jobs"][0]["job"]["id"]
        url = f"/api/v1/jobs/discovered/{job_id}/shortlist"

        first = client.post(url)
        second = client.post(url)
        assert first.json()["application_id"] == second.json()["application_id"]
        assert db.query(Application).filter_by(job_id=job_id).count() == 1

    def test_conflicting_profile_is_rejected_and_not_reassigned(
        self, client, db, candidate, profile_a, profile_b
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_b}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        url = f"/api/v1/jobs/discovered/{job_id}/shortlist"

        first = client.post(url, json={"cv_profile_id": profile_a})
        conflict = client.post(url, json={"cv_profile_id": profile_b})
        assert conflict.status_code == 409
        assert "profile_a_marker" not in conflict.text

        stored = db.get(Application, first.json()["application_id"])
        assert stored.cv_profile_id == profile_a

    def test_legacy_shortlist_cannot_take_over_a_profile_application(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        url = f"/api/v1/jobs/discovered/{job_id}/shortlist"

        client.post(url, json={"cv_profile_id": profile_a})
        conflict = client.post(url)
        assert conflict.status_code == 409

    def test_profile_shortlist_cannot_take_over_a_legacy_application(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(client, {"query": "data scientist", "country": "ng"})
        job_id = response.json()["jobs"][0]["job"]["id"]
        url = f"/api/v1/jobs/discovered/{job_id}/shortlist"

        legacy = client.post(url)
        conflict = client.post(url, json={"cv_profile_id": profile_a})
        assert conflict.status_code == 409
        assert db.get(Application, legacy.json()["application_id"]).cv_profile_id is None

    def test_one_application_per_candidate_job_holds(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        client.post(
            f"/api/v1/jobs/discovered/{job_id}/shortlist", json={"cv_profile_id": profile_a}
        )
        assert db.query(Application).filter_by(job_id=job_id).count() == 1

    def test_shortlist_rejects_invalid_profiles(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        url = f"/api/v1/jobs/discovered/{job_id}/shortlist"

        assert client.post(url, json={"cv_profile_id": 999999}).status_code == 404
        pending = _profile(client, CV_A, "q.docx", "Q", confirm=False)
        assert client.post(url, json={"cv_profile_id": pending}).status_code == 409
        assert db.query(Application).filter_by(job_id=job_id).count() == 0

    def test_shortlist_unknown_job_is_404(self, client, db, candidate):
        assert client.post("/api/v1/jobs/discovered/999999/shortlist").status_code == 404

    def test_shortlisted_flag_reflects_existing_application(
        self, client, db, candidate, profile_a
    ):
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        assert (
            client.get(f"/api/v1/jobs/discovered/{job_id}").json()["shortlisted"] is False
        )
        client.post(
            f"/api/v1/jobs/discovered/{job_id}/shortlist", json={"cv_profile_id": profile_a}
        )
        assert client.get(f"/api/v1/jobs/discovered/{job_id}").json()["shortlisted"] is True

    def test_shortlist_does_not_claim_external_submission(
        self, client, db, candidate, profile_a
    ):
        """Shortlisting is interest, not a submission record."""
        response, _ = _discover(
            client, {"query": "data scientist", "country": "ng", "cv_profile_id": profile_a}
        )
        job_id = response.json()["jobs"][0]["job"]["id"]
        body = client.post(
            f"/api/v1/jobs/discovered/{job_id}/shortlist", json={"cv_profile_id": profile_a}
        ).json()
        stored = db.get(Application, body["application_id"])
        assert stored.status == "INTERESTED"
        assert stored.applied_at is None
