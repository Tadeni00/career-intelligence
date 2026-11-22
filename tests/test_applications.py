"""Application tracking."""

from __future__ import annotations


def _setup(client):
    client.get("/api/v1/candidate")
    client.put(
        "/api/v1/candidate",
        json={
            "name": "Tommie",
            "professional_title": "Machine Learning Engineer",
            "location": "Amsterdam",
            "years_of_experience": 6,
        },
    )
    for skill in ["Python", "SQL", "Machine Learning"]:
        client.post("/api/v1/candidate/skills", json={"name": skill})
    client.post(
        "/api/v1/candidate/experience",
        json={
            "company": "Fintech Systems",
            "title": "Machine Learning Engineer",
            "start_date": "2021",
            "description": "Built fraud detection models.",
        },
    )


def _create_job(client, title="Machine Learning Engineer", company="Fintech Corp"):
    job = client.post(
        "/api/v1/jobs",
        json={
            "title": title,
            "company": company,
            "location": "Amsterdam",
            "remote_status": "Hybrid",
            "description": "Required: Python, Machine Learning, SQL.",
        },
    ).json()
    # V3.1: a job is only matchable once its requirements are extracted. Before
    # V3.1 these tests matched a requirement-less job on neutral defaults.
    extracted = client.post(f"/api/v1/jobs/{job['id']}/extract-requirements")
    assert extracted.status_code == 200, extracted.text
    return extracted.json()


def test_create_application(client):
    _setup(client)
    job = _create_job(client)
    match = client.post(f"/api/v1/jobs/{job['id']}/match").json()

    response = client.post(
        "/api/v1/applications",
        json={"job_id": job["id"], "match_id": match["id"]},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["job_id"] == job["id"]
    assert data["match_id"] == match["id"]
    assert data["status"] == "INTERESTED"


def test_duplicate_application_rejected(client):
    _setup(client)
    job = _create_job(client)
    client.post("/api/v1/applications", json={"job_id": job["id"]})

    response = client.post("/api/v1/applications", json={"job_id": job["id"]})
    assert response.status_code == 409


def test_update_application_status(client):
    _setup(client)
    job = _create_job(client)
    app = client.post("/api/v1/applications", json={"job_id": job["id"]}).json()

    response = client.put(
        f"/api/v1/applications/{app['id']}", json={"status": "APPLIED"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "APPLIED"
    assert response.json()["applied_at"] is not None


def test_application_with_cv_and_cover_letter(client):
    _setup(client)
    job = _create_job(client)
    match = client.post(f"/api/v1/jobs/{job['id']}/match").json()
    cv = client.post(f"/api/v1/jobs/{job['id']}/tailor-cv").json()
    letter = client.post(f"/api/v1/jobs/{job['id']}/cover-letter").json()

    response = client.post(
        "/api/v1/applications",
        json={
            "job_id": job["id"],
            "match_id": match["id"],
            "tailored_cv_id": cv["id"],
            "cover_letter_id": letter["id"],
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["tailored_cv_id"] == cv["id"]
    assert data["cover_letter_id"] == letter["id"]


def test_list_applications(client):
    _setup(client)
    job1 = _create_job(client, title="ML Engineer", company="A")
    job2 = _create_job(client, title="Data Scientist", company="B")
    client.post("/api/v1/applications", json={"job_id": job1["id"]})
    client.post("/api/v1/applications", json={"job_id": job2["id"]})

    response = client.get("/api/v1/applications")
    assert response.status_code == 200
    assert len(response.json()) == 2


def test_filter_applications_by_status(client):
    _setup(client)
    job1 = _create_job(client, title="ML Engineer", company="A")
    job2 = _create_job(client, title="Data Scientist", company="B")
    app1 = client.post("/api/v1/applications", json={"job_id": job1["id"]}).json()
    client.post("/api/v1/applications", json={"job_id": job2["id"]})
    client.put(f"/api/v1/applications/{app1['id']}", json={"status": "APPLIED"})

    response = client.get("/api/v1/applications?status_filter=APPLIED")
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["status"] == "APPLIED"


def test_dashboard(client):
    _setup(client)
    job = _create_job(client)
    client.post(f"/api/v1/jobs/{job['id']}/match")
    client.post("/api/v1/applications", json={"job_id": job["id"]})

    response = client.get("/api/v1/dashboard")
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["jobs"] == 1
    assert data["stats"]["applications"] == 1
    assert len(data["opportunities"]) == 1
    assert data["opportunities"][0]["title"] == "Machine Learning Engineer"


def test_job_listing_with_match(client):
    _setup(client)
    job = _create_job(client)
    client.post(f"/api/v1/jobs/{job['id']}/match")

    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["latest_match"] is not None
    assert data[0]["latest_match"]["overall_score"] > 0


def test_job_filter_by_recommendation(client):
    _setup(client)
    job = _create_job(client)
    match = client.post(f"/api/v1/jobs/{job['id']}/match").json()

    response = client.get(f"/api/v1/jobs?recommendation={match['recommendation']}")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_job_sort_by_match(client):
    _setup(client)
    job1 = _create_job(client, title="ML Engineer", company="A")
    job2 = _create_job(client, title="Data Scientist", company="B")
    client.post(f"/api/v1/jobs/{job1['id']}/match")
    client.post(f"/api/v1/jobs/{job2['id']}/match")

    response = client.get("/api/v1/jobs?sort=match")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["latest_match"]["overall_score"] >= data[1]["latest_match"]["overall_score"]
