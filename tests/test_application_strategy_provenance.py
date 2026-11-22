"""Application and strategy provenance, completing the profile trace chain.

Isolated fixtures only. No external services, no live provider, no reliance on
development or production records.
"""

from __future__ import annotations

import io

import pytest
from app.models import (
    Application,
    ApplicationStatus,
    Candidate,
    Importance,
    Job,
    JobRequirement,
    RequirementType,
)
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


@pytest.fixture
def candidate(db):
    record = Candidate(name="Legacy Candidate", location="Legacy City")
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@pytest.fixture
def job(db):
    job = Job(
        title="Senior Machine Learning Engineer",
        company="Fintech Systems",
        location="London, United Kingdom",
        remote_status="HYBRID",
        description=(
            "Required: Python, Machine Learning, 5+ years of experience building "
            "and deploying models in production."
        ),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    for name, req_type, importance, years in (
        ("Python", RequirementType.SKILL, Importance.REQUIRED, None),
        ("Machine Learning", RequirementType.SKILL, Importance.REQUIRED, None),
        ("5+ years experience", RequirementType.EXPERIENCE, Importance.REQUIRED, 5.0),
    ):
        db.add(
            JobRequirement(
                job_id=job.id,
                requirement_type=req_type,
                name=name,
                importance=importance,
                years_required=years,
            )
        )
    db.commit()
    db.refresh(job)
    return job


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


def _match(client, job_id, profile_id=None):
    body = {"cv_profile_id": profile_id} if profile_id is not None else {}
    response = client.post(f"/api/v1/jobs/{job_id}/match", json=body)
    assert response.status_code == 200, response.text
    return response.json()


# ------------------------------------------------------ strategy provenance


class TestStrategyProvenance:
    def test_strategy_from_profile_records_the_profile(
        self, client, db, candidate, job, profile_a
    ):
        _match(client, job.id, profile_a)
        response = client.get(
            f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a}
        )
        assert response.status_code == 200, response.text
        assert response.json()["cv_profile_id"] == profile_a

    def test_stored_strategy_row_records_the_profile(
        self, client, db, candidate, job, profile_a
    ):
        _match(client, job.id, profile_a)
        client.get(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a})

        from app.models import ApplicationStrategy

        rows = db.query(ApplicationStrategy).filter_by(cv_profile_id=profile_a).all()
        assert len(rows) == 1
        assert rows[0].status == "CURRENT"

    def test_two_profiles_get_independent_strategies(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        _match(client, job.id, profile_a)
        _match(client, job.id, profile_b)

        a = client.get(
            f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a}
        ).json()
        b = client.get(
            f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_b}
        ).json()

        assert a["id"] != b["id"]
        assert a["cv_profile_id"] == profile_a
        assert b["cv_profile_id"] == profile_b

    def test_one_profile_never_marks_the_other_stale(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        """Two independent chains, not one CURRENT slot they fight over."""
        _match(client, job.id, profile_a)
        _match(client, job.id, profile_b)
        client.get(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a})
        client.get(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_b})

        from app.models import ApplicationStrategy

        a = db.query(ApplicationStrategy).filter_by(cv_profile_id=profile_a).all()
        b = db.query(ApplicationStrategy).filter_by(cv_profile_id=profile_b).all()
        assert all(r.status == "CURRENT" for r in a)
        assert all(r.status == "CURRENT" for r in b)
        # Independent version counters.
        assert [r.version for r in a] == [1]
        assert [r.version for r in b] == [1]

    def test_profile_specific_strategy_is_never_returned_to_a_legacy_request(
        self, client, db, candidate, job, profile_a
    ):
        _match(client, job.id, profile_a)
        client.get(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a})

        # No legacy match exists, so a legacy request must not fall back to it.
        assert client.get(f"/api/v1/jobs/{job.id}/strategy").status_code == 409

        _match(client, job.id)
        legacy = client.get(f"/api/v1/jobs/{job.id}/strategy").json()
        assert legacy["cv_profile_id"] is None
        assert legacy["id"] != _only_profile_strategy_id(db, profile_a)

    def test_rebuild_preserves_profile_identity(
        self, client, db, candidate, job, profile_a
    ):
        _match(client, job.id, profile_a)
        first = client.get(
            f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a}
        ).json()
        rebuilt = client.post(
            f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a}
        ).json()
        assert rebuilt["cv_profile_id"] == profile_a
        assert rebuilt["id"] != first["id"]
        assert rebuilt["version"] == first["version"] + 1
        # History preserved: the earlier version is retained as STALE.
        from app.models import ApplicationStrategy

        rows = (
            db.query(ApplicationStrategy)
            .filter_by(cv_profile_id=profile_a)
            .all()
        )
        assert len(rows) == 2
        assert sorted(r.version for r in rows) == [1, 2]

    def test_strategy_history_is_scoped_and_preserved(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        _match(client, job.id, profile_a)
        _match(client, job.id, profile_b)
        for pid in (profile_a, profile_b):
            client.get(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": pid})
            client.post(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": pid})

        hist_a = client.get(
            f"/api/v1/jobs/{job.id}/strategy/history", params={"cv_profile_id": profile_a}
        ).json()
        hist_b = client.get(
            f"/api/v1/jobs/{job.id}/strategy/history", params={"cv_profile_id": profile_b}
        ).json()
        assert {h["cv_profile_id"] for h in hist_a} == {profile_a}
        assert {h["cv_profile_id"] for h in hist_b} == {profile_b}
        assert len(hist_a) == len(hist_b) == 2

    def test_legacy_strategy_creation_and_retrieval_unchanged(
        self, client, db, candidate, job
    ):
        _match(client, job.id)
        legacy = client.get(f"/api/v1/jobs/{job.id}/strategy").json()
        assert legacy["cv_profile_id"] is None

        rebuilt = client.post(f"/api/v1/jobs/{job.id}/strategy").json()
        assert rebuilt["cv_profile_id"] is None
        assert rebuilt["version"] == legacy["version"] + 1

    def test_unconfirmed_profile_is_rejected(
        self, client, db, candidate, job
    ):
        pending = _profile(client, CV_A, "p.docx", "Pending", confirm=False)
        _match(client, job.id)
        response = client.get(
            f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": pending}
        )
        assert response.status_code == 409

    def test_archived_profile_is_rejected(
        self, client, db, candidate, job, profile_a
    ):
        _match(client, job.id, profile_a)
        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")
        response = client.get(
            f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a}
        )
        assert response.status_code == 409

    def test_unknown_profile_is_rejected(self, client, db, candidate, job):
        assert client.get(
            f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": 999999}
        ).status_code == 404

    def test_history_checks_ownership(self, client, db, candidate, job):
        assert client.get(
            f"/api/v1/jobs/{job.id}/strategy/history",
            params={"cv_profile_id": 999999},
        ).status_code == 404

    def test_history_of_another_candidates_profile_is_not_readable(
        self, client, db, candidate, job, profile_a
    ):
        from app.models import CVProfile

        _match(client, job.id, profile_a)
        client.get(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a})

        other = Candidate(name="Someone Else")
        db.add(other)
        db.commit()
        db.refresh(other)
        row = db.get(CVProfile, profile_a)
        row.candidate_id = other.id
        db.commit()

        response = client.get(
            f"/api/v1/jobs/{job.id}/strategy/history",
            params={"cv_profile_id": profile_a},
        )
        assert response.status_code == 404

    def test_archived_profile_history_remains_readable(
        self, client, db, candidate, job, profile_a
    ):
        """Archival retires a profile; it must not erase readable history."""
        _match(client, job.id, profile_a)
        client.get(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a})
        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")

        response = client.get(
            f"/api/v1/jobs/{job.id}/strategy/history",
            params={"cv_profile_id": profile_a},
        )
        assert response.status_code == 200, response.text
        assert len(response.json()) == 1
        assert response.json()[0]["cv_profile_id"] == profile_a

    def test_fingerprint_reflects_the_profile_evidence(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        """Different profile evidence must produce different fingerprints."""
        from app.services import cv_profile as profile_service
        from app.services import strategy as strategy_service

        fingerprints = set()
        for pid in (profile_a, profile_b):
            _p, data = profile_service.resolve_confirmed_profile(
                db, candidate, pid
            )
            summary = profile_service.to_profile_summary(data, pid)
            fingerprints.add(strategy_service.evidence_fingerprint(summary, job))
        assert len(fingerprints) == 2

    def test_profile_aware_generation_does_not_disturb_the_legacy_strategy(
        self, client, db, candidate, job, profile_a
    ):
        _match(client, job.id)
        legacy = client.get(f"/api/v1/jobs/{job.id}/strategy").json()

        _match(client, job.id, profile_a)
        client.post(f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a})

        after = client.get(f"/api/v1/jobs/{job.id}/strategy").json()
        assert after["id"] == legacy["id"]
        assert after["status"] == "CURRENT"
        assert after["cv_profile_id"] is None


def _only_profile_strategy_id(db, profile_id) -> int:
    from app.models import ApplicationStrategy

    return db.query(ApplicationStrategy).filter_by(cv_profile_id=profile_id).one().id


# --------------------------------------------------- application provenance


class TestApplicationProvenance:
    def test_explicit_profile_is_recorded(self, client, db, candidate, job, profile_a):
        _match(client, job.id, profile_a)
        response = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        )
        assert response.status_code == 201, response.text
        assert response.json()["cv_profile_id"] == profile_a

    def test_stored_row_records_the_profile(
        self, client, db, candidate, job, profile_a
    ):
        _match(client, job.id, profile_a)
        created = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        ).json()
        assert db.get(Application, created["id"]).cv_profile_id == profile_a

    def test_provenance_links_the_profile_own_match(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        match_a = _match(client, job.id, profile_a)
        _match(client, job.id, profile_b)
        created = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        ).json()
        # The auto-resolved match must be the profile's own, not the newest one.
        assert created["match_id"] == match_a["id"]

    def test_provenance_is_inferred_from_a_consistent_artefact(
        self, client, db, candidate, job, profile_a
    ):
        match_a = _match(client, job.id, profile_a)
        created = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "match_id": match_a["id"]},
        )
        assert created.status_code == 201, created.text
        assert created.json()["cv_profile_id"] == profile_a

    def test_conflicting_artefacts_are_rejected(self, client, db, candidate, job, profile_a, profile_b):
        match_a = _match(client, job.id, profile_a)
        doc_b = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_b}
        ).json()
        response = client.post(
            "/api/v1/applications",
            json={
                "job_id": job.id,
                "match_id": match_a["id"],
                "tailored_cv_id": doc_b["id"],
            },
        )
        assert response.status_code == 409

    def test_requested_profile_conflicting_with_artefact_is_rejected(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        match_b = _match(client, job.id, profile_b)
        response = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "match_id": match_b["id"], "cv_profile_id": profile_a},
        )
        assert response.status_code == 409

    def test_legacy_application_has_null_provenance(self, client, db, candidate, job):
        _match(client, job.id)
        response = client.post("/api/v1/applications", json={"job_id": job.id})
        assert response.status_code == 201, response.text
        assert response.json()["cv_profile_id"] is None

    def test_existing_application_is_not_silently_reassigned(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        """A second profile must not take over the tracked application."""
        _match(client, job.id, profile_a)
        first = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        ).json()

        _match(client, job.id, profile_b)
        second = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_b},
        )
        assert second.status_code == 409
        assert db.get(Application, first["id"]).cv_profile_id == profile_a

    def test_duplicate_reports_the_existing_profile(
        self, client, db, candidate, job, profile_a
    ):
        _match(client, job.id, profile_a)
        client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        )
        again = client.post("/api/v1/applications", json={"job_id": job.id})
        assert again.status_code == 409
        assert str(profile_a) in again.json()["detail"]

    def test_one_application_per_candidate_job_holds(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        from sqlalchemy.exc import IntegrityError

        _match(client, job.id, profile_a)
        client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        )
        with pytest.raises(IntegrityError):
            db.add(
                Application(
                    candidate_id=candidate.id,
                    job_id=job.id,
                    cv_profile_id=profile_b,
                    status=ApplicationStatus.INTERESTED.value,
                )
            )
            db.commit()
        db.rollback()

    def test_two_profiles_do_not_produce_two_applications(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        _match(client, job.id, profile_a)
        _match(client, job.id, profile_b)
        client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        )
        assert (
            client.post(
                "/api/v1/applications",
                json={"job_id": job.id, "cv_profile_id": profile_b},
            ).status_code
            == 409
        )
        assert db.query(Application).filter_by(job_id=job.id).count() == 1

    def test_provenance_can_be_assigned_once_while_null(
        self, client, db, candidate, job, profile_a
    ):
        created = client.post(
            "/api/v1/applications", json={"job_id": job.id}
        ).json()
        assert created["cv_profile_id"] is None

        updated = client.put(
            f"/api/v1/applications/{created['id']}", json={"cv_profile_id": profile_a}
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["cv_profile_id"] == profile_a

    def test_provenance_is_never_overwritten(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        created = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        ).json()
        response = client.put(
            f"/api/v1/applications/{created['id']}", json={"cv_profile_id": profile_b}
        )
        assert response.status_code == 409
        assert db.get(Application, created["id"]).cv_profile_id == profile_a

    def test_attaching_a_conflicting_document_is_rejected(
        self, client, db, candidate, job, profile_a, profile_b
    ):
        created = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        ).json()
        doc_b = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_b}
        ).json()
        response = client.put(
            f"/api/v1/applications/{created['id']}",
            json={"tailored_cv_id": doc_b["id"]},
        )
        assert response.status_code == 409

    def test_unconfirmed_profile_is_rejected(self, client, db, candidate, job):
        pending = _profile(client, CV_A, "p.docx", "Pending", confirm=False)
        response = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": pending},
        )
        assert response.status_code == 409

    def test_archived_profile_is_rejected(self, client, db, candidate, job, profile_a):
        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")
        response = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        )
        assert response.status_code == 409

    def test_unknown_profile_is_rejected(self, client, db, candidate, job):
        response = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": 999999},
        )
        assert response.status_code == 404

    def test_application_without_documents_is_allowed(
        self, client, db, candidate, job, profile_a
    ):
        """Documents are optional; provenance must not require them."""
        created = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        ).json()
        assert created["tailored_cv_id"] is None
        assert created["cover_letter_id"] is None
        assert created["cv_profile_id"] == profile_a

    def test_status_and_applied_at_still_work(self, client, db, candidate, job, profile_a):
        created = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        ).json()
        updated = client.put(
            f"/api/v1/applications/{created['id']}", json={"status": "APPLIED"}
        ).json()
        assert updated["status"] == "APPLIED"
        assert updated["applied_at"] is not None
        assert updated["cv_profile_id"] == profile_a


# -------------------------------------------------------- lifecycle safety


class TestLifecycleSafety:
    def test_archiving_preserves_application_and_strategy_provenance(
        self, client, db, candidate, job, profile_a
    ):
        _match(client, job.id, profile_a)
        client.get(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a})
        application = client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        ).json()

        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")

        from app.models import ApplicationStrategy

        assert db.get(Application, application["id"]).cv_profile_id == profile_a
        assert (
            db.query(ApplicationStrategy).filter_by(cv_profile_id=profile_a).count() == 1
        )

    def test_hard_delete_is_refused_with_dependent_history(
        self, client, db, candidate, job, profile_a
    ):
        from app.models import CVProfile
        from sqlalchemy.exc import IntegrityError

        _match(client, job.id, profile_a)
        client.get(f"/api/v1/jobs/{job.id}/strategy", params={"cv_profile_id": profile_a})
        client.post(
            "/api/v1/applications",
            json={"job_id": job.id, "cv_profile_id": profile_a},
        )
        with pytest.raises(IntegrityError):
            db.query(CVProfile).filter(CVProfile.id == profile_a).delete()
            db.commit()
        db.rollback()
        assert db.get(CVProfile, profile_a) is not None

    def test_historical_application_keeps_null_provenance(
        self, db, candidate, job
    ):
        legacy = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status=ApplicationStatus.INTERESTED.value,
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        assert legacy.cv_profile_id is None

    def test_historical_strategy_keeps_null_provenance(self, db, candidate, job):
        from app.models import ApplicationStrategy

        legacy = ApplicationStrategy(
            candidate_id=candidate.id,
            job_id=job.id,
            version=1,
            status="CURRENT",
            decision="APPLY_WITH_TAILORING",
        )
        db.add(legacy)
        db.commit()
        db.refresh(legacy)
        assert legacy.cv_profile_id is None


# ---------------------------------------------------------------- migration


class TestMigrationSafety:
    def test_migration_is_additive_and_chained(self):
        import pathlib
        import re

        new = pathlib.Path(
            "migrations/versions/f7a8b9c0d1e2_application_and_strategy_provenance.py"
        )
        assert new.exists(), "migration file missing"
        text = new.read_text()
        assert re.search(r"^revision = 'f7a8b9c0d1e2'", text, re.M)
        assert re.search(r"^down_revision = 'e6f7a8b9c0d1'", text, re.M)
        up = text.split("def upgrade")[1].split("def downgrade")[0]
        assert up.count("op.add_column") == 2
        assert up.count("ondelete='RESTRICT'") == 2
        for verb in ("drop_constraint", "drop_table", "op.execute", "bulk_insert",
                     "op.delete", "create_unique_constraint"):
            assert verb not in up, verb

    def test_upgrade_and_downgrade_on_an_isolated_database(self):
        import os
        import subprocess
        import sys

        from sqlalchemy import create_engine, text

        admin_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+psycopg://career:career@localhost:5433/career_test",
        )
        scratch = "career_migration_v37"
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
                for table in ("applications", "application_strategies"):
                    assert "cv_profile_id" in {
                        r[0]
                        for r in connection.execute(text(
                            "select column_name from information_schema.columns "
                            "where table_name=:t"
                        ), {"t": table})
                    }, table
                # The one-application-per-candidate/job rule must survive.
                uniques = [
                    r[0]
                    for r in connection.execute(text(
                        "select pg_get_constraintdef(oid) from pg_constraint "
                        "where conrelid='applications'::regclass and contype='u'"
                    ))
                ]
                assert len(uniques) == 1, uniques
                assert "candidate_id" in uniques[0] and "job_id" in uniques[0]
                # All five provenance FKs RESTRICT, across every table that carries one.
                fks = [
                    r[0]
                    for r in connection.execute(text(
                        "select conrelid::regclass::text || ' :: ' || "
                        "pg_get_constraintdef(oid) from pg_constraint "
                        "where contype='f' and pg_get_constraintdef(oid) like '%cv_profiles%'"
                    ))
                ]
                assert len(fks) == 5, fks
                assert all("ON DELETE RESTRICT" in f for f in fks), fks
                tables = {f.split(" :: ")[0] for f in fks}
                assert tables == {
                    "applications",
                    "application_strategies",
                    "cover_letters",
                    "match_results",
                    "tailored_cvs",
                }, tables
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
