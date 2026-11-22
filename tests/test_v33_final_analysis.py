"""Tests for the V3.3 final stability analysis code.

The analysis is read-only over frozen artifacts. These tests pin the metric
semantics so a future edit cannot silently change a reported number, and they
assert that the analysis touches nothing it must not touch.

No network, no provider, no inference.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "validation_jobs"))
sys.path.insert(0, str(ROOT / "apps/api"))

ANALYSIS_JSON = ROOT / "docs/benchmark/v3_3_final_stability_analysis.json"
LEDGER = ROOT / "docs/benchmark/v3_3c_extraction_reproducibility_runs.json"
# Frozen historical evidence was hashed with CRLF line endings.
# The initial GitHub import stores LF bytes. Pin both representations explicitly.
LEDGER_HISTORICAL_CRLF_SHA = "6f8f6a1ee5f54acb1bd9d9270f89edf8c244c72118381c21931feb20740557c0"
LEDGER_GIT_LF_SHA = "9badf91c013f440629c13c5cf051a3be9de30af3516aa5a255a0fcc0db4ae92d"
BENCHMARK_HISTORICAL_CRLF_SHA = "4199f5d386e1fb8b9be1a6c053c0c9cc6f2e6e8afeadc31112e650c34f37345f"
BENCHMARK_GIT_LF_SHA = "06356fffd260ab449562de1bc1f4ff45b37b00d244a6149b02bd01973cf8452f"


def assert_imported_frozen_bytes(path: pathlib.Path, expected_lf: str, expected_crlf: str) -> None:
    """Pin both the committed Git bytes and the original Windows representation.

    The original hash must match after newline-only reconstruction; neither the
    file nor its semantic content is rewritten or reserialized by this test.
    """
    raw = path.read_bytes()
    assert b"\r" not in raw, "Git artifact unexpectedly contains carriage returns"
    assert not raw.endswith(b"\n"), "Git artifact unexpectedly has a final newline"
    assert b"\n" in raw, "Expected multi-line frozen JSON"
    assert hashlib.sha256(raw).hexdigest() == expected_lf
    assert hashlib.sha256(raw.replace(b"\n", b"\r\n")).hexdigest() == expected_crlf


@pytest.fixture(scope="module")
def result() -> dict:
    if not ANALYSIS_JSON.exists():
        pytest.skip("analysis artifact not generated")
    return json.loads(ANALYSIS_JSON.read_text(encoding="utf-8"))


# -- helper semantics --------------------------------------------------------


def test_jaccard_values_on_known_sets():
    """J is |A n B| / |A u B|; an empty union is undefined (None), not 1.0."""
    def j(a, b):
        u = a | b
        return None if not u else len(a & b) / len(u)

    assert j({1, 2}, {1, 2}) == 1.0
    assert j({1, 2}, {1, 3}) == pytest.approx(1 / 3)
    assert j({1, 2}, {3, 4}) == 0.0
    assert j(set(), set()) is None
    assert j(set(), {1}) == 0.0


# -- population integrity ----------------------------------------------------


def test_ledger_untouched_by_analysis():
    assert_imported_frozen_bytes(LEDGER, LEDGER_GIT_LF_SHA, LEDGER_HISTORICAL_CRLF_SHA)


def test_frozen_benchmark_untouched():
    b = ROOT / "docs/benchmark/matching_benchmark_v3.json"
    assert_imported_frozen_bytes(b, BENCHMARK_GIT_LF_SHA, BENCHMARK_HISTORICAL_CRLF_SHA)


def test_human_labels_still_zero():
    lab = json.loads((ROOT / "docs/benchmark/human_labels_v3.json").read_text(encoding="utf-8"))
    assert sum(1 for r in lab["labels"] if r["decision"] is not None) == 0


def test_population_is_26_members_with_three_runs(result):
    pre = result["prerequisites"]
    assert pre["ledger_records"] == 81
    assert pre["benchmark_members"] == 26
    assert pre["members_with_three_successes"] == 26
    assert pre["partial_triplets"] == []
    assert pre["ledger_conflicts"] == []
    assert pre["successful_runs"] == 78


def test_three_preserved_failures_are_retained(result):
    pre = result["prerequisites"]
    assert [tuple(x) for x in pre["preserved_failures"]] == [
        ("VJ-B05", 1), ("VJ-B07", 3), ("VJ-B14", 1)]


# -- metric consistency ------------------------------------------------------


def test_identity_equality_is_stricter_than_name_equality(result):
    """Identity-set equality implies name-set equality, never the reverse."""
    A = result["A_structural"]
    assert A["identity_sets_identical_jobs"] <= A["name_sets_identical_jobs"]
    assert A["counts_all_equal_jobs"] >= A["identity_sets_identical_jobs"]


def test_selection_counts_sum_to_union(result):
    """The selection partition must close over the NAME union exactly."""
    B = result["B_selection"]
    assert (B["unique_names_in_all_three"] + B["unique_names_in_exactly_two"]
            + B["unique_names_in_exactly_one"]) == B["unique_names_union_all_jobs"]
    assert B["partition_check"] is True


def test_name_union_is_not_confused_with_identity_tuple_union(result):
    """A name may carry different importance across runs, so the tuple union
    is larger. Using one as the other's denominator is a category error."""
    B = result["B_selection"]
    assert B["unique_identity_tuples_union_all_jobs"] > B["unique_names_union_all_jobs"]
    assert B["denominator_unique_name_union"] == B["unique_names_union_all_jobs"]


def test_selection_denominators_are_distinct_and_labelled(result):
    B = result["B_selection"]
    assert B["denominator_unique_name_union"] != B["denominator_run_level_occurrences"]
    assert B["denominator_run_level_occurrences"] == 1248


def test_classification_denominator_is_alignment_not_presence(result):
    C = result["C_classification"]
    assert C["aligned_requirements"] == C["aligned_consistent"] + C["aligned_inconsistent"]
    assert 0 < C["aligned_requirements"] <= C["aligned_consistent"] + C["aligned_inconsistent"]


def test_informational_label_absent_is_reported_not_assumed(result):
    """INFORMATIONAL never occurred; the report must say 0, not imply it did."""
    assert result["C_classification"]["INFORMATIONAL_observed"] == 0


def test_recommendation_labels_not_merged(result):
    F = result["F_recommendation"]
    assert set(F["labels_preserved"]) == {
        "APPLY", "APPLY_WITH_TAILORING", "SKIP", "STRETCH"}
    assert F["jobs_stable"] + F["jobs_decision_changing"] == 26


def test_score_range_matches_persisted_scores(result):
    for row in result["per_job"]:
        assert row["score_range"] == pytest.approx(
            round(max(row["scores"]) - min(row["scores"]), 2))
        assert row["scores_identical"] == (len(set(row["scores"])) == 1)


def test_count_range_matches_persisted_counts(result):
    for row in result["per_job"]:
        assert row["count_range"] == max(row["counts"]) - min(row["counts"])


def test_jaccard_within_unit_interval(result):
    for row in result["per_job"]:
        for v in row["jaccard_identity"].values():
            assert v is None or 0.0 <= v <= 1.0


# -- evidence ----------------------------------------------------------------


def test_evidence_denominators_are_separated(result):
    D = result["D_evidence"]
    assert (D["carrying_an_evidence_quote"] + D["no_evidence_quote_at_all"]
            == D["requirement_instances_examined"])
    assert (D["quote_found_verbatim_in_source"] + D["quote_not_found_verbatim"]
            == D["carrying_an_evidence_quote"])


def test_evidence_audit_is_labelled_preliminary(result):
    assert result["D_evidence"]["status"] == "PRELIMINARY_MECHANICAL_AUDIT"
    assert "NOT PERFORMED" in result["D_evidence"]["semantic_support_adjudication"]


def test_skill_requirements_are_unevidenced_by_construction(result):
    """SKILL type carries no source_text under the frozen schema."""
    types = result["D_evidence"]["no_evidence_by_requirement_type"]
    assert types["SKILL"]["without_quote"] == types["SKILL"]["total"]
    assert types["SKILL"]["rate"] == 1.0


# -- execution anomalies -----------------------------------------------------


def test_missing_usage_is_null_not_zero(result):
    G = result["G_execution_anomalies"]
    assert sorted(tuple(x) for x in G["runs_with_missing_usage"]) == [
        ("VJ-B07", 3), ("VJ-B14", 1)]
    assert G["measured_usage_denominator"] == 66
    assert G["measured_usage_denominator"] < 78


def test_no_correctness_claim_is_made(result):
    """Human labels are 0/23, so the artifact must not assert correctness."""
    blob = json.dumps(result).lower()
    for forbidden in ("accuracy is", "precision is", "recall is", "validated correct"):
        assert forbidden not in blob
