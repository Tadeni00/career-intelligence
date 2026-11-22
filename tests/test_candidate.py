"""Career profile CRUD."""

from __future__ import annotations


def test_get_profile_creates_candidate(client):
    response = client.get("/api/v1/candidate")
    assert response.status_code == 200
    assert response.json()["name"] == "Candidate"


def test_update_profile(client):
    client.get("/api/v1/candidate")
    response = client.put(
        "/api/v1/candidate",
        json={
            "name": "Tommie",
            "professional_title": "Data Scientist | Machine Learning Engineer",
            "location": "Amsterdam",
            "years_of_experience": 6,
            "preferred_roles": ["Data Scientist", "Machine Learning Engineer"],
            "preferred_locations": ["Amsterdam", "Utrecht"],
            "remote_preference": "HYBRID",
            "minimum_salary": 70000,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Tommie"
    assert data["preferred_roles"] == ["Data Scientist", "Machine Learning Engineer"]
    assert data["minimum_salary"] == 70000

    # Persisted
    again = client.get("/api/v1/candidate").json()
    assert again["location"] == "Amsterdam"


def test_skill_lifecycle(client):
    client.get("/api/v1/candidate")
    created = client.post(
        "/api/v1/candidate/skills",
        json={"name": "Python", "category": "Programming", "years_experience": 6},
    )
    assert created.status_code == 201
    skill_id = created.json()["id"]
    assert created.json()["name"] == "Python"

    # Adding the same skill again updates rather than duplicating.
    again = client.post("/api/v1/candidate/skills", json={"name": "Python"})
    assert again.json()["id"] == skill_id
    assert len(client.get("/api/v1/candidate/skills").json()) == 1

    assert client.delete(f"/api/v1/candidate/skills/{skill_id}").status_code == 204
    assert client.get("/api/v1/candidate/skills").json() == []


def test_experience_lifecycle(client):
    client.get("/api/v1/candidate")
    created = client.post(
        "/api/v1/candidate/experience",
        json={
            "company": "Fintech Systems",
            "title": "Machine Learning Engineer",
            "start_date": "2021-01",
            "description": "Built fraud detection models.",
        },
    )
    assert created.status_code == 201
    exp_id = created.json()["id"]
    assert created.json()["is_current"] is True

    updated = client.put(
        f"/api/v1/candidate/experience/{exp_id}", json={"title": "Senior ML Engineer"}
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Senior ML Engineer"

    assert len(client.get("/api/v1/candidate/experience").json()) == 1
    assert client.delete(f"/api/v1/candidate/experience/{exp_id}").status_code == 204
    assert client.get("/api/v1/candidate/experience").json() == []


def test_education_lifecycle(client):
    client.get("/api/v1/candidate")
    created = client.post(
        "/api/v1/candidate/education",
        json={
            "institution": "University of Amsterdam",
            "degree": "MSc",
            "field": "Data Science",
            "end_date": "2019",
        },
    )
    assert created.status_code == 201
    edu_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/candidate/education/{edu_id}", json={"degree": "MSc (cum laude)"}
    )
    assert updated.json()["degree"] == "MSc (cum laude)"

    assert client.delete(f"/api/v1/candidate/education/{edu_id}").status_code == 204


def test_project_lifecycle(client):
    client.get("/api/v1/candidate")
    created = client.post(
        "/api/v1/candidate/projects",
        json={
            "name": "Fraud Detection Pipeline",
            "description": "End-to-end fraud detection service.",
            "technologies": ["Python", "PostgreSQL"],
        },
    )
    assert created.status_code == 201
    assert created.json()["technologies"] == ["Python", "PostgreSQL"]
    project_id = created.json()["id"]

    updated = client.put(
        f"/api/v1/candidate/projects/{project_id}",
        json={"technologies": ["Python", "PostgreSQL", "Docker"]},
    )
    assert updated.json()["technologies"] == ["Python", "PostgreSQL", "Docker"]

    assert client.delete(f"/api/v1/candidate/projects/{project_id}").status_code == 204


def test_ownership_is_enforced(client):
    client.get("/api/v1/candidate")
    created = client.post(
        "/api/v1/candidate/experience", json={"company": "A", "title": "B"}
    )
    exp_id = created.json()["id"]
    assert client.put(f"/api/v1/candidate/experience/{exp_id + 999}", json={}).status_code == 404
    assert client.delete(f"/api/v1/candidate/experience/{exp_id + 999}").status_code == 404
