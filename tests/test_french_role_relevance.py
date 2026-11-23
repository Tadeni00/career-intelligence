"""Focused bilingual title-alignment tests; not CV matching validation."""
import pytest

from app.services.search_relevance import classify_search_relevance


@pytest.mark.parametrize(
    ("query", "title", "expected"),
    [
        ("data analyst", "Analyste de données — Cotonou", "Aligned"),
        ("analyste de données", "Data Analyst", "Aligned"),
        ("data scientist", "Scientifique des données", "Aligned"),
        ("machine learning engineer", "Ingénieure en apprentissage automatique", "Aligned"),
        ("data analyst", "Ingénieur des données", "Adjacent"),
        ("data analyst", "Scientifique des données", "Mismatch"),
        ("data scientist", "Formation en science des données", "Mismatch"),
        ("data analyst", "Responsable marketing", "Uncertain"),
        ("data analyst", "Data analyst", "Aligned"),
    ],
)
def test_bilingual_role_title_relevance(query, title, expected):
    assert classify_search_relevance(query, title).label == expected


def test_accented_title_does_not_require_external_translation():
    assert classify_search_relevance("Data Analyst", "Analyste de données").label == "Aligned"
