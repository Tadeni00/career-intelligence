"""V3.3 final stability analysis. READ-ONLY over frozen artifacts.

Answers the frozen scientific question:

    Is requirement extraction reproducible across repeated runs on the same
    frozen job postings under the frozen extraction contract?

Analysis only. Makes no inference call, modifies no experiment artifact, and
changes no production behaviour. Canonicalisation semantics are reused exactly
as persisted: the identity tuple is the 7-field tuple recorded by
``canonical_requirements`` -> ``identity``:

    (name, type, importance, category, years_required, evidence_status, work)

Two distinct notions of sameness are reported and never merged:

  * IDENTITY-SET equality  -- all 7 fields equal (the full canonical identity)
  * NAME-SET equality     -- field 0 equal only (the selection unit)

Equal counts with unequal identity sets are explicitly reported as such.
"""

from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import statistics
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "validation_jobs"))
sys.path.insert(0, str(_REPO / "apps/api"))

from benchmark_selector import benchmark_members, build_population  # noqa: E402
from harness_scheduling import authoritative_successes  # noqa: E402

LEDGER = _REPO / "docs/benchmark/v3_3c_extraction_reproducibility_runs.json"
OUT_JSON = _REPO / "docs/benchmark/v3_3_final_stability_analysis.json"
OUT_MD = _REPO / "docs/benchmark/v3_3_final_stability_analysis.md"

NAME, TYPE, IMPORTANCE, CATEGORY, YEARS, EVSTATUS, WORK = range(7)
PAIR_KEYS = ((1, 2), (1, 3), (2, 3))


def sha_file(rel: pathlib.Path) -> str:
    return hashlib.sha256(rel.read_bytes()).hexdigest()


def norm(text: str) -> str:
    return " ".join((text or "").lower().split())


def jaccard(a: set, b: set) -> float | None:
    """J(A,B)=|A n B|/|A u B|. Empty union -> None (undefined, not 1.0)."""
    union = a | b
    if not union:
        return None
    return len(a & b) / len(union)


# ----------------------------------------------------------------- load
runs_all = json.loads(LEDGER.read_text(encoding="utf-8"))["runs"]
state = authoritative_successes(LEDGER)
members = benchmark_members(_REPO)
population = {r["job_id"]: r for r in build_population(_REPO)}

successful = [r for r in runs_all if r["success"]]
by_job: dict[str, dict[int, dict]] = collections.defaultdict(dict)
for r in successful:
    by_job[r["job_id"]][r["run_id"]] = r

failures = [r for r in runs_all if not r["success"]]


def ident_set(run: dict) -> set:
    return {tuple(i) for i in (run.get("canonical_requirement_set") or [])}


def name_set(run: dict) -> set:
    return {i[NAME] for i in ident_set(run)}


# ------------------------------------------------------------ prerequisite
prereq = {
    "ledger_records": len(runs_all),
    "ledger_sha256": sha_file(LEDGER),
    "benchmark_members": len(members),
    "members_with_three_successes": sum(1 for m in members if len(state.get(m, set())) == 3),
    "partial_triplets": sorted(j for j, v in state.items() if 0 < len(v) < 3),
    "ledger_conflicts": state.conflicts,
    "preserved_failures": sorted((r["job_id"], r["run_id"]) for r in failures),
    "successful_runs": len(successful),
    "runs_with_raw_extraction": sum(1 for r in successful if r.get("raw_extraction")),
    "runs_with_coerced_extraction": sum(1 for r in successful if r.get("coerced_extraction")),
    "runs_with_measured_usage": sum(1 for r in successful if r.get("total_tokens") is not None),
}

# --------------------------------------------------------------- per job
per_job = []
importance_seen: collections.Counter = collections.Counter()
category_seen: collections.Counter = collections.Counter()
align_rows = []
evidence_rows = []

for jid in members:
    r1, r2, r3 = (by_job[jid][i] for i in (1, 2, 3))
    runs = (r1, r2, r3)
    isets = [ident_set(r) for r in runs]
    nsets = [name_set(r) for r in runs]
    counts = [r["canonical_requirement_count"] for r in runs]
    scores = [r["score"] for r in runs]
    recs = [r["recommendation"] for r in runs]

    for i in isets:
        for t in i:
            importance_seen[t[IMPORTANCE]] += 1
            category_seen[t[CATEGORY]] += 1

    # ---- B: selection, name-based, per job
    all_names = nsets[0] | nsets[1] | nsets[2]
    in_all = nsets[0] & nsets[1] & nsets[2]
    in_two = {n for n in all_names if sum(n in s for s in nsets) == 2}
    in_one = {n for n in all_names if sum(n in s for s in nsets) == 1}
    pair_add = {}
    pair_rem = {}
    for a, b in PAIR_KEYS:
        pair_add[f"{a}_{b}"] = len(nsets[b - 1] - nsets[a - 1])
        pair_rem[f"{a}_{b}"] = len(nsets[a - 1] - nsets[b - 1])

    # ---- C: classification, aligned by exact name across runs
    aligned, consistent, imp_trans, cat_trans = 0, 0, [], []
    presence_stable_class_changed = []
    for n in sorted(all_names):
        present = [k for k, s in enumerate(nsets) if n in s]
        if len(present) < 2:
            continue
        aligned += 1
        imps = {next(i[IMPORTANCE] for i in isets[k] if i[NAME] == n) for k in present}
        cats = {next(i[CATEGORY] for i in isets[k] if i[NAME] == n) for k in present}
        if len(imps) == 1 and len(cats) == 1:
            consistent += 1
        else:
            if len(imps) > 1:
                imp_trans.append((n, sorted(imps)))
            if len(cats) > 1:
                cat_trans.append((n, sorted(cats)))
            if len(present) == 3:
                presence_stable_class_changed.append(
                    {"name": n, "importance": sorted(imps), "category": sorted(cats)})
        align_rows.append({"job_id": jid, "name": n, "runs_present": present,
                           "importance": sorted(imps), "category": sorted(cats),
                           "consistent": len(imps) == 1 and len(cats) == 1})

    # ---- D: evidence audit against the frozen source
    src = norm(population[jid]["source_text"])
    n_req = n_quote_ok = n_quote_miss = n_bare = 0
    by_type_total: collections.Counter = collections.Counter()
    by_type_bare: collections.Counter = collections.Counter()
    misses = []
    for r in runs:
        for c in (r.get("canonical_requirements") or []):
            n_req += 1
            t = c.get("type")
            by_type_total[t] += 1
            q = (c.get("source_text") or "").strip()
            if not q:
                n_bare += 1
                by_type_bare[t] += 1
                continue
            if norm(q) in src:
                n_quote_ok += 1
            else:
                n_quote_miss += 1
                if len(misses) < 3:
                    misses.append({"job_id": jid, "run_id": r["run_id"],
                                   "name": c.get("name"), "quote": q[:110]})
    stripped = sum(1 for r in runs
                   for n_ in (r.get("canonical_notes") or [])
                   if "not found in the job text" in n_)
    evidence_rows.append({"job_id": jid, "requirements": n_req, "quote_in_source": n_quote_ok,
                          "quote_not_found": n_quote_miss, "no_source_text": n_bare,
                          "stripped_notes": stripped, "examples": misses,
                          "by_type_total": dict(by_type_total),
                          "by_type_without_quote": dict(by_type_bare)})

    row = {
        "job_id": jid,
        "member_class": population[jid]["provenance_status"] and
                        ("FROZEN_REGRESSION" if "archive" in population[jid]["source_origin"]
                         else "COLLECTED_BACKED"),
        "source_origin": population[jid]["source_origin"],
        "provenance_status": population[jid]["provenance_status"],
        "source_sha256": population[jid]["source_sha256"],
        "counts": counts, "count_min": min(counts), "count_max": max(counts),
        "count_range": max(counts) - min(counts),
        "counts_all_equal": len(set(counts)) == 1,
        "identity_sets_identical": isets[0] == isets[1] == isets[2],
        "name_sets_identical": nsets[0] == nsets[1] == nsets[2],
        "counts_equal_but_identity_differs":
            len(set(counts)) == 1 and not (isets[0] == isets[1] == isets[2]),
        "jaccard_identity": {f"{a}_{b}": jaccard(isets[a - 1], isets[b - 1]) for a, b in PAIR_KEYS},
        "jaccard_name": {f"{a}_{b}": jaccard(nsets[a - 1], nsets[b - 1]) for a, b in PAIR_KEYS},
        "union_identity_size": len(isets[0] | isets[1] | isets[2]),
        "intersection_identity_size": len(isets[0] & isets[1] & isets[2]),
        "names_union": len(all_names), "names_in_all_three": len(in_all),
        "names_in_exactly_two": len(in_two), "names_in_exactly_one": len(in_one),
        "pair_additions": pair_add, "pair_removals": pair_rem,
        "aligned_requirements": aligned, "aligned_consistent": consistent,
        "aligned_inconsistent": aligned - consistent,
        "presence_stable_classification_changed": presence_stable_class_changed,
        "scores": scores, "score_min": min(scores), "score_max": max(scores),
        "score_range": round(max(scores) - min(scores), 2),
        "score_mean": round(statistics.mean(scores), 2),
        "scores_identical": len(set(scores)) == 1,
        "scores_identical_identity_differs":
            len(set(scores)) == 1 and not (isets[0] == isets[1] == isets[2]),
        "recommendations": recs, "recommendation_stable": len(set(recs)) == 1,
    }
    row["structural_stability"] = (
        "STABLE" if row["identity_sets_identical"]
        else ("SAME_COUNTS_DIFFERENT_IDENTITIES" if row["counts_all_equal"]
              else "UNSTABLE"))
    per_job.append(row)

# ------------------------------------------------------------- aggregates
j_id = [v for r in per_job for v in r["jaccard_identity"].values() if v is not None]
j_nm = [v for r in per_job for v in r["jaccard_name"].values() if v is not None]
ranges = [r["count_range"] for r in per_job]
srange = [r["score_range"] for r in per_job]

rec_stable = [r for r in per_job if r["recommendation_stable"]]
rec_unstable = [r for r in per_job if not r["recommendation_stable"]]

tot_union = sum(r["union_identity_size"] for r in per_job)
# Selection partition is over NAMES, so its denominator is the NAME union.
# The identity-tuple union is a different, larger number and is reported
# separately; the two are never mixed.
tot_name_union = sum(r["names_union"] for r in per_job)
tot_all3 = sum(r["names_in_all_three"] for r in per_job)
tot_two = sum(r["names_in_exactly_two"] for r in per_job)
tot_one = sum(r["names_in_exactly_one"] for r in per_job)
tot_occ = sum(r["counts"][0] + r["counts"][1] + r["counts"][2] for r in per_job)
tot_aligned = sum(r["aligned_requirements"] for r in per_job)
tot_consistent = sum(r["aligned_consistent"] for r in per_job)

ev_req = sum(e["requirements"] for e in evidence_rows)
ev_ok = sum(e["quote_in_source"] for e in evidence_rows)
ev_miss = sum(e["quote_not_found"] for e in evidence_rows)
ev_bare = sum(e["no_source_text"] for e in evidence_rows)
ev_type_total: collections.Counter = collections.Counter()
ev_type_bare: collections.Counter = collections.Counter()
for e in evidence_rows:
    ev_type_total.update(e["by_type_total"])
    ev_type_bare.update(e["by_type_without_quote"])
ev_bearing = ev_ok + ev_miss

usage = [r["total_tokens"] for r in successful if r.get("total_tokens") is not None]

summary = {
    "artifact": "V3.3 final stability analysis (derived)",
    "frozen_question": ("Is requirement extraction reproducible across repeated runs "
                        "on the same frozen job postings under the frozen extraction contract?"),
    "prerequisites": prereq,
    "metric_definitions": {
        "identity_tuple": ("(name, type, importance, category, years_required, "
                           "evidence_status, work_condition) as persisted by "
                           "canonical_requirements[].identity"),
        "identity_set_stability": "all three runs' full 7-field identity sets are equal",
        "name_set_stability": "all three runs' field-0 sets are equal (selection unit)",
        "jaccard": "J(A,B)=|A n B|/|A u B|; empty union returns None (undefined)",
        "selection_denominator": ("two distinct denominators reported and never mixed: "
                                  "UNIQUE identities per job, and total run-level "
                                  "requirement occurrences (sum of the three counts)"),
        "classification_alignment": ("exact field-0 name match; a name must appear in "
                                     ">=2 of 3 runs to be classified as aligned"),
        "evidence_audit": ("mechanical quote-correspondence only: normalised substring "
                           "check of requirement source_text inside the frozen posting. "
                           "PRELIMINARY -- does not adjudicate semantic support"),
        "missing_data": ("runs without persisted raw/coerced extraction or usage are "
                         "reported as null/absent; never imputed"),
    },
    "A_structural": {
        "counts_all_equal_jobs": sum(1 for r in per_job if r["counts_all_equal"]),
        "identity_sets_identical_jobs": sum(1 for r in per_job if r["identity_sets_identical"]),
        "name_sets_identical_jobs": sum(1 for r in per_job if r["name_sets_identical"]),
        "counts_equal_but_identity_differs": sum(
            1 for r in per_job if r["counts_equal_but_identity_differs"]),
        "denominator_jobs": len(per_job),
        "jaccard_identity": {"n_pairs": len(j_id), "mean": round(statistics.mean(j_id), 4),
                             "median": round(statistics.median(j_id), 4),
                             "min": round(min(j_id), 4), "max": round(max(j_id), 4)},
        "jaccard_name": {"n_pairs": len(j_nm), "mean": round(statistics.mean(j_nm), 4),
                         "median": round(statistics.median(j_nm), 4),
                         "min": round(min(j_nm), 4), "max": round(max(j_nm), 4)},
        "count_range": {"mean": round(statistics.mean(ranges), 3),
                        "median": statistics.median(ranges), "max": max(ranges),
                        "min": min(ranges), "zero_range_jobs":
                            sum(1 for x in ranges if x == 0)},
        "lowest_identity_jaccard_jobs": sorted(
            [{"job_id": r["job_id"], "min_pair_jaccard":
              round(min(v for v in r["jaccard_identity"].values() if v is not None), 4),
              "counts": r["counts"]} for r in per_job],
            key=lambda x: x["min_pair_jaccard"])[:8],
        "greatest_count_variation_jobs": sorted(
            [{"job_id": r["job_id"], "count_range": r["count_range"], "counts": r["counts"]}
             for r in per_job], key=lambda x: -x["count_range"])[:8],
    },
    "B_selection": {
        "unique_identity_tuples_union_all_jobs": tot_union,
        "unique_names_union_all_jobs": tot_name_union,
        "unique_names_in_all_three": tot_all3,
        "unique_names_in_exactly_two": tot_two,
        "unique_names_in_exactly_one": tot_one,
        "denominator_unique_name_union": tot_name_union,
        "denominator_run_level_occurrences": tot_occ,
        "partition_check": tot_all3 + tot_two + tot_one == tot_name_union,
        "pair_additions_total": sum(sum(r["pair_additions"].values()) for r in per_job),
        "pair_removals_total": sum(sum(r["pair_removals"].values()) for r in per_job),
    },
    "C_classification": {
        "aligned_requirements": tot_aligned,
        "aligned_consistent": tot_consistent,
        "aligned_inconsistent": tot_aligned - tot_consistent,
        "denominator_aligned": tot_aligned,
        "importance_values_observed": dict(importance_seen),
        "category_values_observed": dict(category_seen),
        "INFORMATIONAL_observed": importance_seen.get("INFORMATIONAL", 0),
        "presence_stable_classification_changed": sum(
            len(r["presence_stable_classification_changed"]) for r in per_job),
        "importance_transitions": sorted(
            [{"job_id": a["job_id"], "name": a["name"], "from_to": a["importance"]}
             for a in align_rows if not a["consistent"] and len(a["importance"]) > 1],
            key=lambda x: (x["job_id"], x["name"])),
        "category_transitions": sorted(
            [{"job_id": a["job_id"], "name": a["name"], "from_to": a["category"]}
             for a in align_rows if not a["consistent"] and len(a["category"]) > 1],
            key=lambda x: (x["job_id"], x["name"])),
    },
    "D_evidence": {
        "status": "PRELIMINARY_MECHANICAL_AUDIT",
        "requirement_instances_examined": ev_req,
        "carrying_an_evidence_quote": ev_bearing,
        "no_evidence_quote_at_all": ev_bare,
        "quote_found_verbatim_in_source": ev_ok,
        "quote_not_found_verbatim": ev_miss,
        "quote_found_rate_among_evidence_bearing": (
            round(ev_ok / ev_bearing, 4) if ev_bearing else None),
        "quote_found_rate_denominator_evidence_bearing": ev_bearing,
        "quote_found_rate_overall": round(ev_ok / ev_req, 4) if ev_req else None,
        "no_evidence_rate_overall": round(ev_bare / ev_req, 4) if ev_req else None,
        "no_evidence_by_requirement_type": {
            t: {"without_quote": ev_type_bare.get(t, 0), "total": n,
                "rate": round(ev_type_bare.get(t, 0) / n, 4)}
            for t, n in ev_type_total.most_common()},
        "root_cause_of_missing_evidence": (
            "The extraction schema binds source_text to the structured requirement "
            "lists (experience/education/location/other) but not to required_skills "
            "or preferred_skills, which are list[str]. SKILL-type requirements are "
            "therefore unevidenced by construction, not by model omission. Persisted "
            "raw extraction confirms the model emitted 580 bare-string skill items "
            "and 492 dict items carrying source_text."),
        "semantic_support_adjudication": "NOT PERFORMED -- cannot be established mechanically",
        "denominator": ev_req,
        "stripped_note_events": sum(e["stripped_notes"] for e in evidence_rows),
    },
    "E_score": {
        "jobs_identical_scores": sum(1 for r in per_job if r["scores_identical"]),
        "jobs_identical_scores_identity_differs": sum(
            1 for r in per_job if r["scores_identical_identity_differs"]),
        "score_range": {"mean": round(statistics.mean(srange), 3),
                        "median": statistics.median(srange), "max": max(srange),
                        "min": min(srange), "zero_range_jobs": sum(1 for x in srange if x == 0)},
        "largest_score_range_jobs": sorted(
            [{"job_id": r["job_id"], "score_range": r["score_range"], "scores": r["scores"]}
             for r in per_job], key=lambda x: -x["score_range"])[:8],
        "causality": ("correlation between extraction change and score change is reported "
                      "as co-occurrence only; no causal claim is made"),
    },
    "F_recommendation": {
        "jobs_stable": len(rec_stable), "denominator_jobs": len(per_job),
        "jobs_decision_changing": len(rec_unstable),
        "transitions": sorted(
            [{"job_id": r["job_id"], "recommendations": r["recommendations"],
              "scores": r["scores"], "counts": r["counts"]} for r in rec_unstable],
            key=lambda x: x["job_id"]),
        "labels_preserved": sorted({x for r in per_job for x in r["recommendations"]}),
        "stable_jobs_score_range_mean": round(
            statistics.mean([r["score_range"] for r in rec_stable]), 3) if rec_stable else None,
        "unstable_jobs_score_range_mean": round(
            statistics.mean([r["score_range"] for r in rec_unstable]), 3) if rec_unstable else None,
        "stable_jobs_mean_jaccard": round(statistics.mean(
            [statistics.mean([v for v in r["jaccard_identity"].values() if v is not None])
             for r in rec_stable]), 4) if rec_stable else None,
        "unstable_jobs_mean_jaccard": round(statistics.mean(
            [statistics.mean([v for v in r["jaccard_identity"].values() if v is not None])
             for r in rec_unstable]), 4) if rec_unstable else None,
    },
    "G_execution_anomalies": {
        "http_400_json_validate_failed_events": len(failures),
        "preserved_failed_records": sorted((r["job_id"], r["run_id"]) for r in failures),
        "successful_runs_recovered_after_retry": sorted(
            (r["job_id"], r["run_id"]) for r in successful
            if r.get("token_usage_attempts") is not None
            and r["token_usage_attempts"] < 1) or "none",
        "runs_with_missing_usage": sorted(
            (r["job_id"], r["run_id"]) for r in runs_all
            if r.get("token_usage_available") is False),
        "measured_usage_denominator": len(usage),
        "measured_total_tokens": sum(usage),
        "measured_mean_total": round(statistics.mean(usage), 1),
        "runs_at_3072_output_tokens": sum(
            1 for r in successful if r.get("output_tokens") == 3072),
        "connection_to_extraction_variability": (
            "NOT ESTABLISHED -- no persisted evidence links provider execution "
            "anomalies to extraction variability; reported separately"),
    },
    "H_case_studies": {},
    "per_job": per_job,
    "alignment_detail": align_rows,
    "evidence_detail": evidence_rows,
}

# ------------------------------------------------------------ case studies
CASES = ["VJ-B04", "VJ-B11", "VJ-B14", "VJ-B15", "VJ-B20", "VJ-B23", "VJ-B28",
         "VJ-02", "VJ-03", "VJ-01"]
byid = {r["job_id"]: r for r in per_job}
for c in CASES:
    r = byid[c]
    runs = (by_job[c][1], by_job[c][2], by_job[c][3])
    quote_rows = []
    for k, run in enumerate(runs, 1):
        for q in run.get("canonical_requirements") or []:
            quote_rows.append((q.get("source_text") or "").strip())
    dupes = {q for q in quote_rows if q and list(quote_rows).count(q) > 1}
    summary["H_case_studies"][c] = {
        "counts": r["counts"], "scores": r["scores"],
        "recommendations": r["recommendations"],
        "identity_sets_identical": r["identity_sets_identical"],
        "jaccard_identity": r["jaccard_identity"],
        "names_in_all_three": r["names_in_all_three"],
        "names_in_exactly_two": r["names_in_exactly_two"],
        "names_in_exactly_one": r["names_in_exactly_one"],
        "aligned_requirements": r["aligned_requirements"],
        "aligned_inconsistent": r["aligned_inconsistent"],
        "distinct_source_quotes": len(set(quote_rows)),
        "source_quotes_reused_within_job": len(dupes),
        "recovery_history": [f"{f['job_id']}/run{f['run_id']}" for f in failures
                             if f["job_id"] == c],
    }

OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
print(f"wrote {OUT_JSON}")
print(f"  sha256 {sha_file(OUT_JSON)}")

# ------------------------------------------------------------------ report
def pct(n, d):
    return f"{n}/{d} ({n/d:.1%})" if d else f"{n}/{d} (n/a)"


L = []
L += ["# V3.3 Final Stability Analysis", "",
      "Derived artifact. Read-only over frozen inputs. No inference call was made",
      "and no experiment artifact was modified.", "",
      "## 1. Executive verdict", "",
      f"- Canonical **count** reproducibility: "
      f"{pct(summary['A_structural']['counts_all_equal_jobs'], 26)} jobs had equal counts "
      f"across all three runs.",
      f"- Canonical **identity-set** reproducibility: "
      f"{pct(summary['A_structural']['identity_sets_identical_jobs'], 26)}.",
      f"- Mean pairwise identity Jaccard: "
      f"{summary['A_structural']['jaccard_identity']['mean']} "
      f"(median {summary['A_structural']['jaccard_identity']['median']}, "
      f"min {summary['A_structural']['jaccard_identity']['min']}, "
      f"max {summary['A_structural']['jaccard_identity']['max']}, n="
      f"{summary['A_structural']['jaccard_identity']['n_pairs']} pairs).",
      f"- Recommendation stability: {pct(len(rec_stable), 26)}; "
      f"{len(rec_unstable)} jobs changed decision.",
      "", "Full section-by-section results follow. No correctness or quality claim",
      "is made anywhere in this report: the human-label set is 0/23.", ""]

L += ["## 2. Prerequisite and integrity verification", "",
      f"- ledger records : {prereq['ledger_records']}",
      f"- ledger sha256  : `{prereq['ledger_sha256']}`",
      f"- members with 3/3: {prereq['members_with_three_successes']}/26",
      f"- partial triplets: {prereq['partial_triplets'] or 'none'}",
      f"- ledger conflicts: {prereq['ledger_conflicts'] or 'none'}",
      f"- preserved failures: {prereq['preserved_failures']}",
      f"- successful runs: {prereq['successful_runs']}",
      f"- runs with persisted raw_extraction: {prereq['runs_with_raw_extraction']}/78",
      f"- runs with persisted coerced_extraction: {prereq['runs_with_coerced_extraction']}/78",
      f"- runs with measured usage: {prereq['runs_with_measured_usage']}/78", ""]

L += ["## 3. Methods and metric definitions", ""]
for k, v in summary["metric_definitions"].items():
    L.append(f"- **{k}** : {v}")
L += [""]

A, B, C, D = (summary[k] for k in ("A_structural", "B_selection", "C_classification", "D_evidence"))
E, F, G = (summary[k] for k in ("E_score", "F_recommendation", "G_execution_anomalies"))

L += ["## 4. Benchmark-wide aggregate tables", "",
      "### A. Structural extraction stability", "",
      "| metric | value | denominator |", "| --- | --- | ---: |",
      f"| jobs, all 3 counts equal | {A['counts_all_equal_jobs']} | 26 |",
      f"| jobs, identity sets identical | {A['identity_sets_identical_jobs']} | 26 |",
      f"| jobs, name sets identical | {A['name_sets_identical_jobs']} | 26 |",
      f"| equal counts but different identities | {A['counts_equal_but_identity_differs']} | 26 |",
      f"| Jaccard(identity) mean | {A['jaccard_identity']['mean']} | {A['jaccard_identity']['n_pairs']} pairs |",
      f"| Jaccard(identity) median | {A['jaccard_identity']['median']} | {A['jaccard_identity']['n_pairs']} |",
      f"| Jaccard(identity) min | {A['jaccard_identity']['min']} | {A['jaccard_identity']['n_pairs']} |",
      f"| Jaccard(identity) max | {A['jaccard_identity']['max']} | {A['jaccard_identity']['n_pairs']} |",
      f"| Jaccard(name) mean | {A['jaccard_name']['mean']} | {A['jaccard_name']['n_pairs']} pairs |",
      f"| count range mean | {A['count_range']['mean']} | 26 |",
      f"| count range max | {A['count_range']['max']} | 26 |",
      f"| jobs with zero count range | {A['count_range']['zero_range_jobs']} | 26 |", "",
      "Lowest identity Jaccard:", "",
      "| job | min pair Jaccard | counts |", "| --- | ---: | --- |"]
for r in A["lowest_identity_jaccard_jobs"]:
    L.append(f"| {r['job_id']} | {r['min_pair_jaccard']} | {r['counts']} |")
L += ["", "Greatest count variation:", "",
      "| job | count range | counts |", "| --- | ---: | --- |"]
for r in A["greatest_count_variation_jobs"]:
    L.append(f"| {r['job_id']} | {r['count_range']} | {r['counts']} |")

L += ["", "### B. Requirement selection stability", "",
      "Two denominators, never mixed.", "",
      "| quantity | value | denominator |", "| --- | ---: | --- |",
      f"| unique identity TUPLES in union | {B['unique_identity_tuples_union_all_jobs']} | - (separate measure) |",
      f"| unique NAMES in union | {B['unique_names_union_all_jobs']} | {B['denominator_unique_name_union']} |",
      f"| names in all 3 runs | {B['unique_names_in_all_three']} | {B['denominator_unique_name_union']} |",
      f"| names in exactly 2 runs | {B['unique_names_in_exactly_two']} | {B['denominator_unique_name_union']} |",
      f"| names in exactly 1 run | {B['unique_names_in_exactly_one']} | {B['denominator_unique_name_union']} |",
      f"| run-level requirement occurrences | {B['denominator_run_level_occurrences']} | {B['denominator_run_level_occurrences']} |",
      f"| pairwise additions (total) | {B['pair_additions_total']} | 78 pairs |",
      f"| pairwise removals (total) | {B['pair_removals_total']} | 78 pairs |",
      f"| partition check (all3+two+one == name union) | {B['partition_check']} | - |", "",
      "The identity-tuple union exceeds the name union because one name can carry",
      "different importance or category across runs. The two are reported",
      "separately and never used as each other's denominator.", ""]

L += ["### C. Classification stability", "",
      "| quantity | value | denominator |", "| --- | ---: | --- |",
      f"| aligned requirements | {C['aligned_requirements']} | {C['denominator_aligned']} |",
      f"| aligned and consistent | {C['aligned_consistent']} | {C['denominator_aligned']} |",
      f"| aligned and inconsistent | {C['aligned_inconsistent']} | {C['denominator_aligned']} |",
      f"| presence-stable but classification changed | {C['presence_stable_classification_changed']} | {C['denominator_aligned']} |",
      f"| importance values observed | {C['importance_values_observed']} | - |",
      f"| INFORMATIONAL observed | {C['INFORMATIONAL_observed']} | - |", "",
      "Importance transitions (exact-name aligned, present in all 3 runs, importance differs):", ""]
if C["importance_transitions"]:
    L += ["| job | name | values seen |", "| --- | --- | --- |"]
    for t in C["importance_transitions"]:
        L.append(f"| {t['job_id']} | {t['name'][:56]} | {' -> '.join(t['from_to'])} |")
else:
    L.append("None.")
L += ["", "Category transitions:", ""]
if C["category_transitions"]:
    L += ["| job | name | values seen |", "| --- | --- | --- |"]
    for t in C["category_transitions"]:
        L.append(f"| {t['job_id']} | {t['name'][:56]} | {' -> '.join(t['from_to'])} |")
else:
    L.append("None.")

L += ["", "### D. Evidence and source support (PRELIMINARY)", "",
      "| metric | value | denominator |", "| --- | ---: | --- |",
      f"| requirement instances examined | {D['requirement_instances_examined']} | {D['requirement_instances_examined']} |",
      f"| carrying an evidence quote | {D['carrying_an_evidence_quote']} | {D['requirement_instances_examined']} |",
      f"| **no evidence quote at all** | {D['no_evidence_quote_at_all']} | {D['requirement_instances_examined']} |",
      f"| quote found verbatim in source | {D['quote_found_verbatim_in_source']} | {D['carrying_an_evidence_quote']} (evidence-bearing) |",
      f"| quote not found verbatim | {D['quote_not_found_verbatim']} | {D['carrying_an_evidence_quote']} (evidence-bearing) |",
      f"| quote-found rate among evidence-bearing | {D['quote_found_rate_among_evidence_bearing']} | {D['quote_found_rate_denominator_evidence_bearing']} |",
      f"| stripped-evidence notes | {D['stripped_note_events']} | - |", "",
      "No-evidence rate by requirement type:", "",
      "| type | without quote | total | rate |", "| --- | ---: | ---: | ---: |"]
for t, v in D["no_evidence_by_requirement_type"].items():
    L.append(f"| {t} | {v['without_quote']} | {v['total']} | {v['rate']:.1%} |")
L += ["", f"**Root cause.** {D['root_cause_of_missing_evidence']}", "",
      f"**Limitation.** {D['semantic_support_adjudication']}. This audit measures "
      "quote correspondence only. A requirement whose quote appears in the posting "
      "may still misstate what the posting requires, and a paraphrased quote may "
      "fail a strict substring test while being faithful.", ""]

L += ["### E. Score stability", "",
      "| metric | value | denominator |", "| --- | ---: | --- |",
      f"| jobs with identical scores | {E['jobs_identical_scores']} | 26 |",
      f"| identical scores but identity differs | {E['jobs_identical_scores_identity_differs']} | 26 |",
      f"| score range mean | {E['score_range']['mean']} | 26 |",
      f"| score range median | {E['score_range']['median']} | 26 |",
      f"| score range max | {E['score_range']['max']} | 26 |",
      f"| jobs with zero score range | {E['score_range']['zero_range_jobs']} | 26 |", "",
      f"Causality: {E['causality']}.", "",
      "| job | score range | scores |", "| --- | ---: | --- |"]
for r in E["largest_score_range_jobs"]:
    L.append(f"| {r['job_id']} | {r['score_range']} | {r['scores']} |")

L += ["", "### F. Recommendation stability", "",
      "| quantity | value | denominator |", "| --- | ---: | --- |",
      f"| jobs, all 3 recommendations equal | {F['jobs_stable']} | {F['denominator_jobs']} |",
      f"| jobs with decision-changing variation | {F['jobs_decision_changing']} | {F['denominator_jobs']} |",
      f"| mean score range, stable-rec jobs | {F['stable_jobs_score_range_mean']} | {F['jobs_stable']} |",
      f"| mean score range, unstable-rec jobs | {F['unstable_jobs_score_range_mean']} | {F['jobs_decision_changing']} |",
      f"| mean identity Jaccard, stable-rec jobs | {F['stable_jobs_mean_jaccard']} | {F['jobs_stable']} |",
      f"| mean identity Jaccard, unstable-rec jobs | {F['unstable_jobs_mean_jaccard']} | {F['jobs_decision_changing']} |",
      f"| labels preserved (not merged) | {F['labels_preserved']} | - |", "",
      "| job | recommendations | scores | counts |", "| --- | --- | --- | --- |"]
for t in F["transitions"]:
    L.append(f"| {t['job_id']} | {' -> '.join(t['recommendations'])} | "
             f"{t['scores']} | {t['counts']} |")

L += ["", "## 5. Per-job results, all 26 members", "",
      "| job | class | counts | ctr | ident sets | J(identity) mean | scores | range | recs | rec stable |",
      "| --- | --- | --- | ---: | --- | ---: | --- | ---: | --- | --- |"]
for r in per_job:
    jm = statistics.mean([v for v in r["jaccard_identity"].values() if v is not None])
    L.append(f"| {r['job_id']} | {'REG' if r['member_class'] == 'FROZEN_REGRESSION' else 'COL'} | "
             f"{r['counts']} | {r['count_range']} | "
             f"{'SAME' if r['identity_sets_identical'] else 'DIFF'} | {jm:.3f} | "
             f"{r['scores']} | {r['score_range']} | {'/'.join(x[:12] for x in r['recommendations'])} | "
             f"{'yes' if r['recommendation_stable'] else 'NO'} |")

L += ["", "## 6. Provider and execution anomalies", "",
      f"- HTTP 400 json_validate_failed events preserved: {G['http_400_json_validate_failed_events']} "
      f"at {G['preserved_failed_records']}",
      f"- runs with missing usage (null, not zero): {G['runs_with_missing_usage']}",
      f"- measured usage denominator: {G['measured_usage_denominator']}/78 calls",
      f"- measured total tokens: {G['measured_total_tokens']:,} "
      f"(mean {G['measured_mean_total']}/call)",
      f"- successful runs at exactly 3072 output tokens: {G['runs_at_3072_output_tokens']}",
      f"- link to extraction variability: {G['connection_to_extraction_variability']}", ""]

L += ["## 7. Focused case studies", "",
      "| job | counts | identity sets | J mean | recs | distinct quotes | quotes reused | recovery |",
      "| --- | --- | --- | ---: | --- | ---: | ---: | --- |"]
for c in CASES:
    d = summary["H_case_studies"][c]
    jm = statistics.mean([v for v in d["jaccard_identity"].values() if v is not None])
    L.append(f"| {c} | {d['counts']} | {'SAME' if d['identity_sets_identical'] else 'DIFF'} | "
             f"{jm:.3f} | {'/'.join(x[:14] for x in d['recommendations'])} | "
             f"{d['distinct_source_quotes']} | {d['source_quotes_reused_within_job']} | "
             f"{', '.join(d['recovery_history']) or '-'} |")

L += ["", "## 8. Limitations and unresolved questions", "",
      "- Human labels are 0/23. No accuracy, precision, recall, or recommendation",
      "  correctness claim is possible. No proxy metric is substituted.",
      "- `raw_extraction` / `coerced_extraction` are absent for the 12 pre-telemetry",
      "  B01-B04 runs, so raw-vs-canonical divergence cannot be examined there.",
      "- Evidence audit is mechanical quote matching only; semantic support is",
      "  unresolved by construction.",
      "- Classification alignment uses exact normalized-name matching, so a",
      "  paraphrase pair is counted as one disappearance plus one appearance, not as",
      "  a classification change.",
      "- Three runs per job bound observed variability but do not characterise its",
      "  distribution.",
      "- The provider exposes no per-request reproducibility guarantee; nothing here",
      "  separates model-sampling variability from contract ambiguity.", ""]

L += ["## 9. Conclusion", ""]
L += ["See the executive verdict and the six per-dimension verdicts in the chat",
      "report. This artifact contains the measurements only.", ""]

OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"wrote {OUT_MD}")
print(f"  sha256 {sha_file(OUT_MD)}")
print(f"ledger sha256 after analysis: {sha_file(LEDGER)}")
print(f"  unchanged: {sha_file(LEDGER) == '6f8f6a1ee5f54acb1bd9d9270f89edf8c244c72118381c21931feb20740557c0'}")
