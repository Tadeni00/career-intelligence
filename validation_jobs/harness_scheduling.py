"""Pure scheduling predicates for the V3.3 execution harness.

Kept separate from ``v33_runs.py`` so the guard semantics are testable without
executing a window or contacting a provider.

Two rules live here.

**Completion state.** The scheduler acts on benchmark membership *and* the
authoritative completion state, never on a bare index range. A job already
holding three authoritative successes is complete and is skipped, so a valid
triplet can never be overwritten by a re-run.

**Live quota stop signal.** A provider failure is a live stop signal only when
it occurs during the *current* invocation. Historical failures loaded from disk
describe a previous window and must never be read as current exhaustion --
otherwise one recorded 429 permanently blocks every future window.

The atomic-triplet rule is unchanged: when the guard trips, the affected job is
left incomplete, no missing run is fabricated, no alternative provider or model
is tried, the next job does not start, and a later window may resume it.
"""

from __future__ import annotations

import json
import pathlib

RUNS_PER_JOB = 3
RUN_IDS = (1, 2, 3)


class LedgerConflictError(RuntimeError):
    """A (job_id, run_id) slot holds more than one successful record.

    Two different successful results for the same experimental unit cannot both
    be authoritative. The scheduler refuses to choose between them: it never
    silently keeps the newest, the oldest, or any arbitrary winner.
    """


class LedgerState(dict):
    """job_id -> set(successful run ids), carrying conflict findings.

    A plain ``dict`` subclass, so existing callers keep their dict-style
    indexing, ``len()`` and iteration unchanged. ``conflicts`` is a list of
    ``(job_id, run_id, successful_record_count)``.
    """

    def __init__(self, mapping=None, conflicts=None, record_count=0):
        super().__init__(mapping or {})
        self.conflicts = list(conflicts or [])
        self.record_count = record_count


def detect_conflicts(records: list[dict]) -> list[tuple[str, int, int]]:
    """Return every (job_id, run_id) slot holding more than one success.

    A historical *failed* attempt alongside a success is legitimate
    attempt-history and is not a conflict; only multiple *successful* records
    are.
    """
    counts: dict[tuple[str, int], int] = {}
    for rec in records or []:
        if isinstance(rec, dict) and rec.get("success") and rec.get("job_id"):
            key = (rec["job_id"], rec.get("run_id"))
            counts[key] = counts.get(key, 0) + 1
    return [(job, run, n) for (job, run), n in sorted(counts.items()) if n > 1]


def assert_no_conflicts(records: list[dict]) -> None:
    """Raise LedgerConflictError naming every conflicted slot."""
    conflicts = detect_conflicts(records)
    if conflicts:
        detail = ", ".join(f"{job}/run{run} x{n}" for job, run, n in conflicts)
        raise LedgerConflictError(
            f"ledger conflict: {len(conflicts)} slot(s) hold more than one "
            f"successful record: {detail}. Refusing to schedule: no arbitrary "
            "winner may be chosen.")


def authoritative_successes(path: pathlib.Path | str) -> LedgerState:
    """Map job_id -> set of authoritative successful run ids recorded on disk.

    Conflicts are reported, not raised, so a caller can inspect them; the
    refusal to schedule happens in :func:`plan_window`.
    """
    path = pathlib.Path(path)
    if not path.exists():
        return LedgerState()
    try:
        existing = json.loads(path.read_text(encoding="utf-8")).get("runs", [])
    except Exception:
        return LedgerState()
    done: dict[str, set[int]] = {}
    for rec in existing:
        if isinstance(rec, dict) and rec.get("success") and rec.get("job_id"):
            done.setdefault(rec["job_id"], set()).add(rec.get("run_id"))
    return LedgerState(done, detect_conflicts(existing), len(existing))


def live_provider_error(records: list[dict], window_start: int) -> bool:
    """True only if a PROVIDER_ERROR occurred during the current invocation.

    ``window_start`` is the index of the first record this invocation may
    append, captured after historical records are loaded from disk. Records
    before it belong to earlier windows and are deliberately ignored.
    """
    return any(
        isinstance(r, dict) and r.get("failure_code") == "PROVIDER_ERROR"
        for r in records[window_start:]
    )


def plan_window(members: list[str], authoritative: dict[str, set[int]],
                start: int, stop: int) -> dict:
    """Decide what a window executes, given membership and completion state.

    Propagates :class:`LedgerConflictError` rather than returning a plan when
    the ledger holds conflicting successful records. A conflicted slot is never
    reported as complete and is never rescheduled silently.
    """
    conflicts = getattr(authoritative, "conflicts", None)
    if conflicts:
        detail = ", ".join(f"{job}/run{run} x{n}" for job, run, n in conflicts)
        raise LedgerConflictError(
            f"ledger conflict: {len(conflicts)} slot(s) hold more than one "
            f"successful record: {detail}. Refusing to schedule: no arbitrary "
            "winner may be chosen.")
    window = members[start:stop]
    to_run, skipped = [], []
    for job_id in window:
        have = authoritative.get(job_id, set())
        (skipped if len(have) >= RUNS_PER_JOB else to_run).append(job_id)
    return {
        "window": window,
        "to_run": to_run,
        "skipped": skipped,
        "partial": sorted(j for j, r in authoritative.items()
                          if 0 < len(r) < RUNS_PER_JOB),
        "complete": sorted(j for j, r in authoritative.items()
                           if len(r) >= RUNS_PER_JOB),
        "missing_run_ids": {
            job_id: tuple(r for r in RUN_IDS
                          if r not in authoritative.get(job_id, set()))
            for job_id in to_run
        },
    }
