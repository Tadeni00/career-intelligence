"""CV upload, extraction, review and confirmation."""

from __future__ import annotations

import io

from docx import Document


def _make_pdf_bytes() -> bytes:
    """Minimal valid PDF with extractable text."""
    lines = [
        "Tommie van der Berg",
        "Senior Machine Learning Engineer",
        "tommie@example.com | +31 6 1234 5678 | Amsterdam, Netherlands",
        "",
        "Summary",
        "Machine Learning Engineer with experience building and deploying statistical models.",
        "",
        "Experience",
        "Machine Learning Engineer | Fintech Systems | 2021 - Present",
        "Built and deployed classification models for transaction fraud detection.",
        "",
        "Education",
        "MSc Data Science | University of Amsterdam",
        "",
        "Skills",
        "Python, SQL, Statistics, Machine Learning",
    ]
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
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return out.getvalue()


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


def _upload(client, content: bytes, filename: str, content_type: str):
    return client.post(
        "/api/v1/cvs/upload",
        files={"file": (filename, content, content_type)},
    )


def test_pdf_upload_and_extraction(client):
    client.get("/api/v1/candidate")
    response = _upload(client, _make_pdf_bytes(), "cv.pdf", "application/pdf")
    assert response.status_code == 201
    cv_id = response.json()["id"]
    assert response.json()["is_master"] is True

    extracted = client.post(f"/api/v1/cvs/{cv_id}/extract")
    assert extracted.status_code == 200
    data = extracted.json()["data"]
    assert data["name"] == "Tommie van der Berg"
    assert data["professional_title"] == "Senior Machine Learning Engineer"
    assert data["email"] == "tommie@example.com"
    assert data["location"] == "Amsterdam, Netherlands"
    assert "machine learning engineer" in (data["summary"] or "").lower()
    assert len(data["experience"]) == 1
    assert data["experience"][0]["company"] == "Fintech Systems"
    assert data["education"][0]["institution"] == "University of Amsterdam"
    assert {s["name"] for s in data["skills"]} >= {"Python", "SQL", "Statistics"}


def test_docx_upload_and_extraction(client):
    client.get("/api/v1/candidate")
    response = _upload(
        client,
        _make_docx_bytes(),
        "cv.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    assert response.status_code == 201
    cv_id = response.json()["id"]

    extracted = client.post(f"/api/v1/cvs/{cv_id}/extract")
    assert extracted.status_code == 200
    data = extracted.json()["data"]
    assert data["name"] == "Tommie van der Berg"
    assert len(data["experience"]) == 1
    assert data["education"][0]["degree"] == "MSc"


def test_invalid_file_type_rejected(client):
    client.get("/api/v1/candidate")
    response = _upload(client, b"MZ\x90\x00", "evil.exe", "application/octet-stream")
    assert response.status_code == 400
    assert "Unsupported file type" in response.json()["detail"]


def test_empty_file_rejected(client):
    client.get("/api/v1/candidate")
    response = _upload(client, b"", "empty.pdf", "application/pdf")
    assert response.status_code == 400


def test_oversized_file_rejected(client):
    client.get("/api/v1/candidate")
    response = _upload(client, b"x" * (11 * 1024 * 1024), "big.pdf", "application/pdf")
    assert response.status_code == 413


def test_extraction_does_not_overwrite_profile(client):
    client.get("/api/v1/candidate")
    client.put("/api/v1/candidate", json={"name": "Original Name", "location": "Berlin"})
    response = _upload(client, _make_docx_bytes(), "cv.docx", "application/pdf")
    cv_id = response.json()["id"]
    client.post(f"/api/v1/cvs/{cv_id}/extract")

    profile = client.get("/api/v1/candidate").json()
    assert profile["name"] == "Original Name"
    assert profile["location"] == "Berlin"
    assert profile["skills"] == []


def test_confirm_applies_extraction(client):
    client.get("/api/v1/candidate")
    response = _upload(client, _make_docx_bytes(), "cv.docx", "application/pdf")
    cv_id = response.json()["id"]
    extraction = client.post(f"/api/v1/cvs/{cv_id}/extract").json()

    confirmed = client.post(
        f"/api/v1/cvs/{cv_id}/confirm",
        json={"extraction_id": extraction["id"], "overwrite_existing": True},
    )
    assert confirmed.status_code == 200
    data = confirmed.json()
    assert data["name"] == "Tommie van der Berg"
    assert data["professional_title"] == "Senior Machine Learning Engineer"
    assert data["location"] == "Amsterdam, Netherlands"
    assert len(data["experience"]) == 1
    assert data["experience"][0]["company"] == "Fintech Systems"
    assert len(data["education"]) == 1
    assert {s["name"] for s in data["skills"]} >= {"Python", "SQL", "Statistics"}


def test_confirm_without_overwrite_keeps_existing(client):
    client.get("/api/v1/candidate")
    client.put("/api/v1/candidate", json={"name": "Original Name"})
    client.post("/api/v1/candidate/skills", json={"name": "Rust"})

    response = _upload(client, _make_docx_bytes(), "cv.docx", "application/pdf")
    cv_id = response.json()["id"]
    extraction = client.post(f"/api/v1/cvs/{cv_id}/extract").json()
    confirmed = client.post(
        f"/api/v1/cvs/{cv_id}/confirm",
        json={"extraction_id": extraction["id"], "overwrite_existing": False},
    ).json()

    assert confirmed["name"] == "Original Name"
    skill_names = {s["name"] for s in confirmed["skills"]}
    assert "Rust" in skill_names
    assert "Python" in skill_names


def test_master_cv_flag(client):
    client.get("/api/v1/candidate")
    first = _upload(client, _make_docx_bytes(), "first.docx", "application/pdf").json()
    second = _upload(client, _make_docx_bytes(), "second.docx", "application/pdf").json()
    assert first["is_master"] is True
    assert second["is_master"] is False

    promoted = client.post(f"/api/v1/cvs/{second['id']}/make-master")
    assert promoted.status_code == 200
    assert promoted.json()["is_master"] is True

    cvs = client.get("/api/v1/cvs").json()
    masters = [cv for cv in cvs if cv["is_master"]]
    assert len(masters) == 1
    assert masters[0]["id"] == second["id"]


def test_extraction_issues_are_reported(client):
    client.get("/api/v1/candidate")
    response = _upload(client, _make_docx_bytes(), "cv.docx", "application/pdf")
    cv_id = response.json()["id"]
    extraction = client.post(f"/api/v1/cvs/{cv_id}/extract").json()
    assert isinstance(extraction["issues"], list)
    assert extraction["text_length"] > 0


def test_confirm_requires_extraction(client):
    client.get("/api/v1/candidate")
    response = _upload(client, _make_docx_bytes(), "cv.docx", "application/pdf")
    cv_id = response.json()["id"]
    result = client.post(f"/api/v1/cvs/{cv_id}/confirm", json={})
    assert result.status_code == 404


def test_corrupt_pdf_fails_gracefully(client):
    client.get("/api/v1/candidate")
    response = _upload(client, b"%PDF-1.4 not really a pdf", "bad.pdf", "application/pdf")
    cv_id = response.json()["id"]
    result = client.post(f"/api/v1/cvs/{cv_id}/extract")
    assert result.status_code == 422
    assert "could not be opened" in result.json()["detail"].lower()


def test_filename_is_sanitised(client):
    client.get("/api/v1/candidate")
    response = _upload(client, _make_docx_bytes(), "../../evil name.docx", "application/pdf")
    assert response.status_code == 201
    assert ".." not in response.json()["filename"]
    assert response.json()["filename"] == "evil name.docx"
