"""V2 strategy API, persistence and staleness tests (spec sections 25, 26, 28)."""

from __future__ import annotations

import pytest
from app.models import Job, JobRequirement, StrategyStatus
from app.services import strategy as strategy_service
from app.services import strategy_store
from app.services.candidate import to_profile_summary


def _seed_job(db, candidate, *, requirements=None, description="Python and SQL."):
    job = Job(title="Data Scientist", company="Acme", location="Amsterdam",
              description=description)
    db.add(job)
    db.commit()
    db.refresh(job)
    for name, importance, rtype in (requirements or [
        ("Python", "REQUIRED", "SKILL"),
        ("AWS", "REQUIRED", "SKILL"),
        ("Attention to detail", "PREFERRED", "OTHER"),
    ]):
        db.add(JobRequirement(job_id=job.id, requirement_type=rtype, name=name,
                              importance=importance))
    db.commit()
    db.refresh(job)
    return job


def _seed_candidate(db):
    from app.models import Candidate, CandidateSkill, Experience, Skill

    cand = Candidate(name="Tommie van der Berg", professional_title="Data Scientist",
                     location="Amsterdam", years_of_experience=6,
                     summary="Data professional focused on quantitative analysis.")
    db.add(cand)
    db.commit()
    db.refresh(cand)
    for name in ("Python", "SQL"):
        skill = Skill(name=name, category="technical")
        db.add(skill)
        db.commit()
        db.refresh(skill)
        db.add(CandidateSkill(candidate_id=cand.id, skill_id=skill.id))
    db.add(Experience(candidate_id=cand.id, company="Fintech Systems",
                      title="Data Scientist", start_date="2021", is_current=True,
                      description="Built automated data pipelines supporting "
                                  "repeatable validation workflows."))
    db.commit()
    db.refresh(cand)
    return cand


# --------------------------------------------------------------------------- #
# persistence
# --------------------------------------------------------------------------- #


def test_strategy_is_persisted_and_reloadable(db, candidate):
    from app.services.matching import run_match

    job = _seed_job(db, candidate)
    match = run_match(db, candidate, job)
    profile = to_profile_summary(candidate)

    strategy, issues = strategy_store.build_for_match(db, profile, job, match)
    record = strategy_store.persist(
        db, candidate.id, job, match, strategy,
        strategy_service.evidence_fingerprint(profile, job),
    )
    assert record.version == 1
    assert record.status == StrategyStatus.CURRENT.value

    stored = strategy_store.latest_for_job(db, candidate.id, job.id)
    assert stored is not None
    restored = strategy_store.to_strategy(stored)
    assert restored.decision == match.recommendation
    assert len(restored.gaps) == len(strategy.gaps)
    assert len(restored.strengths) == len(strategy.strengths)


def test_new_strategy_version_marks_previous_stale(db, candidate):
    from app.services.matching import run_match

    job = _seed_job(db, candidate)
    match = run_match(db, candidate, job)
    profile = to_profile_summary(candidate)
    fp = strategy_service.evidence_fingerprint(profile, job)

    first, _ = strategy_store.build_for_match(db, profile, job, match)
    strategy_store.persist(db, candidate.id, job, match, first, fp)
    second, _ = strategy_store.build_for_match(db, profile, job, match)
    record2 = strategy_store.persist(db, candidate.id, job, match, second, fp)

    assert record2.version == 2
    history = db.query(type(record2)).filter(
        type(record2).candidate_id == candidate.id).all()
    statuses = sorted(r.version for r in history if r.status == StrategyStatus.STALE.value)
    assert statuses == [1]


def test_strategy_never_mutates_the_profile(db, candidate):
    from app.services.matching import run_match

    job = _seed_job(db, candidate)
    match = run_match(db, candidate, job)
    before = to_profile_summary(candidate).model_dump_json()

    profile = to_profile_summary(candidate)
    strategy, _ = strategy_store.build_for_match(db, profile, job, match)
    strategy_store.persist(
        db, candidate.id, job, match, strategy,
        strategy_service.evidence_fingerprint(profile, job),
    )
    db.refresh(candidate)
    assert to_profile_summary(candidate).model_dump_json() == before


# --------------------------------------------------------------------------- #
# staleness (section 26)
# --------------------------------------------------------------------------- #


def test_stale_strategy_is_rebuilt_when_evidence_changes(db, candidate):
    from app.services.matching import run_match

    job = _seed_job(db, candidate)
    match = run_match(db, candidate, job)

    profile = to_profile_summary(candidate)
    strategy, _ = strategy_store.build_for_match(db, profile, job, match)
    strategy_store.persist(
        db, candidate.id, job, match, strategy,
        strategy_service.evidence_fingerprint(profile, job),
    )

    # A second match (new evidence state) must not silently reuse the strategy.
    match2 = run_match(db, candidate, job)
    record, _issues, rebuilt = strategy_store.refresh_if_stale(
        db, to_profile_summary(candidate), job, match2
    )
    assert rebuilt is True
    assert record.version == 2


def test_current_strategy_is_not_rebuilt(db, candidate):
    from app.services.matching import run_match

    job = _seed_job(db, candidate)
    match = run_match(db, candidate, job)
    profile = to_profile_summary(candidate)
    strategy, _ = strategy_store.build_for_match(db, profile, job, match)
    strategy_store.persist(db, candidate.id, job, match, strategy,
                           strategy_service.evidence_fingerprint(profile, job))

    record, _issues, rebuilt = strategy_store.refresh_if_stale(
        db, to_profile_summary(candidate), job, match
    )
    assert rebuilt is False
    assert record.version == 1


def test_changed_requirements_invalidate_strategy(db, candidate):
    from app.services.matching import run_match

    job = _seed_job(db, candidate)
    match = run_match(db, candidate, job)
    profile = to_profile_summary(candidate)
    strategy, _ = strategy_store.build_for_match(db, profile, job, match)
    strategy_store.persist(db, candidate.id, job, match, strategy,
                           strategy_service.evidence_fingerprint(profile, job))

    db.add(JobRequirement(job_id=job.id, requirement_type="SKILL",
                          name="Kubernetes", importance="REQUIRED"))
    db.commit()
    db.refresh(job)

    _record, _issues, rebuilt = strategy_store.refresh_if_stale(
        db, to_profile_summary(candidate), job, match
    )
    assert rebuilt is True


# --------------------------------------------------------------------------- #
# API surface
# --------------------------------------------------------------------------- #


def test_get_strategy_endpoint(client, db, candidate):
    from app.services.matching import run_match

    job = _seed_job(db, candidate)
    run_match(db, candidate, job)
    response = client.get(f"/api/v1/jobs/{job.id}/strategy")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["status"] == StrategyStatus.CURRENT.value
    assert data["decision"] in {"APPLY", "APPLY_WITH_TAILORING", "STRETCH", "SKIP"}
    assert "claim_restrictions" in data
    assert "actions" in data


def test_strategy_endpoint_conflicts_without_match(client, db, candidate):
    job = _seed_job(db, candidate)
    response = client.get(f"/api/v1/jobs/{job.id}/strategy")
    assert response.status_code == 409


def test_strategy_history_endpoint(client, db, candidate):
    from app.services.matching import run_match

    job = _seed_job(db, candidate)
    match = run_match(db, candidate, job)
    profile = to_profile_summary(candidate)
    for _ in range(2):
        strategy, _ = strategy_store.build_for_match(db, profile, job, match)
        strategy_store.persist(
            db, candidate.id, job, match, strategy,
            strategy_service.evidence_fingerprint(profile, job),
        )
    response = client.get(f"/api/v1/jobs/{job.id}/strategy/history")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert [r["version"] for r in rows] == [2, 1]


def test_strategy_does_not_bypass_validation(client, db, candidate):
    """A valid strategy must not make an unsupported document acceptable."""
    from app.services.matching import run_match

    job = _seed_job(db, candidate)
    run_match(db, candidate, job)
    strategy = client.get(f"/api/v1/jobs/{job.id}/strategy").json()

    letter = (
        "Dear Hiring Team,\n\n"
        "I reduced model error by 30% and deployed models to AWS.\n\n"
        "Kind regards,\nTommie van der Berg"
    )
    from app.services.validation import validate_cover_letter

    report = validate_cover_letter(letter, to_profile_summary(candidate),
                                   job.title, job.company)
    assert report.status.value == "VALIDATION_FAILED"
    assert strategy["decision"]  # the strategy existed and was still overridden


@pytest.mark.parametrize("payload", [
    "BRIGHTEST #RMTM3LjI1NS4xNzcuMTU3",
    "I am authorized to work in the United States.",
])
def test_strategy_layer_preserves_v12_safety(client, db, candidate, payload):
    from app.services.matching import run_match
    from app.services.validation import validate_cover_letter

    job = _seed_job(db, candidate)
    run_match(db, candidate, job)
    client.get(f"/api/v1/jobs/{job.id}/strategy")
    report = validate_cover_letter(
        f"Dear Hiring Team,\n\n{payload}\n\nKind regards",
        to_profile_summary(candidate), job.title, job.company,
    )
    assert report.status.value == "VALIDATION_FAILED"
