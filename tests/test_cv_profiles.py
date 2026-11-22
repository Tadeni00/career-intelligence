"""Independent CV profiles for one candidate.

Every fixture is built inside the isolated test database. These tests never read
or depend on development or production CV, candidate or match records.
"""

from __future__ import annotations

import io

from docx import Document

# --------------------------------------------------------------------------
# upload payloads
# --------------------------------------------------------------------------


def _docx_bytes(lines: list[str]) -> bytes:
    doc = Document()
    for line in lines:
        doc.add_paragraph(line)
    buffer = io.BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def _pdf_bytes(lines: list[str]) -> bytes:
    content_parts = []
    y = 720
    for line in lines:
        if line:
            content_parts.append(f"BT /F1 12 Tf 72 {y} Td ({line}) Tj ET")
        y -= 20
    content = "\n".join(content_parts).encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for index, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(b"xref\n0 %d\n" % (len(objects) + 1))
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return out.getvalue()


CV_ONE = [
    "Ada Okafor",
    "Senior Machine Learning Engineer",
    "ada@example.com | +44 20 7946 0000 | London, United Kingdom",
    "Machine learning engineer focused on fraud detection.",
    "Machine Learning Engineer | Fintech Systems | 2021 - Present",
    "Built classification models for transaction fraud detection.",
    "MSc Data Science | University of Edinburgh",
    "Python, SQL, Statistics, Machine Learning",
]

CV_TWO = [
    "Ada Okafor",
    "Junior Data Analyst",
    "ada@example.com | +44 20 7946 0001 | Manchester, United Kingdom",
    "Data analyst focused on reporting and dashboards.",
    "Data Analyst | Analytics Works | 2019 - 2021",
    "Built segmentation models using Python and SQL.",
    "BSc Statistics | University of Leeds",
    "SQL, Excel, Tableau",
]


_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _post_profile(client, filename: bytes, lines, label=None):
    files = {"file": (filename, _docx_bytes(lines), _DOCX_MIME)}
    data = {"label": label} if label is not None else None
    return client.post("/api/v1/cv-profiles", files=files, data=data)


def _upload_one(client, label=None):
    return _post_profile(client, "cv_one.docx", CV_ONE, label)


def _upload_two(client, label=None):
    return _post_profile(client, "cv_two.docx", CV_TWO, label)


# --------------------------------------------------------------------------
# creation
# --------------------------------------------------------------------------


class TestProfileCreation:
    def test_upload_creates_a_profile(self, client, db, candidate):
        response = _upload_one(client)
        assert response.status_code == 201, response.text
        body = response.json()
        assert body["candidate_id"] == candidate.id
        assert body["label"] == "cv_one.docx"
        assert body["status"] == "AWAITING_EXTRACTION"
        assert body["confirmed"] is None
        assert body["extracted"] is None

    def test_two_different_cvs_create_two_independent_profiles(self, client, db, candidate):
        first = _upload_one(client, label="ML Engineer CV").json()
        second = _upload_two(client, label="Analyst CV").json()

        assert first["id"] != second["id"]
        assert first["candidate_id"] == second["candidate_id"] == candidate.id
        assert first["label"] == "ML Engineer CV"
        assert second["label"] == "Analyst CV"

        listed = client.get("/api/v1/cv-profiles").json()
        assert {p["id"] for p in listed} == {first["id"], second["id"]}

    def test_default_label_is_the_filename(self, client, db, candidate):
        assert _upload_one(client).json()["label"] == "cv_one.docx"

    def test_creation_does_not_touch_the_candidate(self, client, db, candidate):
        before = (candidate.name, candidate.professional_title, candidate.location)
        _upload_one(client)
        _upload_two(client)
        db.expire_all()
        from app.models import Candidate

        after = db.get(Candidate, candidate.id)
        assert (after.name, after.professional_title, after.location) == before

    def test_creation_creates_no_cv_document(self, client, db, candidate):
        from app.models import CVDocument
        from sqlalchemy import func, select

        before = db.execute(select(func.count()).select_from(CVDocument)).scalar()
        _upload_one(client)
        _upload_two(client)
        after = db.execute(select(func.count()).select_from(CVDocument)).scalar()
        assert after == before


# --------------------------------------------------------------------------
# extraction and confirmation stay profile-scoped
# --------------------------------------------------------------------------


class TestProfileExtractionAndConfirmation:
    def test_extraction_is_stored_on_the_profile(self, client, db, candidate):
        profile_id = _upload_one(client).json()["id"]

        response = client.post(f"/api/v1/cv-profiles/{profile_id}/extract")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["status"] == "AWAITING_REVIEW"
        assert body["text_length"] > 0
        assert body["extracted"] is not None

    def test_each_profile_keeps_its_own_extracted_text(self, client, db, candidate):
        first = _upload_one(client).json()["id"]
        second = _upload_two(client).json()["id"]

        client.post(f"/api/v1/cv-profiles/{first}/extract")
        client.post(f"/api/v1/cv-profiles/{second}/extract")

        from app.models import CVProfile

        one = db.get(CVProfile, first)
        two = db.get(CVProfile, second)
        assert one.extracted_text != two.extracted_text
        assert "Senior Machine Learning Engineer" in (one.extracted_text or "")
        assert "Junior Data Analyst" in (two.extracted_text or "")
        assert "Junior Data Analyst" not in (one.extracted_text or "")

    def test_each_profile_keeps_its_own_candidate_information(self, client, db, candidate):
        first = _upload_one(client).json()["id"]
        second = _upload_two(client).json()["id"]

        client.post(f"/api/v1/cv-profiles/{first}/extract")
        client.post(f"/api/v1/cv-profiles/{second}/extract")

        one = client.get(f"/api/v1/cv-profiles/{first}").json()
        two = client.get(f"/api/v1/cv-profiles/{second}").json()

        assert one["extracted"]["professional_title"] == "Senior Machine Learning Engineer"
        assert two["extracted"]["professional_title"] == "Junior Data Analyst"
        assert "Machine Learning" in {s["name"] for s in one["extracted"]["skills"]}
        assert "Tableau" in {s["name"] for s in two["extracted"]["skills"]}

    def test_confirm_stores_information_only_on_that_profile(self, client, db, candidate):
        first = _upload_one(client).json()["id"]
        second = _upload_two(client).json()["id"]
        client.post(f"/api/v1/cv-profiles/{first}/extract")
        client.post(f"/api/v1/cv-profiles/{second}/extract")

        response = client.post(f"/api/v1/cv-profiles/{first}/confirm", json={})
        assert response.status_code == 200, response.text

        confirmed_one = client.get(f"/api/v1/cv-profiles/{first}").json()
        confirmed_two = client.get(f"/api/v1/cv-profiles/{second}").json()

        assert confirmed_one["status"] == "CONFIRMED"
        assert confirmed_one["confirmed"] is not None
        assert confirmed_one["confirmed"]["professional_title"] == "Senior Machine Learning Engineer"

        # The untouched profile keeps its own state.
        assert confirmed_two["status"] == "AWAITING_REVIEW"
        assert confirmed_two["confirmed"] is None

    def test_confirming_one_profile_never_overwrites_another(self, client, db, candidate):
        first = _upload_one(client).json()["id"]
        second = _upload_two(client).json()["id"]
        client.post(f"/api/v1/cv-profiles/{first}/extract")
        client.post(f"/api/v1/cv-profiles/{second}/extract")

        client.post(f"/api/v1/cv-profiles/{first}/confirm", json={})

        from app.models import CVProfile

        two = db.get(CVProfile, second)
        assert two.confirmed_data is None
        assert two.status == "AWAITING_REVIEW"

    def test_confirmation_never_writes_to_the_shared_candidate(self, client, db, candidate):
        first = _upload_one(client).json()["id"]
        second = _upload_two(client).json()["id"]
        client.post(f"/api/v1/cv-profiles/{first}/extract")
        client.post(f"/api/v1/cv-profiles/{second}/extract")

        before = (
            candidate.name,
            candidate.professional_title,
            candidate.email,
            candidate.location,
            candidate.years_of_experience,
            len(candidate.skills),
            len(candidate.experience),
            len(candidate.education),
        )

        client.post(f"/api/v1/cv-profiles/{first}/confirm", json={})
        client.post(f"/api/v1/cv-profiles/{second}/confirm", json={})

        db.expire_all()
        from app.models import Candidate

        after = db.get(Candidate, candidate.id)
        assert (
            after.name,
            after.professional_title,
            after.email,
            after.location,
            after.years_of_experience,
            len(after.skills),
            len(after.experience),
            len(after.education),
        ) == before

    def test_confirmation_can_correct_the_extracted_values(self, client, db, candidate):
        profile_id = _upload_one(client).json()["id"]
        client.post(f"/api/v1/cv-profiles/{profile_id}/extract")

        response = client.post(
            f"/api/v1/cv-profiles/{profile_id}/confirm",
            json={"professional_title": "Staff Data Scientist", "location": "Lagos, Nigeria"},
        )
        assert response.status_code == 200, response.text
        confirmed = response.json()["confirmed"]
        assert confirmed["professional_title"] == "Staff Data Scientist"
        assert confirmed["location"] == "Lagos, Nigeria"

    def test_partial_confirmation_keeps_unsupplied_extracted_values(self, client, db, candidate):
        profile_id = _upload_one(client).json()["id"]
        client.post(f"/api/v1/cv-profiles/{profile_id}/extract")

        confirmed = client.post(
            f"/api/v1/cv-profiles/{profile_id}/confirm",
            json={"professional_title": "Lead Engineer"},
        ).json()["confirmed"]

        # Corrected field takes the supplied value.
        assert confirmed["professional_title"] == "Lead Engineer"
        # Everything not supplied still comes from the extraction.
        assert confirmed["email"] == "ada@example.com"
        assert confirmed["skills"]

    def test_confirming_without_extraction_is_a_conflict(self, client, db, candidate):
        profile_id = _upload_one(client).json()["id"]
        response = client.post(f"/api/v1/cv-profiles/{profile_id}/confirm", json={})
        assert response.status_code == 409
        assert "extraction" in response.json()["detail"].lower()

    def test_reconfirmation_updates_only_that_profile(self, client, db, candidate):
        first = _upload_one(client).json()["id"]
        second = _upload_two(client).json()["id"]
        for pid in (first, second):
            client.post(f"/api/v1/cv-profiles/{pid}/extract")
            client.post(f"/api/v1/cv-profiles/{pid}/confirm", json={})

        client.post(
            f"/api/v1/cv-profiles/{first}/confirm",
            json={"professional_title": "Principal Engineer"},
        )

        assert client.get(f"/api/v1/cv-profiles/{first}").json()["confirmed"][
            "professional_title"
        ] == "Principal Engineer"
        assert client.get(f"/api/v1/cv-profiles/{second}").json()["confirmed"][
            "professional_title"
        ] == "Junior Data Analyst"


# --------------------------------------------------------------------------
# ownership
# --------------------------------------------------------------------------


class TestProfileOwnership:
    def _other_candidate_profile(self, db):
        """A profile owned by a genuinely different candidate row."""
        from app.models import Candidate, CVProfile

        other_candidate = Candidate(name="Another Candidate")
        db.add(other_candidate)
        db.commit()
        db.refresh(other_candidate)

        profile = CVProfile(
            candidate_id=other_candidate.id,
            label="Someone else's CV",
            status="CONFIRMED",
            file_type="pdf",
            storage_path="/tmp/other.pdf",
            confirmed_data="{}",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
        return profile

    def test_listing_returns_only_the_current_candidate(self, client, db, candidate):
        mine = _upload_one(client).json()["id"]
        other = self._other_candidate_profile(db)

        listed = client.get("/api/v1/cv-profiles").json()
        assert [p["id"] for p in listed] == [mine]
        assert other.id not in {p["id"] for p in listed}

    def test_another_candidates_profile_is_not_found(self, client, db, candidate):
        other = self._other_candidate_profile(db)

        assert client.get(f"/api/v1/cv-profiles/{other.id}").status_code == 404
        assert client.post(f"/api/v1/cv-profiles/{other.id}/extract").status_code == 404
        assert client.post(f"/api/v1/cv-profiles/{other.id}/confirm", json={}).status_code == 404

    def test_another_candidates_confirmed_data_is_never_returned(self, client, db, candidate):
        other = self._other_candidate_profile(db)
        response = client.get(f"/api/v1/cv-profiles/{other.id}")
        assert response.status_code == 404
        assert "Someone else's CV" not in response.text
        assert "confirmed" not in response.json()

    def test_missing_profile_returns_the_established_not_found(self, client, db, candidate):
        response = client.get("/api/v1/cv-profiles/999999")
        assert response.status_code == 404
        assert response.json()["detail"] == "CV profile 999999 not found."


# --------------------------------------------------------------------------
# errors and persistence
# --------------------------------------------------------------------------


class TestProfileErrors:
    def test_unsupported_extension_is_rejected(self, client, db, candidate):
        response = client.post(
            "/api/v1/cv-profiles",
            files={"file": ("notes.exe", b"MZ\x00\x00", "application/octet-stream")},
        )
        assert response.status_code == 400

    def test_unsupported_content_type_is_rejected(self, client, db, candidate):
        response = client.post(
            "/api/v1/cv-profiles",
            files={"file": ("cv.txt", b"plain text", "text/plain")},
        )
        assert response.status_code == 400

    def test_empty_upload_is_rejected(self, client, db, candidate):
        response = client.post(
            "/api/v1/cv-profiles",
            files={"file": ("cv.docx", b"", _DOCX_MIME)},
        )
        assert response.status_code == 400

    def test_a_failed_upload_creates_no_profile(self, client, db, candidate):
        from app.models import CVProfile
        from sqlalchemy import func, select

        before = db.execute(select(func.count()).select_from(CVProfile)).scalar()
        client.post(
            "/api/v1/cv-profiles",
            files={"file": ("bad.exe", b"MZ\x00\x00", "application/octet-stream")},
        )
        after = db.execute(select(func.count()).select_from(CVProfile)).scalar()
        assert after == before


class TestProfilePersistence:
    def test_profile_survives_a_new_session(self, client, db, candidate):
        profile_id = _upload_one(client).json()["id"]
        client.post(f"/api/v1/cv-profiles/{profile_id}/extract")
        client.post(f"/api/v1/cv-profiles/{profile_id}/confirm", json={})

        from app.db.session import SessionLocal
        from app.models import CVProfile

        fresh = SessionLocal()
        try:
            stored = fresh.get(CVProfile, profile_id)
            assert stored is not None
            assert stored.status == "CONFIRMED"
            assert stored.extracted_text
            assert stored.confirmed_data
        finally:
            fresh.close()

        # Still readable through the API afterwards.
        assert client.get(f"/api/v1/cv-profiles/{profile_id}").json()["status"] == "CONFIRMED"


# --------------------------------------------------------------------------
# backward compatibility
# --------------------------------------------------------------------------


class TestLegacyCvRoutesUnaffected:
    def test_legacy_upload_still_works(self, client, db, candidate):
        response = client.post(
            "/api/v1/cvs/upload",
            files={
                "file": (
                    "legacy.docx",
                    _docx_bytes(CV_ONE),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        assert response.status_code == 201, response.text
        assert response.json()["is_master"] is True
        assert response.json()["filename"] == "legacy.docx"

    def test_legacy_list_still_works(self, client, db, candidate):
        client.post(
            "/api/v1/cvs/upload",
            files={
                "file": (
                    "legacy.docx",
                    _docx_bytes(CV_ONE),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )
        listed = client.get("/api/v1/cvs").json()
        assert len(listed) == 1
        assert listed[0]["filename"] == "legacy.docx"

    def test_legacy_upload_after_a_profile_does_not_change_profile_state(
        self, client, db, candidate
    ):
        profile_id = _upload_one(client).json()["id"]
        client.post(f"/api/v1/cv-profiles/{profile_id}/extract")
        client.post(f"/api/v1/cv-profiles/{profile_id}/confirm", json={})

        client.post(
            "/api/v1/cvs/upload",
            files={
                "file": (
                    "legacy.docx",
                    _docx_bytes(CV_TWO),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
        )

        still = client.get(f"/api/v1/cv-profiles/{profile_id}").json()
        assert still["status"] == "CONFIRMED"
        assert still["confirmed"]["professional_title"] == "Senior Machine Learning Engineer"

    def test_legacy_confirm_still_writes_to_the_candidate(self, client, db, candidate):
        """The documented bridge: legacy /cvs/{id}/confirm still owns the shared row.

        Legacy confirmation is append-only by default, so it adds the extracted
        skills to the candidate and leaves the existing scalar name alone.
        """
        uploaded = client.post(
            "/api/v1/cvs/upload",
            files={"file": ("legacy.docx", _docx_bytes(CV_ONE), _DOCX_MIME)},
        ).json()
        cv_id = uploaded["id"]
        client.post(f"/api/v1/cvs/{cv_id}/extract")

        summary = client.post(f"/api/v1/cvs/{cv_id}/confirm", json={}).json()
        assert {s["name"] for s in summary["skills"]} >= {"Python", "SQL"}
        assert summary["name"] == candidate.name  # append-only: scalar untouched

    def test_profile_confirmation_does_not_feed_the_legacy_row(self, client, db, candidate):
        """The converse of the bridge: confirming a profile adds nothing to Candidate."""
        profile_id = _upload_one(client).json()["id"]
        client.post(f"/api/v1/cv-profiles/{profile_id}/extract")
        client.post(f"/api/v1/cv-profiles/{profile_id}/confirm", json={})

        summary = client.get("/api/v1/candidate").json()
        assert summary["skills"] == []
        assert summary["experience"] == []
        assert summary["name"] == candidate.name

    def test_profiles_do_not_appear_in_the_legacy_cv_list(self, client, db, candidate):
        _upload_one(client)
        _upload_two(client)
        assert client.get("/api/v1/cvs").json() == []


# --------------------------------------------------------------------------
# migration
# --------------------------------------------------------------------------


class TestMigrationSafety:
    def test_migration_is_additive_and_chained(self):
        import pathlib
        import re

        versions = pathlib.Path("migrations/versions")
        new = versions / "c4d5e6f7a8b9_cv_profiles.py"
        assert new.exists(), "migration file missing"

        text = new.read_text()
        assert re.search(r"^revision = 'c4d5e6f7a8b9'", text, re.M)
        assert re.search(r"^down_revision = 'a1b2c3d4e5f6'", text, re.M)
        # Additive only: no existing table is altered or dropped.
        assert "op.add_column" not in text
        assert "op.drop_column" not in text
        assert "op.drop_table" not in text.split("def downgrade")[0]

    def test_existing_application_records_are_intact(self, client, db, candidate):
        from app.models import Application, ApplicationStatus, Job

        job = Job(
            title="Data Analyst",
            company="Kuda",
            location="Lagos, Nigeria",
            url="https://example.com/1",
            source="manual",
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        application = Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status=ApplicationStatus.INTERESTED.value,
        )
        db.add(application)
        db.commit()
        db.refresh(application)

        profile_id = _upload_one(client).json()["id"]
        client.post(f"/api/v1/cv-profiles/{profile_id}/extract")
        client.post(f"/api/v1/cv-profiles/{profile_id}/confirm", json={})

        db.expire_all()
        still = db.get(Application, application.id)
        assert still is not None
        assert still.candidate_id == candidate.id
        assert still.job_id == job.id
        assert still.status == ApplicationStatus.INTERESTED.value

    def test_migration_creates_the_table_on_a_fresh_database(self):
        """Apply the real migration chain to an isolated database."""
        import os
        import subprocess
        import sys

        from sqlalchemy import create_engine, text

        admin_url = os.environ.get(
            "TEST_DATABASE_URL",
            "postgresql+psycopg://career:career@localhost:5433/career_test",
        )
        scratch_db = "career_migration_check"
        base = create_engine(
            admin_url.rsplit("/", 1)[0] + "/postgres", isolation_level="AUTOCOMMIT"
        )
        with base.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db}"'))
            connection.execute(text(f'CREATE DATABASE "{scratch_db}"'))
        base.dispose()

        scratch_url = admin_url.rsplit("/", 1)[0] + f"/{scratch_db}"
        env = {**os.environ, "DATABASE_URL": scratch_url}
        try:
            upgrade = subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert upgrade.returncode == 0, upgrade.stderr[-2000:]

            engine = create_engine(scratch_url)
            with engine.connect() as connection:
                tables = {
                    row[0]
                    for row in connection.execute(
                        text(
                            "select table_name from information_schema.tables "
                            "where table_schema='public'"
                        )
                    )
                }
                assert "cv_profiles" in tables
                assert {"candidates", "jobs", "applications", "tailored_cvs"} <= tables
                columns = {
                    row[0]
                    for row in connection.execute(
                        text(
                            "select column_name from information_schema.columns "
                            "where table_name='cv_profiles'"
                        )
                    )
                }
                assert {
                    "id",
                    "candidate_id",
                    "label",
                    "status",
                    "extracted_text",
                    "extracted_data",
                    "confirmed_data",
                    "created_at",
                    "updated_at",
                } <= columns
            engine.dispose()

            # The chain must also downgrade cleanly.
            downgrade = subprocess.run(
                [sys.executable, "-m", "alembic", "downgrade", "-1"],
                capture_output=True,
                text=True,
                env=env,
            )
            assert downgrade.returncode == 0, downgrade.stderr[-2000:]
        finally:
            base = create_engine(
                admin_url.rsplit("/", 1)[0] + "/postgres", isolation_level="AUTOCOMMIT"
            )
            with base.connect() as connection:
                connection.execute(text(f'DROP DATABASE IF EXISTS "{scratch_db}"'))
            base.dispose()
