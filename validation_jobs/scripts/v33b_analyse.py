"""V3.3b post-experiment analysis. Measurement only - no code changes."""
import collections
import hashlib
import json
import pathlib

RUNS = json.loads(pathlib.Path(
    "docs/benchmark/v3_3_extraction_reproducibility_runs.json").read_text(encoding="utf-8"))
runs = RUNS["runs"]
meta = RUNS["run_metadata"]

STRUCT = ("experience_requirements", "education_requirements",
          "location_requirements", "other_requirements")
SKILL_FIELDS = (0, 1, 2, 3, 4)  # identity tuple positions


def canon_by_job():
    by = collections.defaultdict(list)
    for r in runs:
        by[r["job_id"]].append(r)
    for j in by:
        by[j].sort(key=lambda x: x["run_id"])
    return by


def sets_of(rs):
    return [set(tuple(x) for x in r["canonical_requirement_set"])
            for r in rs if r["success"]]


def difference(a: set, b: set) -> dict:
    """ADDED / REMOVED / MODIFIED / RECLASSIFIED / REORDERED_ONLY."""
    da = {i[0]: i for i in a}
    db = {i[0]: i for i in b}
    added = sorted(set(db) - set(da))
    removed = sorted(set(da) - set(db))
    modified, reclassified = [], []
    for name in set(da) & set(db):
        if da[name][2] != db[name][2]:
            reclassified.append({"name": name, "from": da[name][2],
                                 "to": db[name][2]})
        elif da[name][4] != db[name][4]:
            modified.append({"name": name, "from": da[name][4],
                             "to": db[name][4]})
    reordered = sorted(set(da) ^ set(db))
    return {"added": added, "removed": removed, "modified": modified,
            "reclassified": reclassified, "reordered_only": reordered}


by = canon_by_job()
successful = [r for r in runs if r["success"]]
failed = [r for r in runs if not r["success"]]

stable, unstable, decidable = [], [], []
job_reports = {}
diff_counts = collections.Counter()
importance_drift = []
evidence_valid = evidence_invalid = evidence_stripped = 0

for jid, rs in sorted(by.items()):
    sets = sets_of(rs)
    n_ok = len(sets)
    identical = (n_ok >= 3 and sets[0] == sets[1] == sets[2])
    recs = [r["recommendation"] for r in rs if r["success"]]
    scores = [r["score"] for r in rs if r["success"]]
    counts = [r["canonical_requirement_count"] for r in rs if r["success"]]

    if identical:
        stable.append(jid)
    else:
        unstable.append(jid)
    if n_ok >= 3 and len(set(recs)) == 1:
        decidable.append(jid)

    job_diffs = []
    for i in (1, 2):
        if n_ok <= i:
            continue
        d = difference(sets[0], sets[i])
        for k in ("added", "removed", "modified", "reclassified"):
            diff_counts[k.upper()] += len(d[k])
        if d["reordered_only"]:
            diff_counts["REORDERED_ONLY"] += len(d["reordered_only"])
        for rc in d["reclassified"]:
            importance_drift.append({
                "job_id": jid, "requirement": rc["name"],
                "from": rc["from"], "to": rc["to"],
                "run_1": 1, "run_2": i + 1,
            })
        job_diffs.append({"run_1": 1, "run_2": i + 1,
                          "added": d["added"], "removed": d["removed"],
                          "modified": d["modified"],
                          "reclassified": d["reclassified"],
                          "reordered_only": d["reordered_only"]})

    # source-evidence audit
    for r in rs:
        if not r["success"]:
            continue
        for c in r.get("canonical_requirements", []):
            if not c.get("source_text"):
                continue
            if c.get("evidence_ok", True):
                evidence_valid += 1
            else:
                evidence_invalid += 1
        for note in (r.get("canonical_notes") or []):
            if "not found in the job text" in note:
                evidence_stripped += 1

    job_reports[jid] = {
        "successful_runs": n_ok,
        "structurally_stable": identical,
        "decision_stable": (n_ok >= 3 and len(set(recs)) == 1),
        "canonical_counts": counts,
        "raw_counts": [r["raw_requirement_count"] for r in rs if r["success"]],
        "scores": scores,
        "recommendations": recs,
        "blocker_counts": [r["blocker_count"] for r in rs if r["success"]],
        "differences": job_diffs,
    }

all_counts = [r["canonical_requirement_count"] for r in successful]
spreads = [max(v["canonical_counts"]) - min(v["canonical_counts"])
           for v in job_reports.values() if len(v["canonical_counts"]) >= 2]

per_call_tokens = 4276
report = {
    "version": "3.3b",
    "experiment": "v3.3b_frozen_reproducibility_execution",
    "run_metadata": meta,
    "implementation_identifier": "dcc4f506965d57e99bf0bb54bdd1c429",
    "harness_sha256": hashlib.sha256(
        pathlib.Path("validation_jobs/scripts/v33_runs.py").read_bytes()
    ).hexdigest(),
    "frozen_artifact_sha256": {
        "matching_benchmark_v3.json":
            "4199f5d386e1fb8b9be1a6c053c0c9cc6f2e6e8afeadc31112e650c34f37345f",
        "human_labels_v3.json":
            "292841efc8b16f5d1569cf015bffba9ecfd2ef80d4b98387e7078f9d53fe0f12",
        "blind_review_pack_v3.json":
            "d70aace7ae28b52196604464dceff9313a325fe82e24292b539e384baebdaf9a",
    },
    "execution": {
        "planned": 78,
        "attempted": len(runs),
        "successful": len(successful),
        "failed": len(failed),
        "failure_code": dict(collections.Counter(r["failure_code"] for r in failed)),
        "failure_reason": "Groq tokens-per-day quota exhaustion (429). "
                          f"Limit 200000, used 197363 at first denial.",
        "tokens_per_call_observed": per_call_tokens,
        "tokens_required_for_78": per_call_tokens * 78,
        "daily_budget": 200000,
        "budget_multiples_required": round(per_call_tokens * 78 / 200000, 2),
    },
    "stability": {
        "jobs_total": len(by),
        "jobs_with_3_successful_runs": len(decidable),
        "structurally_stable_measurable": len(stable),
        "structurally_unstable_measurable": len(unstable),
        "decision_stable_measurable": len(decidable),
        "structural_gate_required": 26,
        "structural_gate_passed": False,
        "decision_gate_required": 26,
        "decision_gate_passed": False,
    },
    "requirement_counts": {
        "mean": round(sum(all_counts) / len(all_counts), 2) if all_counts else None,
        "median": sorted(all_counts)[len(all_counts) // 2] if all_counts else None,
        "min": min(all_counts) if all_counts else None,
        "max": max(all_counts) if all_counts else None,
        "mean_within_job_spread": round(sum(spreads) / len(spreads), 2) if spreads else None,
    },
    "difference_counts": dict(diff_counts),
    "importance_drift": importance_drift,
    "importance_drift_count": len(importance_drift),
    "source_evidence": {
        "requirements_with_valid_evidence": evidence_valid,
        "requirements_with_invalid_evidence": evidence_invalid,
        "requirements_stripped_due_to_invalid_evidence": evidence_stripped,
    },
    "jobs": job_reports,
    "disposition": "V3.3b INCOMPLETE - EXPERIMENT NOT COMPLETED",
}

pathlib.Path("docs/benchmark/v3_3b_extraction_reproducibility.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

print(json.dumps({k: report[k] for k in (
    "execution", "stability", "requirement_counts", "difference_counts",
    "importance_drift_count", "source_evidence", "disposition")},
    indent=2))