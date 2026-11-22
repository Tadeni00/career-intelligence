"""Explicit CV-profile-aware matching and result provenance.

Every fixture is built inside the isolated test database. These tests never read
or depend on development or production match, profile or job records, and never
call an external provider.
"""

from __future__ import annotations

import io

import pytest
from docx import Document

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _docx_bytes(lines: list[str]) -> bytes:
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


# Two deliberately different CVs for the same person. Profile A is a strong ML
# engineer; profile B is a junior reporting analyst with almost no overlap. The
# difference is real fixture data, not an adjusted score.
CV_A = [
    "Ada Okafor",
    "Senior Machine Learning Engineer",
    "ada@example.com | London, United Kingdom",
    "Machine learning engineer specialising in fraud detection and model evaluation.",
    "Machine Learning Engineer | Fintech Systems | 2020 - Present",
    "Built and deployed classification models for transaction fraud detection.",
    "Senior Machine Learning Engineer | Analytics Works | 2017 - 2020",
    "Developed statistical models for customer segmentation using Python and SQL.",
    "MSc Data Science | University of Edinburgh",
    "Python, SQL, Machine Learning, Statistics, Model Evaluation, FastAPI, Docker",
]

CV_B = [
    "Ada Okafor",
    "Junior Reporting Analyst",
    "ada@example.com | Manchester, United Kingdom",
    "Reporting analyst producing weekly dashboards and spreadsheets.",
    "Reporting Analyst | Retail Insight | 2023 - Present",
    "Produced weekly sales dashboards in Excel and Tableau.",
    "BSc Statistics | University of Leeds",
    "Excel, Tableau, Power BI, SQL",
]


# --------------------------------------------------------------- fixtures


@pytest.fixture
def candidate_with_evidence(db):
    """A candidate with confirmed evidence on the shared record."""
    from app.models import Candidate, CandidateSkill, Experience, Skill

    candidate = Candidate(
        name="Ada Okafor",
        professional_title="Senior Machine Learning Engineer",
        location="London, United Kingdom",
        summary="Machine learning engineer specialising in fraud detection.",
        years_of_experience=9.0,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    for name in ("Python", "SQL", "Machine Learning"):
        skill = Skill(name=name, category="TECHNICAL")
        db.add(skill)
        db.commit()
        db.refresh(skill)
        db.add(CandidateSkill(candidate_id=candidate.id, skill_id=skill.id))

    db.add(
        Experience(
            candidate_id=candidate.id,
            company="Fintech Systems",
            title="Machine Learning Engineer",
            start_date="2020-01-01",
            is_current=True,
        )
    )
    db.commit()
    db.refresh(candidate)
    return candidate


def _profile(client, lines, filename, label, *, confirm=True):
    files = {"file": (filename, _docx_bytes(lines), _DOCX_MIME)}
    created = client.post("/api/v1/cv-profiles", files=files, data={"label": label})
    assert created.status_code == 201, created.text
    profile_id = created.json()["id"]
    extracted = client.post(f"/api/v1/cv-profiles/{profile_id}/extract")
    assert extracted.status_code == 200, extracted.text
    if confirm:
        confirmed = client.post(f"/api/v1/cv-profiles/{profile_id}/confirm", json={})
        assert confirmed.status_code == 200, confirmed.text
    return profile_id


@pytest.fixture
def job(db):
    from app.models import Importance, Job, JobRequirement, RequirementType

    job = Job(
        title="Senior Machine Learning Engineer",
        company="Fintech Systems",
        location="London, United Kingdom",
        remote_status="HYBRID",
        description="Required: Python, Machine Learning, 5+ years of experience.",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    for name, req_type, importance in (
        ("Python", RequirementType.SKILL, Importance.REQUIRED),
        ("Machine Learning", RequirementType.SKILL, Importance.REQUIRED),
        ("Docker", RequirementType.SKILL, Importance.PREFERRED),
        ("5+ years experience", RequirementType.EXPERIENCE, Importance.REQUIRED),
    ):
        db.add(
            JobRequirement(
                job_id=job.id,
                requirement_type=req_type,
                name=name,
                importance=importance,
                years_required=5.0 if "years" in name else None,
            )
        )
    from app.services import extraction as extraction_service

    db.commit()
    db.refresh(job)
    extraction_service.assert_matchable(job)
    return job


@pytest.fixture
def profile_a(client):
    return _profile(client, CV_A, "ml_cv.docx", "Profile A")


@pytest.fixture
def profile_b(client):
    return _profile(client, CV_B, "analyst_cv.docx", "Profile B")


# --------------------------------------------------- eligibility and input


class TestProfileEligibility:
    def test_confirmed_profile_a_is_accepted(self, client, db, candidate_with_evidence, job, profile_a):
        response = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        assert response.status_code == 200, response.text
        assert response.json()["cv_profile_id"] == profile_a

    def test_confirmed_profile_b_is_accepted(self, client, db, candidate_with_evidence, job, profile_b):
        response = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_b})
        assert response.status_code == 200, response.text
        assert response.json()["cv_profile_id"] == profile_b

    def test_unconfirmed_profile_is_rejected(self, client, db, candidate_with_evidence, job):
        pending = _profile(client, CV_A, "pending.docx", "Pending", confirm=False)
        response = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": pending})
        assert response.status_code == 409
        assert "not CONFIRMED" in response.json()["detail"]

    def test_extracted_but_unconfirmed_profile_is_rejected(self, client, db, candidate_with_evidence, job):
        created = client.post(
            "/api/v1/cv-profiles",
            files={"file": ("x.docx", _docx_bytes(CV_A), _DOCX_MIME)},
            data={"label": "X"},
        ).json()
        client.post(f"/api/v1/cv-profiles/{created['id']}/extract")
        response = client.post(
            f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": created["id"]}
        )
        assert response.status_code == 409

    def test_nonexistent_profile_is_rejected(self, client, db, candidate_with_evidence, job):
        response = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": 999999})
        assert response.status_code == 404

    def test_another_candidates_profile_is_not_accessible(self, client, db, candidate_with_evidence, job):
        from app.models import Candidate, CVProfile, CVProfileStatus
        from app.schemas import CVProfileData

        other = Candidate(name="Someone Else")
        db.add(other)
        db.commit()
        db.refresh(other)

        foreign = CVProfile(
            candidate_id=other.id,
            label="Foreign",
            status=CVProfileStatus.CONFIRMED.value,
            file_type="pdf",
            storage_path="/tmp/x.pdf",
            confirmed_data=CVProfileData(
                name="Someone Else", professional_title="Machine Learning Engineer"
            ).model_dump_json(),
        )
        db.add(foreign)
        db.commit()
        db.refresh(foreign)

        response = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": foreign.id})
        assert response.status_code == 404
        assert "Foreign" not in response.text

    def test_rejected_profile_creates_no_match(self, client, db, candidate_with_evidence, job):
        from app.models import MatchResult

        before = db.query(MatchResult).count()
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": 999999})
        pending = _profile(client, CV_A, "p.docx", "P", confirm=False)
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": pending})
        assert db.query(MatchResult).count() == before

    def test_error_does_not_fall_back_to_the_shared_candidate(
        self, client, db, candidate_with_evidence, job
    ):
        """A rejected profile must never silently produce a legacy match."""
        from app.models import MatchResult

        response = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": 999999})
        assert response.status_code == 404
        assert db.query(MatchResult).count() == 0

    def test_profile_input_does_not_read_the_shared_candidate(
        self, client, db, candidate_with_evidence, job
    ):
        """Profile B's score reflects Profile B, not the shared candidate's 9 years."""
        response = client.post(
            f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": _profile(client, CV_B, "b.docx", "B")}
        )
        assert response.status_code == 200
        body = response.json()
        # The shared candidate holds Python/SQL/ML and 9 years. Profile B has
        # none of the required skills, so the match must show that, not the
        # candidate's evidence.
        assert "Python" not in {item["name"] for item in body["matched_items"]}
        assert "Machine Learning" not in {item["name"] for item in body["matched_items"]}
        # The required skills Profile B lacks surface as its gaps.
        assert {"Python", "Machine Learning"} <= {
            item["name"] for item in body["gap_items"]
        }

    def test_profile_input_does_not_mutate_the_shared_candidate(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        before = (
            candidate_with_evidence.name,
            candidate_with_evidence.professional_title,
            candidate_with_evidence.years_of_experience,
            len(candidate_with_evidence.skills),
        )
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        db.expire_all()
        from app.models import Candidate

        after = db.get(Candidate, candidate_with_evidence.id)
        assert (
            after.name,
            after.professional_title,
            after.years_of_experience,
            len(after.skills),
        ) == before

    def test_null_years_of_experience_uses_the_engine_derivation(
        self, client, db, candidate_with_evidence, job
    ):
        """A profile with no confirmed years still matches; the engine derives."""
        profile_id = _profile(client, CV_A, "ml.docx", "A")
        response = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_id})
        assert response.status_code == 200
        confirmed = client.get(f"/api/v1/cv-profiles/{profile_id}").json()["confirmed"]
        assert confirmed["years_of_experience"] is None
        # A score was still produced, so the derivation path ran without error.
        assert response.json()["overall_score"] is not None


# ----------------------------------------------------- independent results


class TestIndependentResults:
    def test_both_profiles_match_the_same_job(self, client, db, candidate_with_evidence, job, profile_a, profile_b):
        first = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        second = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_b})
        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["id"] != second.json()["id"]

    def test_each_result_keeps_its_own_profile_identifier(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        a = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a}).json()
        b = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_b}).json()
        assert a["cv_profile_id"] == profile_a
        assert b["cv_profile_id"] == profile_b

    def test_different_profiles_produce_different_scores(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        a = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a}).json()
        b = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_b}).json()
        # Driven by the fixtures: A holds the required skills, B does not.
        assert a["technical_score"] > b["technical_score"]
        assert a["overall_score"] > b["overall_score"]

    def test_scores_match_the_stored_rows(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        from app.models import MatchResult

        a = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a}).json()
        b = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_b}).json()

        row_a = db.get(MatchResult, a["id"])
        row_b = db.get(MatchResult, b["id"])
        assert row_a.cv_profile_id == profile_a
        assert row_b.cv_profile_id == profile_b
        assert row_a.overall_score == a["overall_score"]
        assert row_b.overall_score == b["overall_score"]
        assert row_a.overall_score != row_b.overall_score

    def test_retrieving_profile_a_never_returns_profile_b(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_b})

        got_a = client.get(f"/api/v1/jobs/{job.id}/match", params={"cv_profile_id": profile_a}).json()
        got_b = client.get(f"/api/v1/jobs/{job.id}/match", params={"cv_profile_id": profile_b}).json()
        assert got_a["cv_profile_id"] == profile_a
        assert got_b["cv_profile_id"] == profile_b
        assert got_a["id"] != got_b["id"]

    def test_scoped_lookup_never_returns_a_legacy_result(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        legacy = client.post(f"/api/v1/jobs/{job.id}/match").json()
        scoped = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a}).json()
        assert legacy["cv_profile_id"] is None

        fetched = client.get(
            f"/api/v1/jobs/{job.id}/match", params={"cv_profile_id": profile_a}
        ).json()
        assert fetched["id"] == scoped["id"]
        assert fetched["id"] != legacy["id"]

    def test_scoped_lookup_404s_when_that_profile_never_matched(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        response = client.get(f"/api/v1/jobs/{job.id}/match", params={"cv_profile_id": profile_b})
        assert response.status_code == 404

    def test_scoped_lookup_rejects_another_candidates_profile(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        from app.models import Candidate, CVProfile, CVProfileStatus

        other = Candidate(name="Someone Else")
        db.add(other)
        db.commit()
        db.refresh(other)
        foreign = CVProfile(
            candidate_id=other.id,
            label="Foreign",
            status=CVProfileStatus.CONFIRMED.value,
            file_type="pdf",
            storage_path="/tmp/f.pdf",
        )
        db.add(foreign)
        db.commit()
        db.refresh(foreign)

        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        response = client.get(f"/api/v1/jobs/{job.id}/match", params={"cv_profile_id": foreign.id})
        assert response.status_code == 404

    def test_legacy_lookup_is_unchanged_by_a_newer_profile_result(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        """A legacy request keeps its meaning: newest result for the job."""
        legacy = client.post(f"/api/v1/jobs/{job.id}/match").json()
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})

        got = client.get(f"/api/v1/jobs/{job.id}/match").json()
        assert got["id"] == legacy["id"]

    def test_legacy_helper_can_still_find_the_legacy_result(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        from app.services.matching import latest_match

        client.post(f"/api/v1/jobs/{job.id}/match")
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        found = latest_match(db, job.id)
        assert found is not None
        assert found.cv_profile_id is None


# --------------------------------------------------------------- discovered


class TestDiscoveredJobDetailProvenance:
    def test_detail_supports_profile_scoped_lookup(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        job.is_discovered = True
        job.external_id = "jsearch:test-1"
        db.commit()

        a = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a}).json()
        b = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_b}).json()

        scoped = client.get(
            f"/api/v1/jobs/discovered/{job.id}", params={"cv_profile_id": profile_a}
        ).json()
        assert scoped["match"]["id"] == a["id"]
        assert scoped["match"]["cv_profile_id"] == profile_a

        scoped_b = client.get(
            f"/api/v1/jobs/discovered/{job.id}", params={"cv_profile_id": profile_b}
        ).json()
        assert scoped_b["match"]["id"] == b["id"]

    def test_detail_without_profile_keeps_legacy_behaviour(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        legacy = client.post(f"/api/v1/jobs/{job.id}/match").json()
        body = client.get(f"/api/v1/jobs/discovered/{job.id}").json()
        assert body["match"]["id"] == legacy["id"]
        assert body["match"]["cv_profile_id"] is None

    def test_detail_still_serializes_item_collections(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        """The Text-column decoding boundary stays intact with provenance added."""
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        match = client.get(
            f"/api/v1/jobs/discovered/{job.id}", params={"cv_profile_id": profile_a}
        ).json()["match"]
        for key in ("matched_items", "gap_items", "blocker_items", "unknown_items"):
            assert isinstance(match[key], list)
            for item in match[key]:
                assert set(item) == {"category", "name", "detail", "importance"}

    def test_detail_unknown_profile_is_404(self, client, db, candidate_with_evidence, job):
        assert client.get(
            f"/api/v1/jobs/discovered/{job.id}", params={"cv_profile_id": 999999}
        ).status_code == 404


# ------------------------------------------------------------- persistence


class TestProvenancePersistence:
    def test_provenance_survives_a_session_boundary(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        created = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a}).json()

        from app.db.session import SessionLocal
        from app.models import MatchResult

        fresh = SessionLocal()
        try:
            stored = fresh.get(MatchResult, created["id"])
            assert stored.cv_profile_id == profile_a
        finally:
            fresh.close()

    def test_historical_rows_keep_null_provenance(self, db, candidate_with_evidence, job):
        from app.api.routes.matches import _to_out
        from app.models import MatchResult

        legacy = MatchResult(
            candidate_id=candidate_with_evidence.id,
            job_id=job.id,
            technical_score=50.0,
            experience_score=50.0,
            education_score=50.0,
            location_score=50.0,
            other_score=50.0,
            overall_score=50.0,
            recommendation="STRETCH",
            confidence=0.5,
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        assert legacy.cv_profile_id is None
        assert _to_out(legacy).cv_profile_id is None

    def test_no_unique_constraint_blocks_two_profiles(
        self, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        from app.models import MatchResult
        from app.services import matching as matching_service

        matching_service.run_match(db, candidate_with_evidence, job, cv_profile_id=profile_a)
        matching_service.run_match(db, candidate_with_evidence, job, cv_profile_id=profile_b)
        matching_service.run_match(db, candidate_with_evidence, job)

        rows = db.query(MatchResult).filter(MatchResult.job_id == job.id).all()
        assert len(rows) == 3
        assert {r.cv_profile_id for r in rows} == {profile_a, profile_b, None}


# ----------------------------------------------------- policy and thresholds


class TestMatchingPolicyUnchanged:
    def test_legacy_match_still_uses_the_candidate_record(
        self, client, db, candidate_with_evidence, job
    ):
        body = client.post(f"/api/v1/jobs/{job.id}/match").json()
        assert body["cv_profile_id"] is None
        assert body["candidate_id"] == candidate_with_evidence.id

    def test_profile_match_reports_the_same_fields(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        legacy = client.post(f"/api/v1/jobs/{job.id}/match").json()
        scoped = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a}).json()
        for key in (
            "technical_score",
            "experience_score",
            "education_score",
            "location_score",
            "other_score",
            "overall_score",
            "recommendation",
            "confidence",
            "explanation",
        ):
            assert key in legacy and key in scoped

    def test_weights_and_thresholds_are_untouched(self):
        from app.services.matching import build_settings

        settings = build_settings()
        assert settings.weights.technical == 0.40
        assert settings.weights.experience == 0.25
        assert settings.weights.education == 0.10
        assert settings.weights.location == 0.10
        assert settings.weights.other == 0.15
        assert settings.policy.apply_threshold == 80.0
        assert settings.policy.apply_with_tailoring_threshold == 65.0
        assert settings.policy.stretch_threshold == 50.0

    def test_blocker_forces_skip_for_a_profile_match(
        self, client, db, candidate_with_evidence, job, profile_b
    ):
        """Profile B matches a London hybrid role from Manchester: still scored."""
        body = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_b}).json()
        assert body["recommendation"] in {"APPLY", "APPLY_WITH_TAILORING", "STRETCH", "SKIP"}
        if body["blocker_items"]:
            assert body["recommendation"] == "SKIP"


# ------------------------------------------------------------- migration


class TestMigrationSafety:
    def test_migration_is_additive_and_chained(self):
        import pathlib
        import re

        new = pathlib.Path("migrations/versions/d5e6f7a8b9c0_match_result_cv_profile.py")
        assert new.exists(), "migration file missing"
        text = new.read_text()
        assert re.search(r"^revision = 'd5e6f7a8b9c0'", text, re.M)
        assert re.search(r"^down_revision = 'c4d5e6f7a8b9'", text, re.M)
        upgrade = text.split("def upgrade")[1].split("def downgrade")[0]
        assert "op.drop_column" not in upgrade
        assert "op.drop_table" not in upgrade
        assert "op.execute" not in upgrade
        assert "bulk_insert" not in upgrade
        assert "op.add_column" in upgrade

    def test_migration_upgrades_and_downgrades_on_an_isolated_database(self):
        import os
        import subprocess
        import sys

        from sqlalchemy import create_engine, text

        admin_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+psycopg://career:career@localhost:5433/career_test",
        )
        scratch = "career_migration_v35"
        base_url = admin_url.rsplit("/", 1)[0] + "/postgres"

        admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
            connection.execute(text(f'CREATE DATABASE "{scratch}"'))
        admin.dispose()

        env = {**os.environ, "DATABASE_URL": admin_url.rsplit("/", 1)[0] + f"/{scratch}"}
        try:
            upgrade = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                capture_output=True, text=True, env=env,
            )
            assert upgrade.returncode == 0, upgrade.stderr[-2000:]

            engine = create_engine(env["DATABASE_URL"])
            with engine.connect() as connection:
                columns = {
                    row[0]
                    for row in connection.execute(
                        text(
                            "select column_name from information_schema.columns "
                            "where table_name='match_results'"
                        )
                    )
                }
                assert "cv_profile_id" in columns
                # No uniqueness rule was introduced.
                uniques = [
                    row[0]
                    for row in connection.execute(text(
                        "select conname from pg_constraint "
                        "where conrelid='match_results'::regclass and contype='u'"
                    ))
                ]
                assert uniques == []
            engine.dispose()

            downgrade = subprocess.run(
                [sys.executable, "-m", "alembic", "downgrade", "-1"],
                capture_output=True, text=True, env=env,
            )
            assert downgrade.returncode == 0, downgrade.stderr[-2000:]
        finally:
            admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
            with admin.connect() as connection:
                connection.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
            admin.dispose()

    def test_historical_matches_survive_the_migration_shape(self, db, candidate_with_evidence, job):
        """Existing rows keep every original field and gain a null profile."""
        from app.models import MatchResult

        row = MatchResult(
            candidate_id=candidate_with_evidence.id,
            job_id=job.id,
            technical_score=81.0,
            experience_score=60.0,
            education_score=55.0,
            location_score=20.0,
            other_score=70.0,
            overall_score=64.6,
            recommendation="STRETCH",
            confidence=0.9,
            matched_items="[]",
            gap_items="[]",
            blocker_items="[]",
            unknown_items="[]",
            explanation="legacy row",
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        assert row.overall_score == 64.6
        assert row.recommendation == "STRETCH"
        assert row.explanation == "legacy row"
        assert row.cv_profile_id is None
