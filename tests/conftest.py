"""Shared pytest fixtures.

Tests run against an isolated database so they never touch development data.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for extra in (ROOT / "apps" / "api", ROOT / "packages" / "matching",
              ROOT / "validation_jobs"):
    if str(extra) not in os.sys.path:
        os.sys.path.insert(0, str(extra))

TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://career:career@localhost:5433/career_test"
)

os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["AI_PROVIDER"] = "offline"
os.environ["ENVIRONMENT"] = "test"
os.environ.setdefault(
    "STORAGE_DIR", str(ROOT / "storage" / "test"),
)

from app.core.config import get_settings  # noqa: E402

settings = get_settings()

import app.models  # noqa: E402,F401
from app.db.session import Base, SessionLocal, engine  # noqa: E402


def _ensure_test_database() -> None:
    from sqlalchemy import create_engine, text

    target = engine.url
    # render_as_string is required: str(url) masks the password.
    admin_url = target.set(database="postgres").render_as_string(hide_password=False)
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": target.database},
        ).scalar()
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{target.database}"'))
    admin.dispose()


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    if engine.dialect.name == "postgresql":
        _ensure_test_database()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    """Truncate all tables between tests while keeping the schema in place."""
    yield
    with engine.begin() as connection:
        tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
        if tables:
            connection.exec_driver_sql(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    from app.main import app
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def candidate(db):
    from app.models import Candidate

    record = Candidate(name="Test Candidate")
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@pytest.fixture
def sample_cv_text() -> str:
    return SAMPLE_CV


SAMPLE_CV = """
Tommie van der Berg
Senior Machine Learning Engineer
tommie@example.com | +31 6 1234 5678 | Amsterdam, Netherlands

Summary
Machine Learning Engineer with experience building and deploying statistical
models in production. Focused on fraud detection, model evaluation and
reliable data pipelines.

Experience

Machine Learning Engineer | Fintech Systems BV | 2021 - Present
- Built and deployed classification models for transaction fraud detection serving real-time traffic.
- Designed model evaluation pipelines covering offline metrics and online A/B testing.
- Reduced false positive rate by 30% through statistical analysis of model errors.

Data Scientist | Analytics Works | 2019 - 2021
- Developed statistical models for customer segmentation using Python and SQL.
- Built ETL data pipelines on PostgreSQL and ran model evaluation each release.

Education

MSc Data Science | University of Amsterdam | 2017 - 2019
BSc Statistics | Utrecht University | 2014 - 2017

Skills
Python, SQL, PostgreSQL, Statistics, Machine Learning, Model Evaluation, FastAPI, Docker

Projects
Fraud Detection Pipeline (Python, PostgreSQL)
Built an end-to-end fraud detection service, reducing manual review volume by 30%.

Certifications
AWS Machine Learning Specialty | Amazon Web Services | 2022
"""
