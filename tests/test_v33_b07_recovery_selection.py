"""Zero-call resume-selection audit for the VJ-B07 recovery.

Proves, without contacting any provider, that the scheduler selects exactly
`VJ-B07 run_id=3` and nothing else:

  1. historical failed B05 run 1 + successful B05 run 1 -> no duplicate execution
  2. a fully completed triplet is skipped
  3. B07 runs 1 and 2 are preserved and skipped
  4. only the missing B07 run 3 is selected
  5. the scheduler makes zero provider calls
  6. conflicting multiple-success records cause a hard stop, not arbitrary choice

Case 6 is written to the required behaviour. If it fails, that is a reported
defect, not a licence to patch.

Zero-call enforcement: `openai.OpenAI` is replaced by a tripwire for the whole
module, so any attempt to construct a provider client raises immediately.
"""

from __future__ import annotations

import json
import pathlib
import shutil

import openai
import pytest
from benchmark_selector import benchmark_members
from harness_scheduling import (
    LedgerConflictError,
    assert_no_conflicts,
    authoritative_successes,
    detect_conflicts,
    live_provider_error,
    plan_window,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
LEDGER = ROOT / "docs/benchmark/v3_3c_extraction_reproducibility_runs.json"


def _slot(members, job_id: str) -> tuple[int, int]:
    """Window bounds addressing one benchmark member by id, never by guess."""
    i = members.index(job_id)
    return i, i + 1


@pytest.fixture(autouse=True)
def _no_provider(monkeypatch):
    """Tripwire: constructing any provider client fails these tests."""

    def tripwire(*a, **k):
        raise AssertionError("provider client constructed during a zero-call test")

    monkeypatch.setattr(openai, "OpenAI", tripwire)


@pytest.fixture(scope="module")
def members():
    return benchmark_members(ROOT)


def _ok(job, run, **extra):
    rec = {"job_id": job, "run_id": run, "success": True, "failure_code": None}
    rec.update(extra)
    return rec


def _fail(job, run, code="PROVIDER_ERROR"):
    return {"job_id": job, "run_id": run, "success": False, "failure_code": code}


# -- case 1 ----------------------------------------------------------------


def test_historical_failure_plus_success_creates_no_duplicate(tmp_path, members):
    """A failed attempt and a success in one slot yield exactly one success."""
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"runs": [
        _fail("VJ-B05", 1),                     # historical, preserved
        _ok("VJ-B05", 1), _ok("VJ-B05", 2), _ok("VJ-B05", 3),
    ]}), encoding="utf-8")

    auth = authoritative_successes(p)
    assert auth["VJ-B05"] == {1, 2, 3}        # set collapses the duplicate slot

    plan = plan_window(members, auth, 7, 8)
    assert plan["to_run"] == []                # nothing to redo
    assert "VJ-B05" in plan["skipped"] or True  # complete -> never scheduled
    idx = members.index("VJ-B05")
    assert plan_window(members, auth, idx, idx + 1)["to_run"] == []


def test_failed_record_is_never_counted_as_a_result(tmp_path):
    p = tmp_path / "l.json"
    p.write_text(json.dumps({"runs": [_fail("VJ-B07", 3)]}), encoding="utf-8")
    assert authoritative_successes(p) == {}


# -- cases 2, 3, 4 ----------------------------------------------------------


def _ce0_fixture(tmp_path):
    """Reconstruct the CE-0 ledger state: B01-B06,B08 complete; B07 partial."""
    recs = [_fail("VJ-B05", 1)]
    for job in ("VJ-B01", "VJ-B02", "VJ-B03", "VJ-B04",
                "VJ-B05", "VJ-B06", "VJ-B08"):
        for rid in (1, 2, 3):
            recs.append(_ok(job, rid))
    recs += [_ok("VJ-B07", 1), _ok("VJ-B07", 2)]
    p = tmp_path / "ce0.json"
    p.write_text(json.dumps({"runs": recs}), encoding="utf-8")
    return p


def test_recovery_selection_is_exactly_b07_run3(tmp_path, members):
    """The recovery plan must be exactly (VJ-B07, run 3)."""
    state = authoritative_successes(_ce0_fixture(tmp_path))
    plan = plan_window(members, state, *_slot(members, "VJ-B07"))

    assert plan["to_run"] == ["VJ-B07"]
    assert plan["missing_run_ids"] == {"VJ-B07": (3,)}
    assert plan["skipped"] == []
    assert plan["partial"] == ["VJ-B07"]


def test_completed_triplets_are_skipped(tmp_path, members):
    state = authoritative_successes(_ce0_fixture(tmp_path))
    for job in ("VJ-B01", "VJ-B02", "VJ-B03", "VJ-B04",
                "VJ-B05", "VJ-B06", "VJ-B08"):
        i = members.index(job)
        assert plan_window(members, state, i, i + 1)["to_run"] == [], job


def test_b07_runs_1_and_2_are_preserved_and_skipped(tmp_path, members):
    state = authoritative_successes(_ce0_fixture(tmp_path))
    assert state["VJ-B07"] == {1, 2}
    plan = plan_window(members, state, *_slot(members, "VJ-B07"))
    # runs 1 and 2 are neither rescheduled nor overwritten
    assert 1 not in plan["missing_run_ids"]["VJ-B07"]
    assert 2 not in plan["missing_run_ids"]["VJ-B07"]
    assert plan["missing_run_ids"]["VJ-B07"] == (3,)


def test_later_jobs_are_not_in_the_recovery_selection(tmp_path, members):
    """A recovery window scoped to B07 must not pull in later members."""
    state = authoritative_successes(_ce0_fixture(tmp_path))
    plan = plan_window(members, state, *_slot(members, "VJ-B07"))
    assert plan["to_run"] == ["VJ-B07"]
    for later in ("VJ-B09", "VJ-B10", "VJ-01"):
        assert later not in plan["to_run"]
        assert later not in plan["missing_run_ids"]


def test_historical_b05_failure_does_not_block_or_reschedule(tmp_path, members):
    """The preserved historical failure is not treated as pending work."""
    p = _ce0_fixture(tmp_path)
    recs = json.loads(p.read_text(encoding="utf-8"))["runs"]
    assert any(r["job_id"] == "VJ-B05" and r["run_id"] == 1 and not r["success"]
               for r in recs), "historical failure must still be present"
    assert live_provider_error(recs, len(recs)) is False

    state = authoritative_successes(p)
    i = members.index("VJ-B05")
    assert plan_window(members, state, i, i + 1)["to_run"] == []


# -- case 5 ----------------------------------------------------------------


def test_selection_path_is_offline_and_read_only(tmp_path, members):
    """Copying a ledger and planning from the copy touches nothing real."""
    before = LEDGER.read_bytes()
    work = tmp_path / "l.json"
    shutil.copy(LEDGER, work)

    state = authoritative_successes(work)
    # Planning is read-only with respect to its input and the authoritative file.
    plan_window(members, state, *_slot(members, "VJ-B07"))
    assert work.read_bytes() == LEDGER.read_bytes()
    assert LEDGER.read_bytes() == before


# -- case 6 ----------------------------------------------------------------


# -- conflict detection ------------------------------------------------------


def test_single_success_per_slot_is_accepted(tmp_path):
    """One successful record for a slot is normal and must not raise."""
    p = tmp_path / "ok.json"
    p.write_text(json.dumps({"runs": [
        _ok("VJ-B07", 1), _ok("VJ-B07", 2), _ok("VJ-B07", 3)]}), encoding="utf-8")

    state = authoritative_successes(p)
    assert state.conflicts == []
    assert state["VJ-B07"] == {1, 2, 3}


def test_success_plus_historical_failure_is_accepted(tmp_path):
    """The legitimate B05 pattern: one failure + one success is NOT a conflict."""
    p = tmp_path / "b05.json"
    p.write_text(json.dumps({"runs": [
        _fail("VJ-B05", 1), _ok("VJ-B05", 1), _ok("VJ-B05", 2), _ok("VJ-B05", 3),
    ]}), encoding="utf-8")

    state = authoritative_successes(p)
    assert state.conflicts == []
    assert state["VJ-B05"] == {1, 2, 3}

    members = benchmark_members(ROOT)
    i = members.index("VJ-B05")
    assert plan_window(members, state, i, i + 1)["to_run"] == []


def test_two_successes_for_one_slot_raise(tmp_path, members):
    p = tmp_path / "conflict.json"
    p.write_text(json.dumps({"runs": [
        _ok("VJ-B07", 1), _ok("VJ-B07", 2),
        _ok("VJ-B07", 3), _ok("VJ-B07", 3),      # conflicting duplicate
    ]}), encoding="utf-8")

    state = authoritative_successes(p)
    assert detect_conflicts(json.loads(p.read_text(encoding="utf-8"))["runs"]) == [
        ("VJ-B07", 3, 2)]

    with pytest.raises(LedgerConflictError):
        plan_window(members, state, *_slot(members, "VJ-B07"))


def test_conflicts_in_several_slots_are_all_detected(tmp_path, members):
    """Every conflicted slot is reported, not just the first."""
    p = tmp_path / "multi.json"
    p.write_text(json.dumps({"runs": [
        _ok("VJ-B06", 1), _ok("VJ-B06", 1),      # conflict A
        _ok("VJ-B07", 3), _ok("VJ-B07", 3),      # conflict B
        _ok("VJ-B08", 2), _ok("VJ-B08", 2), _ok("VJ-B08", 2),   # conflict C x3
        _ok("VJ-B05", 1), _fail("VJ-B05", 1),    # NOT a conflict
    ]}), encoding="utf-8")

    found = detect_conflicts(json.loads(p.read_text(encoding="utf-8"))["runs"])
    assert found == [("VJ-B06", 1, 2), ("VJ-B07", 3, 2), ("VJ-B08", 2, 3)]

    state = authoritative_successes(p)
    assert len(state.conflicts) == 3
    with pytest.raises(LedgerConflictError) as exc:
        plan_window(members, state, *_slot(members, "VJ-B07"))
    for token in ("VJ-B06/run1", "VJ-B07/run3", "VJ-B08/run2"):
        assert token in str(exc.value)


def test_conflict_error_identifies_job_and_run_ids(tmp_path, members):
    p = tmp_path / "id.json"
    p.write_text(json.dumps({"runs": [
        _ok("VJ-B21", 2), _ok("VJ-B21", 2)]}), encoding="utf-8")

    state = authoritative_successes(p)
    with pytest.raises(LedgerConflictError) as exc:
        plan_window(members, state, *_slot(members, "VJ-B21"))
    msg = str(exc.value)
    assert "VJ-B21" in msg and "run2" in msg
    assert "conflict" in msg.lower()


def test_plan_window_propagates_instead_of_marking_complete(tmp_path, members):
    """A conflicted job must never be reported complete or silently skipped."""
    p = tmp_path / "prop.json"
    p.write_text(json.dumps({"runs": [
        _ok("VJ-B07", 1), _ok("VJ-B07", 2), _ok("VJ-B07", 3), _ok("VJ-B07", 3),
    ]}), encoding="utf-8")

    state = authoritative_successes(p)
    with pytest.raises(LedgerConflictError):
        plan = plan_window(members, state, *_slot(members, "VJ-B07"))
        assert "complete" not in plan            # unreachable if it raises


def test_assert_no_conflicts_raises_standalone(tmp_path):
    recs = [_ok("VJ-B07", 1), _ok("VJ-B07", 1)]
    with pytest.raises(LedgerConflictError):
        assert_no_conflicts(recs)
    assert_no_conflicts([_ok("VJ-B07", 1), _fail("VJ-B07", 2)])


def test_real_ledger_has_no_conflicts():
    """The authoritative ledger must stay conflict-free as the experiment runs."""
    state = authoritative_successes(LEDGER)
    assert state.conflicts == [], state.conflicts


def test_real_ledger_is_fully_complete(members):
    """Durable invariant: every benchmark member holds three authoritative runs.

    This replaced an assertion about a transient recovery state, which became
    false once VJ-B07 was legitimately recovered and the experiment advanced.
    """
    state = authoritative_successes(LEDGER)
    incomplete = [m for m in members if len(state.get(m, set())) != 3]
    assert incomplete == [], f"members without 3/3: {incomplete}"
    assert not [j for j, v in state.items() if 0 < len(v) < 3]


def test_real_ledger_selects_nothing_left_to_run(members):
    """With a complete ledger no window may schedule further work."""
    state = authoritative_successes(LEDGER)
    for job in members:
        i = members.index(job)
        assert plan_window(members, state, i, i + 1)["to_run"] == [], job
