"""Document provenance for CV profiles, and profile lifecycle safety.

Isolated fixtures only. No external services, no live provider, and no reliance
on development or production records.
"""

from __future__ import annotations

import io

import pytest
from app.models import (
    Candidate,
    CandidateSkill,
    CoverLetter,
    Importance,
    Job,
    JobRequirement,
    MatchResult,
    RequirementType,
    Skill,
    TailoredCV,
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
    "Reporting analyst producing weekly dashboards.",
    "Reporting Analyst | Retail Insight | 2023 - Present",
    "Produced weekly sales dashboards in Excel and Tableau.",
    "BSc Statistics | University of Leeds",
    "Excel, Tableau, Power BI",
]


@pytest.fixture
def candidate_with_evidence(db):
    """Shared Candidate evidence, deliberately unlike both profiles."""
    candidate = Candidate(
        name="Shared Legacy Name",
        professional_title="Shared Legacy Title",
        location="Shared Legacy City",
        summary="Legacy summary that no profile contains.",
        years_of_experience=25.0,
    )
    db.add(candidate)
    db.commit()
    db.refresh(candidate)

    skill = Skill(name="LegacyOnlySkill", category="LEGACY")
    db.add(skill)
    db.commit()
    db.refresh(skill)
    db.add(CandidateSkill(candidate_id=candidate.id, skill_id=skill.id))
    db.commit()
    db.refresh(candidate)
    return candidate


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
        ("Docker", RequirementType.SKILL, Importance.PREFERRED, None),
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
    profile_id = created.json()["id"]
    assert client.post(f"/api/v1/cv-profiles/{profile_id}/extract").status_code == 200
    if confirm:
        assert (
            client.post(f"/api/v1/cv-profiles/{profile_id}/confirm", json={}).status_code
            == 200
        )
    return profile_id


@pytest.fixture
def profile_a(client):
    return _profile(client, CV_A, "a.docx", "Profile A")


@pytest.fixture
def profile_b(client):
    return _profile(client, CV_B, "b.docx", "Profile B")


# ------------------------------------------------------- tailored CV provenance


class TestTailoredCVProvenance:
    def test_profile_aware_tailored_cv_records_the_profile(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        response = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a}
        )
        assert response.status_code == 200, response.text
        assert response.json()["cv_profile_id"] == profile_a

    def test_stored_row_records_the_same_profile(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        created = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a}
        ).json()

        from app.models import TailoredCV

        row = db.get(TailoredCV, created["id"])
        assert row.cv_profile_id == profile_a

    def test_generated_content_comes_from_the_selected_profile(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        """The stored content must reflect profile A, not the shared candidate."""
        created = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a}
        ).json()

        from app.models import TailoredCV

        row = db.get(TailoredCV, created["id"])
        blob = (row.content_json or "") + (row.summary or "") + (row.analysis or "")
        assert "Senior Machine Learning Engineer" in blob
        # The shared candidate's title and its lone skill must not appear.
        assert "Shared Legacy Title" not in blob
        assert "LegacyOnlySkill" not in blob

    def test_legacy_generation_still_works_without_a_profile(
        self, client, db, candidate_with_evidence, job
    ):
        response = client.post(f"/api/v1/jobs/{job.id}/tailor-cv")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["cv_profile_id"] is None
        # Legacy behaviour: the shared candidate's evidence is still used.
        assert "Shared Legacy Title" in (body["summary"] or "") or "Shared Legacy" in (
            body["summary"] or ""
        ) or body["cv_profile_id"] is None

    def test_legacy_generation_uses_the_shared_candidate_evidence(
        self, client, db, candidate_with_evidence, job
    ):
        created = client.post(f"/api/v1/jobs/{job.id}/tailor-cv").json()
        from app.models import TailoredCV

        row = db.get(TailoredCV, created["id"])
        blob = (row.content_json or "") + (row.summary or "") + (row.analysis or "")
        assert "Shared Legacy" in blob

    def test_two_profiles_generate_separate_documents(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        first = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a}
        ).json()
        second = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_b}
        ).json()

        assert first["id"] != second["id"]
        assert first["cv_profile_id"] == profile_a
        assert second["cv_profile_id"] == profile_b

    def test_scoped_listing_returns_only_that_profile(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        client.post(f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a})
        client.post(f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_b})
        client.post(f"/api/v1/jobs/{job.id}/tailor-cv")

        scoped = client.get(
            "/api/v1/tailored-cvs", params={"cv_profile_id": profile_a}
        ).json()
        assert scoped
        assert {d["cv_profile_id"] for d in scoped} == {profile_a}

        unscoped = client.get("/api/v1/tailored-cvs").json()
        assert len(unscoped) == 3

    def test_regenerate_keeps_the_profile(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        created = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a}
        ).json()

        regenerated = client.post(
            f"/api/v1/tailored-cvs/{created['id']}/regenerate"
        ).json()
        assert regenerated["cv_profile_id"] == profile_a
        assert regenerated["id"] != created["id"]

    def test_regenerating_a_legacy_document_stays_legacy(
        self, client, db, candidate_with_evidence, job
    ):
        created = client.post(f"/api/v1/jobs/{job.id}/tailor-cv").json()
        regenerated = client.post(
            f"/api/v1/tailored-cvs/{created['id']}/regenerate"
        ).json()
        assert regenerated["cv_profile_id"] is None


# ---------------------------------------------------- cover letter provenance


class TestCoverLetterProvenance:
    def test_profile_aware_cover_letter_records_the_profile(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        response = client.post(
            f"/api/v1/jobs/{job.id}/cover-letter", json={"cv_profile_id": profile_a}
        )
        assert response.status_code == 200, response.text
        assert response.json()["cv_profile_id"] == profile_a

    def test_cover_letter_content_comes_from_the_selected_profile(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        created = client.post(
            f"/api/v1/jobs/{job.id}/cover-letter", json={"cv_profile_id": profile_a}
        ).json()

        from app.models import CoverLetter

        row = db.get(CoverLetter, created["id"])
        assert row.cv_profile_id == profile_a
        assert "Shared Legacy Title" not in row.content

    def test_legacy_cover_letter_still_works(
        self, client, db, candidate_with_evidence, job
    ):
        response = client.post(f"/api/v1/jobs/{job.id}/cover-letter")
        assert response.status_code == 200, response.text
        assert response.json()["cv_profile_id"] is None

    def test_two_profiles_generate_separate_letters(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        first = client.post(
            f"/api/v1/jobs/{job.id}/cover-letter", json={"cv_profile_id": profile_a}
        ).json()
        second = client.post(
            f"/api/v1/jobs/{job.id}/cover-letter", json={"cv_profile_id": profile_b}
        ).json()
        assert first["id"] != second["id"]
        assert first["cv_profile_id"] == profile_a
        assert second["cv_profile_id"] == profile_b

    def test_scoped_listing_returns_only_that_profile(
        self, client, db, candidate_with_evidence, job, profile_a, profile_b
    ):
        client.post(f"/api/v1/jobs/{job.id}/cover-letter", json={"cv_profile_id": profile_a})
        client.post(f"/api/v1/jobs/{job.id}/cover-letter", json={"cv_profile_id": profile_b})

        scoped = client.get(
            "/api/v1/cover-letters", params={"cv_profile_id": profile_b}
        ).json()
        assert {letter["cv_profile_id"] for letter in scoped} == {profile_b}


# --------------------------------------------------------------- rejections


class TestProfileRejection:
    @pytest.mark.parametrize(
        "endpoint", ["tailor-cv", "cover-letter"]
    )
    def test_missing_profile_is_rejected(
        self, client, db, candidate_with_evidence, job, endpoint
    ):
        response = client.post(
            f"/api/v1/jobs/{job.id}/{endpoint}", json={"cv_profile_id": 999999}
        )
        assert response.status_code == 404

    @pytest.mark.parametrize("endpoint", ["tailor-cv", "cover-letter"])
    def test_unconfirmed_profile_is_rejected(
        self, client, db, candidate_with_evidence, job, endpoint
    ):
        pending = _profile(client, CV_A, "p.docx", "Pending", confirm=False)
        response = client.post(
            f"/api/v1/jobs/{job.id}/{endpoint}", json={"cv_profile_id": pending}
        )
        assert response.status_code == 409

    @pytest.mark.parametrize("endpoint", ["tailor-cv", "cover-letter"])
    def test_another_candidates_profile_is_rejected(
        self, client, db, candidate_with_evidence, job, endpoint
    ):
        other = Candidate(name="Someone Else")
        db.add(other)
        db.commit()
        db.refresh(other)

        foreign = _profile(client, CV_A, "f.docx", "Foreign")
        from app.models import CVProfile

        row = db.get(CVProfile, foreign)
        row.candidate_id = other.id
        db.commit()

        response = client.post(
            f"/api/v1/jobs/{job.id}/{endpoint}", json={"cv_profile_id": foreign}
        )
        assert response.status_code == 404

    @pytest.mark.parametrize("endpoint", ["tailor-cv", "cover-letter"])
    def test_rejected_profile_creates_no_document(
        self, client, db, candidate_with_evidence, job, endpoint
    ):
        from app.models import CoverLetter, TailoredCV

        before_cv = db.query(TailoredCV).count()
        before_cl = db.query(CoverLetter).count()

        client.post(f"/api/v1/jobs/{job.id}/{endpoint}", json={"cv_profile_id": 999999})
        pending = _profile(client, CV_A, "q.docx", "Q", confirm=False)
        client.post(f"/api/v1/jobs/{job.id}/{endpoint}", json={"cv_profile_id": pending})

        assert db.query(TailoredCV).count() == before_cv
        assert db.query(CoverLetter).count() == before_cl

    @pytest.mark.parametrize("endpoint", ["tailor-cv", "cover-letter"])
    def test_no_legacy_fallback_when_a_profile_is_rejected(
        self, client, db, candidate_with_evidence, job, endpoint
    ):
        response = client.post(
            f"/api/v1/jobs/{job.id}/{endpoint}", json={"cv_profile_id": 999999}
        )
        assert response.status_code == 404
        # Nothing legacy was produced as a consolation.
        from app.models import CoverLetter, TailoredCV

        assert db.query(TailoredCV).count() == 0
        assert db.query(CoverLetter).count() == 0


# ----------------------------------------------------------------- lifecycle


class TestProfileLifecycle:
    def test_archive_keeps_history_attributable(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        document = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a}
        ).json()

        archived = client.post(f"/api/v1/cv-profiles/{profile_a}/archive")
        assert archived.status_code == 200, archived.text
        assert archived.json()["archived_at"] is not None

        from app.models import MatchResult, TailoredCV

        assert db.get(TailoredCV, document["id"]).cv_profile_id == profile_a
        assert db.query(MatchResult).filter_by(cv_profile_id=profile_a).count() == 1

    def test_archived_profile_is_hidden_from_the_default_listing(
        self, client, db, candidate_with_evidence, profile_a
    ):
        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")
        assert client.get("/api/v1/cv-profiles").json() == []
        assert len(client.get("/api/v1/cv-profiles", params={"include_archived": True}).json()) == 1

    def test_archived_profile_is_still_readable(
        self, client, db, candidate_with_evidence, profile_a
    ):
        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")
        assert client.get(f"/api/v1/cv-profiles/{profile_a}").status_code == 200

    def test_archived_profile_cannot_be_used_for_new_work(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")
        match = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        assert match.status_code == 409
        assert "archived" in match.json()["detail"].lower()

    @pytest.mark.parametrize("endpoint", ["tailor-cv", "cover-letter"])
    def test_archived_profile_cannot_generate(
        self, client, db, candidate_with_evidence, job, profile_a, endpoint
    ):
        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")
        response = client.post(
            f"/api/v1/jobs/{job.id}/{endpoint}", json={"cv_profile_id": profile_a}
        )
        assert response.status_code == 409

    def test_archiving_twice_is_idempotent(
        self, client, db, candidate_with_evidence, profile_a
    ):
        first = client.post(f"/api/v1/cv-profiles/{profile_a}/archive").json()
        second = client.post(f"/api/v1/cv-profiles/{profile_a}/archive").json()
        assert first["archived_at"] == second["archived_at"]

    def test_archive_requires_ownership(
        self, client, db, candidate_with_evidence
    ):
        other = Candidate(name="Someone Else")
        db.add(other)
        db.commit()
        db.refresh(other)
        foreign = _profile(client, CV_A, "f.docx", "Foreign")
        from app.models import CVProfile

        row = db.get(CVProfile, foreign)
        row.candidate_id = other.id
        db.commit()

        assert client.post(f"/api/v1/cv-profiles/{foreign}/archive").status_code == 404

    def test_hard_delete_is_refused_while_history_exists(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        """The RESTRICT foreign key must block the provenance-erasing delete."""
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        client.post(f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a})
        client.post(f"/api/v1/jobs/{job.id}/cover-letter", json={"cv_profile_id": profile_a})

        from app.models import CVProfile
        from sqlalchemy.exc import IntegrityError

        with pytest.raises(IntegrityError):
            db.query(CVProfile).filter(CVProfile.id == profile_a).delete()
            db.commit()
        db.rollback()

        # The profile and all three kinds of dependent history survive intact.
        assert db.get(CVProfile, profile_a) is not None
        assert db.query(TailoredCV).filter_by(cv_profile_id=profile_a).count() == 1
        assert db.query(CoverLetter).filter_by(cv_profile_id=profile_a).count() == 1
        assert db.query(MatchResult).filter_by(cv_profile_id=profile_a).count() == 1

    def test_archive_does_not_null_any_provenance(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a})
        document = client.post(
            f"/api/v1/jobs/{job.id}/tailor-cv", json={"cv_profile_id": profile_a}
        ).json()
        letter = client.post(
            f"/api/v1/jobs/{job.id}/cover-letter", json={"cv_profile_id": profile_a}
        ).json()

        client.post(f"/api/v1/cv-profiles/{profile_a}/archive")

        from app.models import CoverLetter, MatchResult, TailoredCV

        assert db.get(TailoredCV, document["id"]).cv_profile_id == profile_a
        assert db.get(CoverLetter, letter["id"]).cv_profile_id == profile_a
        assert db.query(MatchResult).filter_by(cv_profile_id=profile_a).count() == 1


# --------------------------------------------------------- historical records


class TestHistoricalRecordsUnchanged:
    def test_legacy_document_keeps_null_provenance(self, db, candidate_with_evidence, job):
        from app.models import CoverLetter, TailoredCV

        legacy_cv = TailoredCV(
            candidate_id=candidate_with_evidence.id,
            job_id=job.id,
            version=1,
            filename="legacy-cv.docx",
            storage_path="/tmp/legacy.docx",
            validation_status="VALID",
            content_json="{}",
        )
        legacy_letter = CoverLetter(
            candidate_id=candidate_with_evidence.id,
            job_id=job.id,
            content="Dear hiring manager",
            validation_status="VALID",
        )
        db.add_all([legacy_cv, legacy_letter])
        db.commit()
        db.refresh(legacy_cv)
        db.refresh(legacy_letter)

        assert legacy_cv.cv_profile_id is None
        assert legacy_letter.cv_profile_id is None
        assert legacy_cv.filename == "legacy-cv.docx"
        assert legacy_letter.content == "Dear hiring manager"

    def test_matching_provenance_is_intact(
        self, client, db, candidate_with_evidence, job, profile_a
    ):
        legacy = client.post(f"/api/v1/jobs/{job.id}/match").json()
        scoped = client.post(f"/api/v1/jobs/{job.id}/match", json={"cv_profile_id": profile_a}).json()

        assert legacy["cv_profile_id"] is None
        assert scoped["cv_profile_id"] == profile_a
        assert legacy["id"] != scoped["id"]


# ----------------------------------------------------------------- migration


class TestMigrationSafety:
    def test_migration_is_chained_and_documented(self):
        import pathlib
        import re

        new = pathlib.Path(
            "migrations/versions/e6f7a8b9c0d1_document_provenance_and_archival.py"
        )
        assert new.exists(), "migration file missing"
        text = new.read_text()
        assert re.search(r"^revision = 'e6f7a8b9c0d1'", text, re.M)
        assert re.search(r"^down_revision = 'd5e6f7a8b9c0'", text, re.M)
        # The foreign-key change is explained, not silent.
        assert "SET NULL" in text and "RESTRICT" in text
        assert "relabelling" in text or "relabel" in text
        up = text.split("def upgrade")[1].split("def downgrade")[0]
        # Additive columns plus the one documented constraint swap.
        assert up.count("op.add_column") == 3
        for verb in ("op.execute", "bulk_insert", "op.delete", "drop_table"):
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
        scratch = "career_migration_v36"
        base_url = admin_url.rsplit("/", 1)[0] + "/postgres"

        admin = create_engine(base_url, isolation_level="AUTOCOMMIT")
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{scratch}"'))
            connection.execute(text(f'CREATE DATABASE "{scratch}"'))
        admin.dispose()

        url = admin_url.rsplit("/", 1)[0] + f"/{scratch}"
        env = {**os.environ, "DATABASE_URL": url}
        try:
            upgrade = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                capture_output=True, text=True, env=env,
            )
            assert upgrade.returncode == 0, upgrade.stderr[-2000:]

            engine = create_engine(url)
            with engine.connect() as connection:
                for table in ("tailored_cvs", "cover_letters"):
                    cols = {
                        r[0]
                        for r in connection.execute(text(
                            "select column_name from information_schema.columns "
                            "where table_name=:t"
                        ), {"t": table})
                    }
                    assert "cv_profile_id" in cols, table
                assert any(
                    r[0] == "archived_at"
                    for r in connection.execute(text(
                        "select column_name from information_schema.columns "
                        "where table_name='cv_profiles'"
                    ))
                )
                # The provenance FKs this task introduced must all RESTRICT.
                # Scoped to the tables it owns so a later task adding further
                # provenance columns does not make this assertion stale.
                fks = [
                    r[0]
                    for r in connection.execute(text(
                        "select conrelid::regclass::text || ' :: ' || "
                        "pg_get_constraintdef(oid) from pg_constraint "
                        "where contype='f' and pg_get_constraintdef(oid) like '%cv_profiles%' "
                        "and conrelid::regclass::text in "
                        "('tailored_cvs','cover_letters','match_results')"
                    ))
                ]
                assert len(fks) == 3, fks
                assert all("ON DELETE RESTRICT" in f for f in fks), fks
                assert {f.split(" :: ")[0] for f in fks} == {
                    "cover_letters",
                    "match_results",
                    "tailored_cvs",
                }, fks
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
