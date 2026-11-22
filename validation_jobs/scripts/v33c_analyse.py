"""V3.3c post-experiment analysis. Measurement only."""
import collections
import hashlib
import json
import pathlib

RUNS_PATH = pathlib.Path(
    "docs/benchmark/v3_3c_extraction_reproducibility_runs.json")
doc = json.loads(RUNS_PATH.read_text(encoding="utf-8"))
runs = doc["runs"]
meta = doc["run_metadata"]

by = collections.defaultdict(list)
for r in runs:
    by[r["job_id"]].append(r)
for j in by:
    by[j].sort(key=lambda x: x["run_id"])

successful = [r for r in runs if r["success"]]
failed = [r for r in runs if not r["success"]]


def diff(a: set, b: set) -> dict:
    da, db = {i[0]: i for i in a}, {i[0]: i for i in b}
    added = sorted(set(db) - set(da))
    removed = sorted(set(da) - set(db))
    modified, reclassified = [], []
    for n in set(da) & set(db):
        if da[n][2] != db[n][2]:
            reclassified.append({"name": n, "from": da[n][2], "to": db[n][2]})
        elif da[n][4] != db[n][4]:
            modified.append({"name": n, "from": da[n][4], "to": db[n][4]})
    return {"added": added, "removed": removed, "modified": modified,
            "reclassified": reclassified,
            "reordered_only": sorted(set(da) ^ set(db))}


complete = []
jobs = {}
diff_counts = collections.Counter()
importance_drift = []
ev_valid = ev_invalid = ev_stripped = 0

for jid, rs in sorted(by.items()):
    ok = [r for r in rs if r["success"]]
    sets = [set(tuple(x) for x in r["canonical_requirement_set"]) for r in ok]
    is_complete = len(ok) == 3
    identical = is_complete and sets[0] == sets[1] == sets[2]
    recs = [r["recommendation"] for r in ok]
    scores = [r["score"] for r in ok]
    if is_complete:
        complete.append(jid)

    jd = []
    for i in (1, 2):
        if len(sets) <= i:
            continue
        d = diff(sets[0], sets[i])
        for k in ("added", "removed", "modified", "reclassified"):
            diff_counts[k.upper()] += len(d[k])
        if d["reordered_only"]:
            diff_counts["REORDERED_ONLY"] += len(d["reordered_only"])
        for rc in d["reclassified"]:
            importance_drift.append({"job_id": jid, "requirement": rc["name"],
                                     "from": rc["from"], "to": rc["to"],
                                     "run_1": 1, "run_2": i + 1})
        jd.append({"run_1": 1, "run_2": i + 1, **d})

    for r in ok:
        for c in r.get("canonical_requirements", []):
            if not c.get("source_text"):
                continue
            if c.get("evidence_ok", True):
                ev_valid += 1
            else:
                ev_invalid += 1
        for note in (r.get("canonical_notes") or []):
            if "not found in the job text" in note:
                ev_stripped += 1

    jobs[jid] = {
        "successful_runs": len(ok),
        "triplet_complete": is_complete,
        "structurally_stable": identical,
        "decision_stable": is_complete and len(set(recs)) == 1,
        "canonical_counts": [r["canonical_requirement_count"] for r in ok],
        "raw_counts": [r["raw_requirement_count"] for r in ok],
        "scores": scores,
        "recommendations": recs,
        "blocker_counts": [r["blocker_count"] for r in ok],
        "score_range": round(max(scores) - min(scores), 2) if scores else None,
        "differences": jd,
    }

struct_stable = [j for j, v in jobs.items() if v["structurally_stable"]]
struct_unstable = [j for j, v in jobs.items() if v["triplet_complete"]
                  and not v["structurally_stable"]]
dec_stable = [j for j, v in jobs.items() if v["decision_stable"]]
dec_unstable = [j for j, v in jobs.items() if v["triplet_complete"]
                and not v["decision_stable"]]
ranges = [v["score_range"] for v in jobs.values()
          if v["triplet_complete"] and v["score_range"] is not None]
nonzero = [r for r in ranges if r > 0]
threshold_cross = [j for j, v in jobs.items() if v["triplet_complete"]
                   and len(set(v["recommendations"])) > 1]
all_counts = [r["canonical_requirement_count"] for r in successful]

report = {
    "version": "3.3c",
    "experiment": "v3.3c_multi_window_frozen_execution",
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
        "failure_codes": dict(collections.Counter(r["failure_code"] for r in failed)),
        "failure_reason": "Groq tokens-per-day quota exhaustion (429). "
                          "No Groq call was made outside this experiment.",
        "jobs_started": len(by),
        "job_triplets_complete": len(complete),
        "tokens_per_call_estimate": 4276,
        "tokens_observed_successful_calls": 4276 * len(successful),
    },
    "windows": [
        {"window": 1, "jobs": "VJ-B01..VJ-B12", "planned_calls": 36,
         "successful_calls": 12, "triplets_completed": 4,
         "outcome": "quota exhausted at VJ-B05"},
        {"window": 2, "jobs": "VJ-B13..VJ-B24", "planned_calls": 36,
         "successful_calls": 0, "triplets_completed": 0,
         "outcome": "quota already exhausted; VJ-B13 run1 failed"},
        {"window": 3, "jobs": "VJ-B25..VJ-B26", "planned_calls": 6,
         "successful_calls": 0, "triplets_completed": 0,
         "outcome": "quota already exhausted; VJ-B25 run1 failed"},
    ],
    "stability": {
        "structural_gate_required": 26,
        "triplets_measurable": len(complete),
        "structurally_stable": len(struct_stable),
        "structurally_unstable": len(struct_unstable),
        "structural_gate_passed": len(struct_stable) == 26,
        "decision_gate_required": 26,
        "decision_stable": len(dec_stable),
        "decision_unstable": len(dec_unstable),
        "decision_gate_passed": len(dec_stable) == 26,
    },
    "requirement_counts": {
        "mean": round(sum(all_counts) / len(all_counts), 2) if all_counts else None,
        "median": sorted(all_counts)[len(all_counts) // 2] if all_counts else None,
        "min": min(all_counts) if all_counts else None,
        "max": max(all_counts) if all_counts else None,
    },
    "score_stability": {
        "mean_score_range": round(sum(ranges) / len(ranges), 2) if ranges else None,
        "median_score_range": sorted(ranges)[len(ranges) // 2] if ranges else None,
        "max_score_range": max(ranges) if ranges else None,
        "jobs_with_score_variation": len(nonzero),
        "jobs_crossing_recommendation_threshold": len(threshold_cross),
        "jobs_with_score_variation_but_stable_decision": [
            j for j, v in jobs.items()
            if v["triplet_complete"] and v["score_range"] and v["decision_stable"]
        ],
    },
    "difference_counts": dict(diff_counts),
    "importance_stability": {
        "reclassified_events": len(importance_drift),
        "transitions": importance_drift,
    },
    "source_evidence": {
        "requirements_with_valid_evidence": ev_valid,
        "requirements_with_invalid_evidence": ev_invalid,
        "requirements_stripped_due_to_invalid_evidence": ev_stripped,
    },
    "jobs": jobs,
    "disposition": "V3.3 INCOMPLETE - EXPERIMENT NOT COMPLETED",
}

pathlib.Path("docs/benchmark/v3_3c_extraction_reproducibility.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

for k in ("execution", "stability", "requirement_counts", "score_stability",
          "difference_counts", "importance_stability", "source_evidence",
          "disposition"):
    print(k, "=", json.dumps(report[k], indent=2) if isinstance(report[k], (dict, list))
          else report[k])