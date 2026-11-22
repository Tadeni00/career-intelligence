"""Regression tests for the window-scoped quota guard.

The defect: the guard evaluated ``any(PROVIDER_ERROR for f in runs)`` over
*every* record loaded from disk, so a single historical 429 permanently blocked
every future window. The corrected semantics:

    A provider failure during the CURRENT invocation is a live stop signal.
    A historical provider failure is not.

All tests here are pure and offline. No provider is contacted and no window is
executed.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from benchmark_selector import benchmark_members
from harness_scheduling import (
    RUNS_PER_JOB,
    authoritative_successes,
    live_provider_error,
    plan_window,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
# The real frozen order, never an invented one.
MEMBERS = benchmark_members(ROOT)
BY_INDEX = {job_id: i for i, job_id in enumerate(MEMBERS)}
B01, B05, B06 = "VJ-B01", "VJ-B05", "VJ-B06"


def _ok(job_id: str, run_id: int) -> dict:
    return {"job_id": job_id, "run_id": run_id, "success": True,
            "failure_code": None}


def _boom(job_id: str, run_id: int) -> dict:
    return {"job_id": job_id, "run_id": run_id, "success": False,
            "failure_code": "PROVIDER_ERROR"}


# -- Test A -----------------------------------------------------------------


def test_historical_provider_failure_does_not_block_a_new_window():
    """A 429 recorded in an earlier window must not stop a fresh window."""
    historical = [_ok("VJ-B01", 1), _boom("VJ-B05", 1)]

    # This invocation appends nothing yet, so window_start == len(historical).
    window_start = len(historical)

    assert live_provider_error(historical, window_start) is False


def test_historical_failure_does_not_block_even_with_earlier_successes():
    """A long history ending in a failure still leaves the guard clear."""
    historical = [_ok("VJ-B01", 1), _ok("VJ-B01", 2), _ok("VJ-B01", 3),
                  _boom("VJ-B05", 1), _boom("VJ-B06", 1)]
    window_start = len(historical)

    assert live_provider_error(historical, window_start) is False


# -- Test B -----------------------------------------------------------------


def test_current_window_provider_failure_stops_execution():
    """A failure raised inside this window trips the guard immediately."""
    window_start = 2
    records = [_ok("VJ-B01", 1), _boom("VJ-B05", 1),   # historical
               _ok("VJ-B05", 2), _boom("VJ-B05", 3)]   # this window

    assert live_provider_error(records, window_start) is True


def test_boundary_is_respected_exactly():
    """A failure one position before the boundary must not trip the guard."""
    records = [_boom("VJ-B05", 1)]
    assert live_provider_error(records, 1) is False
    assert live_provider_error(records, 0) is True


# -- Test C -----------------------------------------------------------------


def test_historical_failure_plus_complete_triplets_skips_and_proceeds():
    """Complete triplets are skipped and the historical failure is ignored."""
    historical = []
    for job in (B01, "VJ-B02", "VJ-B03", "VJ-B04"):
        historical += [_ok(job, r) for r in (1, 2, 3)]
    historical.append(_boom(B05, 1))
    window_start = len(historical)

    authoritative = authoritative_successes_from(historical)
    first = BY_INDEX[B01]
    last = BY_INDEX["VJ-B08"]
    plan = plan_window(MEMBERS, authoritative, first, last + 1)

    assert plan["skipped"] == ["VJ-B01", "VJ-B02", "VJ-B03", "VJ-B04"]
    assert plan["to_run"] == [B05, B06, "VJ-B07", "VJ-B08"]
    assert len(plan["complete"]) == 4
    # The historical 429 must not read as current exhaustion.
    assert live_provider_error(historical, window_start) is False


# -- Test D -----------------------------------------------------------------


def test_partial_current_triplet_stays_partial_and_next_job_does_not_start():
    """B05 run1 success then run2 failure leaves B05 at 1/3 and halts."""
    records = [_ok("VJ-B05", 1), _boom("VJ-B05", 2)]
    window_start = 0

    assert live_provider_error(records, window_start) is True

    # The guard trips before run 3 is attempted, so B05 holds exactly one
    # authoritative success and no fabricated run 3 exists.
    authoritative = authoritative_successes_from(records)
    assert authoritative["VJ-B05"] == {1}
    assert len(authoritative["VJ-B05"]) < RUNS_PER_JOB

    # No record for B06 was ever produced.
    assert "VJ-B06" not in authoritative


def test_partial_job_is_completed_by_missing_run_ids_only():
    """Resuming a 1/3 job schedules only the missing run ids."""
    authoritative = {B05: {1}}
    idx = BY_INDEX[B05]
    plan = plan_window(MEMBERS, authoritative, idx, idx + 1)

    assert plan["to_run"] == [B05]
    assert plan["missing_run_ids"][B05] == (2, 3)
    assert plan["partial"] == [B05]


# -- Test E -----------------------------------------------------------------


def test_fresh_invocation_resets_the_live_failure_boundary():
    """A second invocation re-anchors the boundary and may start a new job."""
    first_window = [_ok("VJ-B05", 1), _boom("VJ-B05", 2)]  # this window trips
    assert live_provider_error(first_window, 0) is True

    # Next invocation loads those records as history.
    loaded = list(first_window)
    second_start = len(loaded)
    assert live_provider_error(loaded, second_start) is False

    # It can begin a new job; only a new failure trips the guard again.
    records = loaded + [_ok("VJ-B06", 1)]
    assert live_provider_error(records, second_start) is False
    records.append(_boom("VJ-B06", 2))
    assert live_provider_error(records, second_start) is True


# -- helpers ----------------------------------------------------------------


def authoritative_successes_from(records: list[dict]) -> dict[str, set[int]]:
    """Same rule as authoritative_successes(), applied to in-memory records."""
    done: dict[str, set[int]] = {}
    for rec in records:
        if isinstance(rec, dict) and rec.get("success") and rec.get("job_id"):
            done.setdefault(rec["job_id"], set()).add(rec.get("run_id"))
    return done


def test_authoritative_successes_reads_only_successful_records(tmp_path):
    path = tmp_path / "runs.json"
    path.write_text(json.dumps({"runs": [
        _ok("VJ-B05", 1), _boom("VJ-B05", 2), _ok("VJ-B06", 1),
    ]}), encoding="utf-8")

    assert authoritative_successes(path) == {"VJ-B05": {1}, "VJ-B06": {1}}


def test_authoritative_successes_missing_file_is_empty(tmp_path):
    assert authoritative_successes(tmp_path / "absent.json") == {}


def test_non_provider_failure_does_not_trip_the_guard():
    """Only PROVIDER_ERROR is a live stop signal."""
    records = [{"failure_code": "EXTRACTION_FAILED"}, {"failure_code": None}]
    assert live_provider_error(records, 0) is False


@pytest.mark.parametrize("bad", [[None], ["x"], [{}]])
def test_malformed_records_do_not_raise(bad):
    assert live_provider_error(bad, 0) is False
