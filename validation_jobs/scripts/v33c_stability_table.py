"""V3.3c Task B - authoritative 26-job stability table + aggregate dashboard.
DIAGNOSTIC ONLY. Reads the frozen run artifact; writes nothing it did not read.
"""
import collections
import hashlib
import json
import pathlib
from datetime import datetime, timezone

RUNS = json.loads(pathlib.Path(
    "docs/benchmark/v3_3c_extraction_reproducibility_runs.json").read_text(encoding="utf-8"))
META = RUNS["run_metadata"]
BM = json.loads(pathlib.Path(
    "docs/benchmark/matching_benchmark_v3.json").read_text(encoding="utf-8"))
JOB_IDS = [c["job_id"] for c in BM["cases"]]

by = collections.defaultdict(dict)
for r in RUNS["runs"]:
    by[r["job_id"]][r["run_id"]] = r

NM = "NOT_MEASURABLE"


def sets(run):
    return set(tuple(x) for x in run["canonical_requirement_set"])


rows = []
for jid in JOB_IDS:
    rs = by.get(jid, {})
    r1, r2, r3 = rs.get(1), rs.get(2), rs.get(3)
    ok = [x for x in (r1, r2, r3) if x and x["success"]]

    status = {i: ("OK" if rs.get(i) and rs[i]["success"]
                  else ("FAILED" if rs.get(i) else "NOT_RUN")) for i in (1, 2, 3)}

    complete = len(ok) == 3 and r1 and r2 and r3
    if complete:
        s1, s2, s3 = sets(r1), sets(r2), sets(r3)
        struct = "STABLE" if (s1 == s2 == s3) else "UNSTABLE"
        recs = [r1["recommendation"], r2["recommendation"], r3["recommendation"]]
        dec = "STABLE" if len(set(recs)) == 1 else "UNSTABLE"
        scores = [r1["score"], r2["score"], r3["score"]]
        added = len((s2 | s3) - s1) + len((s1 | s3) - s2)
        removed = len((s1 | s2) - s3)
        names = {i[0] for i in (s1 | s2 | s3)}
        modified = reclassified = 0
        for n in names:
            cand = [s for s in (s1, s2, s3) if n in {i[0] for i in s}]
            if len(cand) > 1:
                imps = {i[2] for s in cand for i in s if i[0] == n}
                yrs = {i[4] for s in cand for i in s if i[0] == n}
                if len(imps) > 1:
                    reclassified += 1
                elif len(yrs) > 1:
                    modified += 1
        diagnostics = {"SELECTION_VARIANCE" if added or removed else "",
                       "CLASSIFICATION_VARIANCE" if reclassified else ""}
        dclass = "SELECTION_AND_CLASSIFICATION_VARIANCE" if (added or removed) and reclassified \
            else ("SELECTION_VARIANCE" if (added or removed) else
                  ("CLASSIFICATION_VARIANCE" if reclassified else "STABLE"))
        ev_bad = sum(1 for c in (r1.get("canonical_requirements") or []) + (r2.get("canonical_requirements") or []) + (r3.get("canonical_requirements") or [])
                     if c.get("source_text") and c.get("evidence_ok") is False)
        ev_strip = sum(1 for r in (r1, r2, r3)
                       for n in (r.get("canonical_notes") or [])
                       if "not found in the job text" in n)
        row = {
            "job_id": jid, "run_1_status": status[1], "run_2_status": status[2],
            "run_3_status": status[3],
            "run_1_requirement_count": r1["canonical_requirement_count"],
            "run_2_requirement_count": r2["canonical_requirement_count"],
            "run_3_requirement_count": r3["canonical_requirement_count"],
            "structural_stability": struct,
            "run_1_score": r1["score"], "run_2_score": r2["score"],
            "run_3_score": r3["score"],
            "score_min": min(scores), "score_max": max(scores),
            "score_range": round(max(scores) - min(scores), 2),
            "run_1_recommendation": r1["recommendation"],
            "run_2_recommendation": r2["recommendation"],
            "run_3_recommendation": r3["recommendation"],
            "decision_stability": dec,
            "added_count": added, "removed_count": removed,
            "modified_count": modified, "reclassified_count": reclassified,
            "source_evidence_invalid_count": ev_bad,
            "source_evidence_stripped_count": ev_strip,
            "diagnostic_status": "MEASURABLE",
            "diagnostic_class": dclass,
        }
    else:
        row = {
            "job_id": jid, "run_1_status": status[1], "run_2_status": status[2],
            "run_3_status": status[3],
            "run_1_requirement_count": NM, "run_2_requirement_count": NM,
            "run_3_requirement_count": NM,
            "structural_stability": NM,
            "run_1_score": NM, "run_2_score": NM, "run_3_score": NM,
            "score_min": NM, "score_max": NM, "score_range": NM,
            "run_1_recommendation": NM, "run_2_recommendation": NM,
            "run_3_recommendation": NM,
            "decision_stability": NM,
            "added_count": NM, "removed_count": NM, "modified_count": NM,
            "reclassified_count": NM,
            "source_evidence_invalid_count": NM,
            "source_evidence_stripped_count": NM,
            "diagnostic_status": "NOT_MEASURABLE",
            "diagnostic_class": NM,
        }
    rows.append(row)

meas = [r for r in rows if r["diagnostic_status"] == "MEASURABLE"]
nonmeas = [r for r in rows if r["diagnostic_status"] != "MEASURABLE"]
ranges = [r["score_range"] for r in meas]


def mean(xs):
    return round(sum(xs) / len(xs), 2) if xs else None


def median(xs):
    return sorted(xs)[len(xs) // 2] if xs else None


agg = {
    "jobs_total": len(rows),
    "jobs_measurable": len(meas),
    "jobs_not_measurable": len(nonmeas),
    "structurally_stable": sum(1 for r in meas if r["structural_stability"] == "STABLE"),
    "structurally_unstable": sum(1 for r in meas if r["structural_stability"] == "UNSTABLE"),
    "decision_stable": sum(1 for r in meas if r["decision_stability"] == "STABLE"),
    "decision_unstable": sum(1 for r in meas if r["decision_stability"] == "UNSTABLE"),
    "structural_stability_rate_among_measurable":
        f"{sum(1 for r in meas if r['structural_stability'] == 'STABLE')}/{len(meas)}",
    "decision_stability_rate_among_measurable":
        f"{sum(1 for r in meas if r['decision_stability'] == 'STABLE')}/{len(meas)}",
    "rate_note": "Denominator is measurable jobs only. Not presented as a 26-job rate.",
    "mean_score_range": mean(ranges),
    "median_score_range": median(ranges),
    "max_score_range": max(ranges) if ranges else None,
    "total_added": sum(r["added_count"] for r in meas),
    "total_removed": sum(r["removed_count"] for r in meas),
    "total_modified": sum(r["modified_count"] for r in meas),
    "total_reclassified": sum(r["reclassified_count"] for r in meas),
    "total_invalid_source_evidence": sum(r["source_evidence_invalid_count"] for r in meas),
    "total_stripped_source_evidence": sum(r["source_evidence_stripped_count"] for r in meas),
    "diagnostic_class_distribution": dict(
        collections.Counter(r["diagnostic_class"] for r in meas)),
}

table = {
    "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "status": "V3.3 INCOMPLETE - EXPERIMENT NOT COMPLETED",
    "provenance": {
        "implementation_identifier": "dcc4f506965d57e99bf0bb54bdd1c429",
        "prompt_sha256": META["system_prompt_sha256"],
        "schema_version": META["schema_version"],
        "provider": META["provider"], "model": META["model"],
        "temperature": META["temperature"], "seed": META["seed"],
        "profile_sha256": META["profile_sha256"],
        "experiment_artifact_sha256": hashlib.sha256(
            pathlib.Path("docs/benchmark/v3_3c_extraction_reproducibility_runs.json")
            .read_bytes()).hexdigest(),
        "benchmark_sha256": hashlib.sha256(
            pathlib.Path("docs/benchmark/matching_benchmark_v3.json")
            .read_bytes()).hexdigest(),
    },
    "aggregate": agg,
    "jobs": rows,
}

pathlib.Path("docs/benchmark/v3_3c_26_job_stability.json").write_text(
    json.dumps(table, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(agg, indent=2))