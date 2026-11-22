"""Selector tests: benchmark membership defines the V3.3 population.

Governance requires that the experimental population be explicit benchmark
membership, resolved through provenance, and never a slice of the collected
postings file. These tests pin that contract.

No provider calls and no database access: the selector is pure artifact
resolution over files in the repository.
"""

from __future__ import annotations

import copy
import json
import pathlib

import pytest
from benchmark_selector import (
    COLLECTED_RELPATH,
    EXPECTED_BENCHMARK_SIZE,
    BenchmarkPopulationError,
    SourceResolutionError,
    assert_member,
    benchmark_members,
    build_population,
    is_member,
    load_archives,
    load_collected,
    load_provenance,
    resolve_source,
    select_window,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
EXCLUDED_CLICKUP = ["VJ-B22", "VJ-B24", "VJ-B25", "VJ-B26", "VJ-B27"]
FROZEN_REGRESSION = ["VJ-01", "VJ-02", "VJ-03"]


@pytest.fixture(scope="module")
def members() -> list[str]:
    return benchmark_members(ROOT)


# -- Test 1 -----------------------------------------------------------------


def test_all_26_frozen_benchmark_ids_are_selected(members):
    """Every case in the frozen benchmark is a member of the population."""
    bench = json.loads((ROOT / "docs/benchmark/matching_benchmark_v3.json")
                       .read_text(encoding="utf-8"))
    bench_ids = [c["job_id"] for c in bench["cases"]]

    assert len(members) == EXPECTED_BENCHMARK_SIZE
    assert set(members) == set(bench_ids)
    assert members == bench_ids, "ordering must come from the frozen benchmark"


# -- Test 2 -----------------------------------------------------------------


def test_five_excluded_clickup_jobs_are_rejected(members):
    """Postings excluded by the per-company cap are not members."""
    for job_id in EXCLUDED_CLICKUP:
        assert not is_member(job_id, members)
        with pytest.raises(BenchmarkPopulationError):
            assert_member(job_id, members)


# -- Test 3 -----------------------------------------------------------------


def test_vjb28_is_selected_because_it_is_a_benchmark_member(members):
    """A member past the old index slice must still be reachable."""
    assert "VJ-B28" in members
    assert is_member("VJ-B28", members)
    collected = load_collected(ROOT)
    resolved = resolve_source("VJ-B28", members, collected=collected)
    assert resolved["source_text"]
    assert resolved["population_status"] == "BENCHMARK_MEMBER"


# -- Test 4 -----------------------------------------------------------------


def test_collection_position_cannot_introduce_a_non_benchmark_job(members):
    """Excluded postings are rejected whatever their collection position."""
    collected = load_collected(ROOT)
    assert set(EXCLUDED_CLICKUP) <= set(collected), (
        "excluded postings must still exist in the collection, otherwise this "
        "test would pass vacuously")

    for job_id in EXCLUDED_CLICKUP:
        # Each excluded posting sits at a real collection position; addressing it
        # by that position must still not make it selectable.
        assert job_id in list(collected)
        with pytest.raises(BenchmarkPopulationError):
            resolve_source(job_id, members, collected=collected)


# -- Test 5 -----------------------------------------------------------------


def test_collection_reorder_does_not_change_benchmark_membership():
    """Membership is a property of the benchmark, not of collection order."""
    real_collected = load_collected(ROOT)
    shuffled = dict(reversed(list(real_collected.items())))
    assert list(shuffled) != list(real_collected)

    members = benchmark_members(ROOT)
    before = [r["job_id"] for r in build_population(ROOT)]
    after = [
        r["job_id"] for r in
        (resolve_source(j, members, collected=shuffled,
                        archives=load_archives(ROOT),
                        provenance=load_provenance(ROOT)) for j in members)
    ]
    assert before == after == members


# -- Test 6 -----------------------------------------------------------------


def test_selector_returns_exactly_26_members(members):
    """The full population is exactly the 26 frozen benchmark cases."""
    assert len(members) == 26
    assert len(set(members)) == 26
    resolved = build_population(ROOT)
    assert len(resolved) == 26
    assert [r["job_id"] for r in resolved] == members
    assert all(r["source_text"] for r in resolved)


# -- Test 7 -----------------------------------------------------------------


def test_no_duplicate_benchmark_ids(members):
    """Membership must be a set, not a multiset."""
    assert len(set(members)) == len(members)

    bench = json.loads((ROOT / "docs/benchmark/matching_benchmark_v3.json")
                       .read_text(encoding="utf-8"))
    ids = [c["job_id"] for c in bench["cases"]]
    assert len(set(ids)) == len(ids)


# -- Test 8 -----------------------------------------------------------------


def test_missing_source_raises_instead_of_taking_a_neighbour(members):
    """A member with no resolvable source fails loudly and never borrows one."""
    collected = load_collected(ROOT)

    # Drop a member's own record entirely: no text, no archive -> must raise.
    without = {k: v for k, v in collected.items() if k != "VJ-B23"}
    assert "VJ-B23" in members
    assert "VJ-B23" not in without
    with pytest.raises(SourceResolutionError):
        resolve_source("VJ-B23", members, collected=without)

    # Empty the text but keep the record: still an explicit error, not a
    # silent fall-through to the neighbouring collection entry.
    blanked = copy.deepcopy(collected)
    blanked["VJ-B23"]["description"] = ""
    with pytest.raises(SourceResolutionError):
        resolve_source("VJ-B23", members, collected=blanked)

    # A frozen regression member with no archive must raise rather than be
    # sourced from the development database.
    for job_id in FROZEN_REGRESSION:
        with pytest.raises(SourceResolutionError):
            resolve_source(job_id, members, collected=collected, archives={},
                           provenance=load_provenance(ROOT))


# -- supporting invariants ---------------------------------------------------


def test_frozen_regression_cases_resolve_from_archives_with_verified_provenance():
    """Frozen cases are sourced from their archived capture, hash-checked."""
    members = benchmark_members(ROOT)
    archives, provenance = load_archives(ROOT), load_provenance(ROOT)
    for job_id in FROZEN_REGRESSION:
        assert job_id in members
        record = provenance.get(job_id)
        assert record is not None, "provenance record must exist"
        assert record["provenance_status"] == "VERIFIED"
        resolved = resolve_source(job_id, members, collected=load_collected(ROOT),
                                  archives=archives, provenance=provenance)
        assert resolved["provenance_status"] == "VERIFIED"
        assert resolved["source_sha256"] == record["source_sha256"]
        assert resolved["source_length"] == record["source_length"]
        assert COLLECTED_RELPATH not in resolved["source_origin"]


def test_tampered_archive_is_rejected(members):
    """If archive bytes stop matching the pinned hash, resolution fails."""
    archives = copy.deepcopy(load_archives(ROOT))
    provenance = load_provenance(ROOT)
    archives["VJ-01"]["description"] += " TAMPERED"
    with pytest.raises(SourceResolutionError):
        resolve_source("VJ-01", members, collected=load_collected(ROOT),
                       archives=archives, provenance=provenance)


def test_window_indices_address_benchmark_members(members):
    """--from/--to address the ordered membership list."""
    assert select_window(members, 0, 26) == members
    assert select_window(members, 0, 1) == [members[0]]
    with pytest.raises(BenchmarkPopulationError):
        select_window(members, 0, 27)
    with pytest.raises(BenchmarkPopulationError):
        select_window(members, 5, 2)


def test_population_composition(members):
    """26 = 23 collected-backed + 3 frozen regression."""
    collected = set(load_collected(ROOT))
    in_collection = [m for m in members if m in collected]
    assert len(in_collection) == 23
    assert [m for m in members if m not in collected] == FROZEN_REGRESSION
    assert len(in_collection) + len(FROZEN_REGRESSION) == 26
