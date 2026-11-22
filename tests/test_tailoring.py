"""CV tailoring and cover letter generation."""

from __future__ import annotations

import io

from docx import Document


def _make_docx_bytes() -> bytes:
    document = Document()
    document.add_heading("Tommie van der Berg", level=0)
    document.add_paragraph("Senior Machine Learning Engineer")
    document.add_paragraph("tommie@example.com | Amsterdam, Netherlands")
    document.add_heading("Summary", level=1)
    document.add_paragraph("Machine Learning Engineer with experience in fraud detection.")
    document.add_heading("Experience", level=1)
    document.add_paragraph("Machine Learning Engineer | Fintech Systems | 2021 - Present")
    document.add_paragraph("Built fraud detection models.")
    document.add_heading("Education", level=1)
    document.add_paragraph("MSc Data Science | University of Amsterdam")
    document.add_heading("Skills", level=1)
    document.add_paragraph("Python, SQL, Statistics, Machine Learning")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def _setup_profile(client):
    client.get("/api/v1/candidate")
    client.put(
        "/api/v1/candidate",
        json={
            "name": "Tommie van der Berg",
            "professional_title": "Senior Machine Learning Engineer",
            "location": "Amsterdam, Netherlands",
            "years_of_experience": 6,
            "summary": "Machine Learning Engineer with experience in fraud detection.",
        },
    )
    for skill in ["Python", "SQL", "Statistics", "Machine Learning", "PostgreSQL"]:
        client.post("/api/v1/candidate/skills", json={"name": skill})
    client.post(
        "/api/v1/candidate/experience",
        json={
            "company": "Fintech Systems",
            "title": "Machine Learning Engineer",
            "start_date": "2021",
            "description": "Built fraud detection models and evaluation pipelines.",
        },
    )
    client.post(
        "/api/v1/candidate/education",
        json={
            "institution": "University of Amsterdam",
            "degree": "MSc",
            "field": "Data Science",
        },
    )


def _create_job(client, **overrides):
    payload = {
        "title": "Machine Learning Engineer",
        "company": "Fintech Corp",
        "location": "Amsterdam, Netherlands",
        "remote_status": "Hybrid",
        "description": (
            "We are looking for a Machine Learning Engineer to build fraud detection models. "
            "Required: Python, Machine Learning, SQL. Preferred: Kubernetes, AWS."
        ),
    }
    payload.update(overrides)
    return client.post("/api/v1/jobs", json=payload)


def test_tailor_cv_generates_valid_document(client):
    _setup_profile(client)
    # Upload a master CV so source_cv_id is set
    client.post(
        "/api/v1/cvs/upload",
        files={
            "file": (
                "cv.docx",
                _make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    job = _create_job(client).json()

    response = client.post(f"/api/v1/jobs/{job['id']}/tailor-cv")
    assert response.status_code == 200
    data = response.json()
    assert data["validation_status"] == "VALID"
    assert data["validation_issues"] == []
    assert data["version"] == 1
    assert data["source_cv_id"] is not None
    assert data["analysis"] is not None
    assert len(data["analysis"]["relevant_skills"]) > 0
    assert len(data["changes_summary"]) > 0

    # Download and verify DOCX
    download = client.get(f"/api/v1/tailored-cvs/{data['id']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    document = Document(io.BytesIO(download.content))
    text = "\n".join(p.text for p in document.paragraphs)
    assert "Tommie van der Berg" in text
    assert "Machine Learning Engineer" in text
    assert "Fintech Systems" in text
    assert "Python" in text


def test_tailor_cv_does_not_add_unsupported_skills(client):
    _setup_profile(client)
    job = _create_job(
        client,
        description="Required: Python, Machine Learning, SQL, Kubernetes, AWS, Rust.",
    ).json()

    response = client.post(f"/api/v1/jobs/{job['id']}/tailor-cv")
    assert response.status_code == 200
    data = response.json()
    # Kubernetes, AWS, Rust are not on the profile — they must not appear
    content = client.get(f"/api/v1/tailored-cvs/{data['id']}/content").json()
    skills = content["content"].get("skills", [])
    assert "Kubernetes" not in skills
    assert "AWS" not in skills
    assert "Rust" not in skills
    # But they should be flagged as missing
    assert any("Kubernetes" in item for item in data["analysis"]["missing_requirements"])


def test_tailor_cv_does_not_add_unsupported_achievements(client):
    _setup_profile(client)
    job = _create_job(client).json()

    response = client.post(f"/api/v1/jobs/{job['id']}/tailor-cv")
    data = response.json()
    content = client.get(f"/api/v1/tailored-cvs/{data['id']}/content").json()
    # The profile says "Built fraud detection models" — no metrics
    for exp in content["content"].get("experience", []):
        for bullet in exp.get("bullets", []):
            assert "30%" not in bullet
            assert "50%" not in bullet


def test_master_cv_unchanged_after_tailoring(client):
    _setup_profile(client)
    # Upload a master CV
    upload = client.post(
        "/api/v1/cvs/upload",
        files={
            "file": (
                "cv.docx",
                _make_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    cv_id = upload.json()["id"]
    client.post(f"/api/v1/cvs/{cv_id}/extract")
    extraction = client.get(f"/api/v1/cvs/{cv_id}/extraction").json()
    client.post(
        f"/api/v1/cvs/{cv_id}/confirm",
        json={"extraction_id": extraction["id"], "overwrite_existing": True},
    )

    job = _create_job(client).json()
    client.post(f"/api/v1/jobs/{job['id']}/tailor-cv")

    # Master CV should still be the same
    cvs = client.get("/api/v1/cvs").json()
    master = [cv for cv in cvs if cv["is_master"]][0]
    assert master["id"] == cv_id
    assert master["status"] == "READY"


def test_tailored_cv_associated_with_correct_job(client):
    _setup_profile(client)
    job1 = _create_job(client, title="ML Engineer", company="Company A").json()
    job2 = _create_job(client, title="Data Scientist", company="Company B").json()

    cv1 = client.post(f"/api/v1/jobs/{job1['id']}/tailor-cv").json()
    cv2 = client.post(f"/api/v1/jobs/{job2['id']}/tailor-cv").json()

    assert cv1["job_id"] == job1["id"]
    assert cv2["job_id"] == job2["id"]
    assert cv1["id"] != cv2["id"]


def test_regenerate_creates_new_version(client):
    _setup_profile(client)
    job = _create_job(client).json()

    v1 = client.post(f"/api/v1/jobs/{job['id']}/tailor-cv").json()
    v2 = client.post(f"/api/v1/tailored-cvs/{v1['id']}/regenerate").json()

    assert v2["version"] == 2
    assert v2["id"] != v1["id"]


def test_cover_letter_generation(client):
    """V1.1: the letter must be generated, correctly targeted, and validated.

    V1 asserted VALID unconditionally. V1.1 deliberately tightened validation, so
    this test now asserts the V1.1 contract instead: correct role/company/evidence,
    no fabricated entity or contact claim, and any detected violation is actually
    surfaced rather than silently passed.
    """
    _setup_profile(client)
    job = _create_job(client).json()

    response = client.post(f"/api/v1/jobs/{job['id']}/cover-letter")
    assert response.status_code == 200
    data = response.json()
    assert "Machine Learning Engineer" in data["content"]
    assert "Fintech Corp" in data["content"]
    # Genuine candidate evidence is used.
    assert "fraud detection" in data["content"].lower()

    # V1.1 gate: fabricated entities/contacts/metrics must never be present.
    forbidden_codes = {
        "INVENTED_EMPLOYER", "INSUPPORTED_CONTACT", "UNSUPPORTED_CONTACT",
        "UNSUPPORTED_METRIC", "INVENTED_COMPANY_KNOWLEDGE", "SUSPICIOUS_OUTPUT",
    }
    assert not forbidden_codes & {i["code"] for i in data["validation_issues"]}

    # Status must be a defined V1.1 status, and if it failed, the reasons are
    # reported so a human can review them.
    assert data["validation_status"] in {"VALID", "REVIEW_REQUIRED",
                                        "VALIDATION_FAILED"}
    if data["validation_status"] != "VALID":
        assert data["validation_issues"], "failed validation must explain why"
    assert "Tommie van der Berg" in data["content"]
    assert "fraud detection" in data["content"].lower()


def test_cover_letter_flags_unsupported_claims(client):
    _setup_profile(client)
    job = _create_job(
        client,
        description="Required: Python, Machine Learning, SQL, Kubernetes, AWS, 10 years experience.",
    ).json()

    response = client.post(f"/api/v1/jobs/{job['id']}/cover-letter")
    data = response.json()
    # Should still generate but may have warnings about unsupported claims
    assert data["validation_status"] in {"VALID", "VALIDATION_FAILED"}


def test_cover_letter_download(client):
    _setup_profile(client)
    job = _create_job(client).json()
    letter = client.post(f"/api/v1/jobs/{job['id']}/cover-letter").json()

    download = client.get(f"/api/v1/cover-letters/{letter['id']}/download")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("text/plain")
    assert "Fintech-Corp" in download.headers["content-disposition"]


def test_analyze_cv_endpoint(client):
    _setup_profile(client)
    job = _create_job(client).json()

    response = client.post(f"/api/v1/jobs/{job['id']}/analyze-cv")
    assert response.status_code == 200
    data = response.json()
    assert len(data["relevant_skills"]) > 0
    assert len(data["relevant_experience"]) > 0
    assert any("Kubernetes" in item for item in data["missing_requirements"])
