"""Regression tests for discovered-job detail serialization of persisted matches.

`MatchResult` stores its four item collections in ``Text`` columns holding JSON
arrays. ``MatchOut`` declares them as ``list[MatchItemOut]``. Validating the ORM
object directly therefore feeds raw ``str`` values into Pydantic and raises,
producing HTTP 500 for every discovered job that has a persisted match.

These tests build their own fixtures inside the isolated test database. They do
not read or depend on any development or production match record.
"""

from __future__ import annotations

import json

import pytest


def _make_discovered_job(db, **overrides) -> int:
    from app.models import Job

    payload = dict(
        title="Senior Data Scientist",
        company="Kuda Microfinance Bank",
        location="Lagos, Nigeria",
        url="https://employ.ng/jobs/senior-data-scientist",
        source="jsearch",
        source_id="serialization-probe-1",
        external_id="jsearch:serialization-probe-1",
        is_discovered=True,
        description="Required: Python, SQL, and 5+ years of experience.",
    )
    payload.update(overrides)
    job = Job(**payload)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job.id


def _make_match(db, candidate_id: int, job_id: int, **item_columns):
    """Persist a MatchResult exactly as run_match() would: JSON text columns."""

    from app.models import MatchResult

    defaults = {
        "matched_items": "[]",
        "gap_items": "[]",
        "blocker_items": "[]",
        "unknown_items": "[]",
    }
    defaults.update(item_columns)

    match = MatchResult(
        candidate_id=candidate_id,
        job_id=job_id,
        technical_score=81.5,
        experience_score=70.0,
        education_score=60.0,
        location_score=90.0,
        other_score=55.0,
        overall_score=76.25,
        recommendation="APPLY_WITH_TAILORING",
        confidence=0.82,
        explanation="Strong technical overlap with a location gap.",
        **defaults,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match


MATCHED = json.dumps(
    [
        {
            "category": "SKILL",
            "name": "Python",
            "detail": "Appears in the confirmed evidence.",
            "importance": "REQUIRED",
        }
    ]
)
GAPS = json.dumps(
    [
        {
            "category": "SKILL",
            "name": "Kubernetes",
            "detail": "Not evidenced in the confirmed profile.",
            "importance": "PREFERRED",
        }
    ]
)
BLOCKERS = json.dumps(
    [
        {
            "category": "LOCATION",
            "name": "On-site in Germany",
            "detail": "Role is not available in the candidate's location.",
            "importance": "REQUIRED",
        }
    ]
)
UNKNOWNS = json.dumps(
    [
        {
            "category": "EDUCATION",
            "name": "Doctorate",
            "detail": "Not stated in the vacancy.",
            "importance": "UNKNOWN",
        }
    ]
)


class TestDiscoveredJobDetailWithPersistedMatch:
    """The previously untested path: GET /jobs/discovered/{id} with a match."""

    def test_populated_arrays_serialize_as_lists(self, client, db, candidate):
        job_id = _make_discovered_job(db)
        _make_match(
            db,
            candidate.id,
            job_id,
            matched_items=MATCHED,
            gap_items=GAPS,
            blocker_items=BLOCKERS,
            unknown_items=UNKNOWNS,
        )

        response = client.get(f"/api/v1/jobs/discovered/{job_id}")

        assert response.status_code == 200, response.text
        match = response.json()["match"]
        assert match is not None
        assert match["matched_items"] == [
            {
                "category": "SKILL",
                "name": "Python",
                "detail": "Appears in the confirmed evidence.",
                "importance": "REQUIRED",
            }
        ]
        assert [i["name"] for i in match["gap_items"]] == ["Kubernetes"]
        assert [i["name"] for i in match["blocker_items"]] == ["On-site in Germany"]
        assert [i["name"] for i in match["unknown_items"]] == ["Doctorate"]

    def test_empty_arrays_serialize_as_empty_lists(self, client, db, candidate):
        job_id = _make_discovered_job(db)
        _make_match(db, candidate.id, job_id)

        response = client.get(f"/api/v1/jobs/discovered/{job_id}")

        assert response.status_code == 200, response.text
        match = response.json()["match"]
        assert match["matched_items"] == []
        assert match["gap_items"] == []
        assert match["blocker_items"] == []
        assert match["unknown_items"] == []

    def test_null_collections_serialize_as_empty_lists(self, client, db, candidate):
        """A NULL column is optional per MatchOut and must not raise."""

        job_id = _make_discovered_job(db)
        _make_match(
            db,
            candidate.id,
            job_id,
            matched_items=None,
            gap_items=None,
            blocker_items=None,
            unknown_items=None,
        )

        response = client.get(f"/api/v1/jobs/discovered/{job_id}")

        assert response.status_code == 200, response.text
        match = response.json()["match"]
        assert match["matched_items"] == []
        assert match["gap_items"] == []
        assert match["blocker_items"] == []
        assert match["unknown_items"] == []

    def test_malformed_collection_is_handled_conservatively(self, client, db, candidate):
        """Legacy garbage must not 500, and must not invent evidence."""

        job_id = _make_discovered_job(db)
        _make_match(
            db,
            candidate.id,
            job_id,
            matched_items="{not valid json",
            gap_items="{}",
            blocker_items="null",
            unknown_items='"a string"',
        )

        response = client.get(f"/api/v1/jobs/discovered/{job_id}")

        assert response.status_code == 200, response.text
        match = response.json()["match"]
        assert match["matched_items"] == []
        assert match["gap_items"] == []
        assert match["blocker_items"] == []
        assert match["unknown_items"] == []

    def test_scores_and_recommendation_are_unchanged(self, client, db, candidate):
        job_id = _make_discovered_job(db)
        _make_match(db, candidate.id, job_id, matched_items=MATCHED)

        response = client.get(f"/api/v1/jobs/discovered/{job_id}")

        assert response.status_code == 200, response.text
        match = response.json()["match"]
        assert match["technical_score"] == 81.5
        assert match["experience_score"] == 70.0
        assert match["education_score"] == 60.0
        assert match["location_score"] == 90.0
        assert match["other_score"] == 55.0
        assert match["overall_score"] == 76.25
        assert match["recommendation"] == "APPLY_WITH_TAILORING"
        assert match["confidence"] == 0.82
        assert match["explanation"] == "Strong technical overlap with a location gap."
        assert match["candidate_id"] == candidate.id
        assert match["job_id"] == job_id

    def test_collections_conform_to_match_item_schema(self, client, db, candidate):
        job_id = _make_discovered_job(db)
        _make_match(
            db,
            candidate.id,
            job_id,
            matched_items=MATCHED,
            gap_items=GAPS,
            blocker_items=BLOCKERS,
            unknown_items=UNKNOWNS,
        )

        body = client.get(f"/api/v1/jobs/discovered/{job_id}").json()
        match = body["match"]

        assert match is not None
        for key in ("matched_items", "gap_items", "blocker_items", "unknown_items"):
            assert isinstance(match[key], list), key
            for item in match[key]:
                assert set(item) == {"category", "name", "detail", "importance"}, key

    def test_stored_match_row_is_not_modified_by_reading(self, client, db, candidate):
        """Serializing a match must not rewrite its stored values."""

        job_id = _make_discovered_job(db)
        match = _make_match(db, candidate.id, job_id, matched_items=MATCHED)
        stored_before = (
            match.matched_items,
            match.gap_items,
            match.blocker_items,
            match.unknown_items,
        )

        client.get(f"/api/v1/jobs/discovered/{job_id}")

        db.expire_all()
        reloaded = db.get(type(match), match.id)
        assert reloaded.matched_items == stored_before[0]
        assert reloaded.gap_items == stored_before[1]
        assert reloaded.blocker_items == stored_before[2]
        assert reloaded.unknown_items == stored_before[3]


class TestDiscoveredJobDetailWithoutMatch:
    """The previously covered path must keep working."""

    def test_no_match_returns_null_match(self, client, db, candidate):
        job_id = _make_discovered_job(db)

        response = client.get(f"/api/v1/jobs/discovered/{job_id}")

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["match"] is None
        assert body["job"]["id"] == job_id

    def test_unknown_job_still_returns_404(self, client, db, candidate):
        assert client.get("/api/v1/jobs/discovered/999999").status_code == 404

    def test_existing_detail_signals_still_present(self, client, db, candidate):
        job_id = _make_discovered_job(db)
        _make_match(db, candidate.id, job_id, matched_items=MATCHED)

        body = client.get(
            f"/api/v1/jobs/discovered/{job_id}", params={"query": "Senior Data Scientist"}
        ).json()

        assert body["search_relevance"]["label"] == "Aligned"
        assert body["freshness"]["status"] in {"current", "stale", "unknown"}
        assert "duplicate_review" in body
        assert body["job"]["url"] == "https://employ.ng/jobs/senior-data-scientist"


class TestItemDecoderBoundary:
    """Values that cannot be produced through persistence are checked directly.

    ``MatchResult`` stores the collections in ``Text`` columns, so a pre-decoded
    ``list`` can only reach the decoder if the column type ever changes or an
    object is held in the identity map. The decoder must survive that without
    double-decoding.
    """

    def test_already_decoded_list_is_not_double_decoded(self):
        from app.api.routes.matches import _items

        decoded = [{"category": "SKILL", "name": "SQL", "detail": "d", "importance": "REQUIRED"}]
        assert [i.name for i in _items(decoded)] == ["SQL"]

    def test_falsy_values_yield_empty_list(self):
        from app.api.routes.matches import _items

        assert _items(None) == []
        assert _items("") == []

    def test_non_list_json_yields_empty_list(self):
        from app.api.routes.matches import _items

        assert _items("{}") == []
        assert _items("null") == []
        assert _items('"text"') == []
        assert _items("42") == []

    def test_item_optional_fields_are_defaulted(self):
        from app.api.routes.matches import _items

        items = _items(json.dumps([{"category": "SKILL", "name": "Go"}]))
        assert items[0].detail == ""
        assert items[0].importance == "UNKNOWN"


class TestMatchEndpointsShareTheSameShape:
    """The discovery detail response must agree with the /matches endpoints."""

    def test_discovery_detail_matches_direct_match_endpoint(self, client, db, candidate):
        job_id = _make_discovered_job(db)
        _make_match(
            db,
            candidate.id,
            job_id,
            matched_items=MATCHED,
            gap_items=GAPS,
            blocker_items=BLOCKERS,
            unknown_items=UNKNOWNS,
        )

        discovered = client.get(f"/api/v1/jobs/discovered/{job_id}").json()["match"]
        direct = client.get(f"/api/v1/jobs/{job_id}/match").json()

        for key in (
            "id",
            "candidate_id",
            "job_id",
            "technical_score",
            "experience_score",
            "education_score",
            "location_score",
            "other_score",
            "overall_score",
            "recommendation",
            "confidence",
            "matched_items",
            "gap_items",
            "blocker_items",
            "unknown_items",
            "explanation",
        ):
            assert discovered[key] == direct[key], key


@pytest.mark.parametrize("field", ["matched_items", "gap_items", "blocker_items", "unknown_items"])
def test_each_collection_is_independently_decoded(client, db, candidate, field):
    """One populated collection at a time: each column decodes on its own."""

    job_id = _make_discovered_job(db)
    columns = {field: MATCHED}
    _make_match(db, candidate.id, job_id, **columns)

    response = client.get(f"/api/v1/jobs/discovered/{job_id}")

    assert response.status_code == 200, response.text
    match = response.json()["match"]
    assert len(match[field]) == 1
    assert match[field][0]["name"] == "Python"
    for other in {"matched_items", "gap_items", "blocker_items", "unknown_items"} - {field}:
        assert match[other] == []
