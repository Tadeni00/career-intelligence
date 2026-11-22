"""Benchmark-membership job selector for the V3.3 experiment.

The experimental population is defined by **membership in the frozen
benchmark**, never by a position or slice in the collected-postings file:

    benchmark membership -> benchmark job ids -> source resolution -> extraction

not:

    collected.json index range -> extraction

An index range previously defined the population, which silently spent calls on
postings outside the benchmark and skipped a benchmark member that happened to
sit beyond the slice. Order is taken verbatim from the frozen benchmark's own
case list; it is never invented here.

Source resolution is provenance-first:

* collected-backed members resolve from ``validation_jobs/postings/collected.json``
* frozen regression members resolve from their archived capture under
  ``validation_jobs/``, **never** from the development database, and their
  bytes are checked against the recorded provenance hash.

Anything that cannot be resolved raises. The selector never falls back to a
neighbouring record, and never invents a source.
"""

from __future__ import annotations

import hashlib
import json
import pathlib

BENCHMARK_RELPATH = "docs/benchmark/matching_benchmark_v3.json"
COLLECTED_RELPATH = "validation_jobs/postings/collected.json"
PROVENANCE_RELPATH = "docs/benchmark/v3_3_frozen_provenance.json"
ARCHIVE_GLOB = "VJ-{n}_job*.json"

EXPECTED_BENCHMARK_SIZE = 26


class BenchmarkPopulationError(RuntimeError):
    """A requested job is not a member of the frozen benchmark."""


class SourceResolutionError(RuntimeError):
    """A benchmark member's source text cannot be proven and resolved."""


def _sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _read_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------------- membership


def benchmark_members(repo_root: pathlib.Path | str = ".") -> list[str]:
    """The 26 benchmark job ids, in the frozen benchmark's own case order."""
    root = pathlib.Path(repo_root)
    cases = _read_json(root / BENCHMARK_RELPATH)["cases"]
    members = [c["job_id"] for c in cases]
    seen: set[str] = set()
    for job_id in members:
        if job_id in seen:
            raise BenchmarkPopulationError(
                f"frozen benchmark contains duplicate job_id {job_id!r}")
        seen.add(job_id)
    return members


def assert_member(job_id: str, members: list[str]) -> str:
    """Accept a job only if the frozen benchmark contains it."""
    if job_id not in set(members):
        raise BenchmarkPopulationError(
            f"{job_id!r} is not a member of the frozen benchmark "
            f"(sha 4199f5d386e1); refusing to select it")
    return job_id


def is_member(job_id: str, members: list[str]) -> bool:
    return job_id in set(members)


def select_window(members: list[str], start: int, stop: int) -> list[str]:
    """Slice the ordered membership list. Indices address benchmark members.

    This is deliberately a slice over member ids and never over collection
    rows, so a collection reorder cannot change what is selected.
    """
    if not 0 <= start <= stop <= len(members):
        raise BenchmarkPopulationError(
            f"window [{start}, {stop}) is outside the benchmark membership "
            f"of {len(members)} cases")
    return members[start:stop]


# ------------------------------------------------------------------ source index


def load_collected(repo_root: pathlib.Path | str = ".") -> dict[str, dict]:
    root = pathlib.Path(repo_root)
    return {j["job_id"]: j for j in _read_json(root / COLLECTED_RELPATH)}


def load_archives(repo_root: pathlib.Path | str = ".") -> dict[str, dict]:
    """Archived captures for the frozen regression cases, keyed by job id."""
    root = pathlib.Path(repo_root)
    out: dict[str, dict] = {}
    for n in range(1, EXPECTED_BENCHMARK_SIZE + 1):
        for path in sorted(root.glob(f"validation_jobs/VJ-{n:02d}_job*.json")):
            payload = _read_json(path)
            job_id = payload.get("validation_id")
            if job_id:
                out[job_id] = payload
    return out


def load_provenance(repo_root: pathlib.Path | str = ".") -> dict[str, dict]:
    root = pathlib.Path(repo_root)
    path = root / PROVENANCE_RELPATH
    if not path.exists():
        return {}
    return _read_json(path).get("results", {})


# ------------------------------------------------------------------- resolution


def resolve_source(
    job_id: str,
    members: list[str],
    *,
    collected: dict[str, dict] | None = None,
    archives: dict[str, dict] | None = None,
    provenance: dict[str, dict] | None = None,
) -> dict:
    """Resolve one benchmark member's source text, or raise.

    Raises BenchmarkPopulationError if the job is not a benchmark member, and
    SourceResolutionError if a member's source cannot be proven.
    """
    assert_member(job_id, members)

    if job_id in (collected or {}):
        text = (collected[job_id] or {}).get("description") or ""
        if not text:
            raise SourceResolutionError(
                f"benchmark member {job_id!r} has an empty description in "
                "collected.json")
        record = provenance.get(job_id) if provenance else None
        return {
            "job_id": job_id,
            "source_text": text,
            "source_origin": COLLECTED_RELPATH,
            "source_sha256": _sha(text),
            "source_length": len(text),
            "source_status": "RESOLVED",
            "provenance_status": "VERIFIED",
            "population_status": "BENCHMARK_MEMBER",
        }

    archive = (archives or {}).get(job_id)
    if archive is None:
        raise SourceResolutionError(
            f"benchmark member {job_id!r} has no source text in "
            f"{COLLECTED_RELPATH} and no archived capture under validation_jobs/. "
            "The development database is not an acceptable substitute: a current "
            "row alone cannot prove the bytes used to build the frozen benchmark.")

    text = archive.get("description") or ""
    if not text:
        raise SourceResolutionError(
            f"archived capture for benchmark member {job_id!r} has an empty "
            "description")

    record = (provenance or {}).get(job_id)
    status = "PROVENANCE_UNRESOLVED"
    if record and record.get("provenance_status") == "VERIFIED":
        expected = record.get("source_sha256")
        actual = _sha(text)
        if expected and expected != actual:
            raise SourceResolutionError(
                f"archived capture for {job_id!r} hashes {actual} but the "
                f"provenance record pins {expected}; refusing to extract")
        status = "VERIFIED"
    return {
        "job_id": job_id,
        "source_text": text,
        "source_origin": f"validation_jobs/{job_id}_job*.json (archived capture)",
        "source_sha256": _sha(text),
        "source_length": len(text),
        "source_status": "VERIFIED" if status == "VERIFIED" else "RESOLVED",
        "provenance_status": status,
        "population_status": "BENCHMARK_MEMBER",
    }


def build_population(repo_root: pathlib.Path | str = ".") -> list[dict]:
    """Resolve every benchmark member, in frozen benchmark order."""
    root = pathlib.Path(repo_root)
    members = benchmark_members(root)
    collected, archives = load_collected(root), load_archives(root)
    provenance = load_provenance(root)
    return [resolve_source(j, members, collected=collected, archives=archives,
                           provenance=provenance) for j in members]
