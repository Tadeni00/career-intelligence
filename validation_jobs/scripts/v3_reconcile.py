"""V3 — build the reconciliation analysis pipeline and final metrics.

Combines human labels (currently 3 pre-existing, 23 PENDING) with system output.
Runs cleanly with labels pending so the pipeline itself is verified.
"""
import json
import pathlib

BENCH = pathlib.Path("docs/benchmark/matching_benchmark_v3.json")
LABELS = pathlib.Path("docs/benchmark/human_labels_v3.json")
OUT = pathlib.Path("docs/benchmark/v3_decision_analysis.json")

bench = json.loads(BENCH.read_text(encoding="utf-8"))
labels_doc = json.loads(LABELS.read_text(encoding="utf-8"))
labels = {row["job_id"]: row for row in labels_doc["labels"]}

# The 3 frozen cases carry labels recorded before V3.
FROZEN = {
    "VJ-01": {"decision": "MAYBE",
              "primary_reason": "Strong technical and experience match, but the "
                                "role is restricted to UK-based candidates and "
                                "the candidate is in Lagos.",
              "hard_blocker": False},
    "VJ-02": {"decision": "NO",
              "primary_reason": "Remote (US) only, and the candidate lacks the "
                                "core ML stack the role is built around.",
              "hard_blocker": False},
    "VJ-03": {"decision": "YES",
              "primary_reason": "Directly aligned with the candidate's "
                                "confirmed data analysis experience.",
              "hard_blocker": False},
}


def norm(rec: str) -> str:
    return {"APPLY": "YES", "APPLY_WITH_TAILORING": "YES",
            "STRETCH": "MAYBE", "SKIP": "NO"}[rec]


rows = []
for case in bench["cases"]:
    jid = case["job_id"]
    if jid in FROZEN:
        human = FROZEN[jid]["decision"]
        reason = FROZEN[jid]["primary_reason"]
        source = "pre-V3 frozen label"
    else:
        row = labels.get(jid, {})
        human = row.get("decision")
        reason = row.get("primary_reason")
        source = "blind human label"
    sys_dec = case["system"]["recommendation"]
    rows.append({
        "job_id": jid,
        "human_decision": human,
        "human_source": source if human else "PENDING",
        "human_reason": reason,
        "system_recommendation": sys_dec,
        "system_score": case["system"]["overall_score"],
        "components": {k: case["system"][k] for k in
                       ("technical", "experience", "education", "location", "other")},
        "blockers": case["system"]["blockers"],
        "required_coverage": case["system"]["required_coverage"],
        "requirements_extracted": case["requirements_extracted"],
    })

labelled = [r for r in rows if r["human_decision"]]
agreement = [r for r in labelled
             if norm(r["system_recommendation"]) == r["human_decision"]]
false_skip = [r for r in labelled
              if r["system_recommendation"] == "SKIP" and r["human_decision"] == "YES"]
false_apply = [r for r in labelled
               if r["system_recommendation"] in ("APPLY", "APPLY_WITH_TAILORING")
               and r["human_decision"] == "NO"]
severe = [r for r in labelled
          if {norm(r["system_recommendation"]), r["human_decision"]} == {"YES", "NO"}]
near = [r for r in labelled
        if r["human_decision"] != norm(r["system_recommendation"])
        and r not in severe]

# Requirement-level disagreement analysis (per section 21).
analysis = []
for r in labelled:
    if norm(r["system_recommendation"]) == r["human_decision"]:
        continue
    analysis.append({
        "job_id": r["job_id"],
        "human_decisive_factor": r["human_reason"],
        "engine_decisive_factor": (
            f"blockers={r['blockers']}" if r["blockers"]
            else f"overall={r['system_score']}, lowest component="
                 f"{min(r['components'], key=r['components'].get)}"
                 f"({min(r['components'].values())})"
        ),
        "same_job_requirements": True,
        "same_candidate_evidence": True,
        "blocker_present": bool(r["blockers"]),
        "suspected_cause": (
            "recommendation policy / suitability-vs-action conflation (H7)"
            if r["blockers"]
            else "scoring or evidence mapping"
        ),
    })

payload = {
    "version": "3.0",
    "status": "INCOMPLETE - human labels pending",
    "engine_baseline": bench["engine_baseline"],
    "counts": {
        "cases": len(rows),
        "human_labelled": len(labelled),
        "pending_human_label": len(rows) - len(labelled),
    },
    "metrics": {
        "agreement": f"{len(agreement)}/{len(labelled)}",
        "false_skip": len(false_skip),
        "false_apply": len(false_apply),
        "severe_yes_no_disagreement": len(severe),
        "near_disagreement": len(near),
        "sample_size_sufficient_for_calibration": False,
    },
    "false_skip_cases": [r["job_id"] for r in false_skip],
    "false_apply_cases": [r["job_id"] for r in false_apply],
    "severe_disagreement_cases": [r["job_id"] for r in severe],
    "near_disagreement_cases": [r["job_id"] for r in near],
    "disagreement_analysis": analysis,
    "cases": rows,
}

OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"cases            : {payload['counts']['cases']}")
print(f"human labelled   : {len(labelled)}")
print(f"pending labels   : {payload['counts']['pending_human_label']}")
print(f"agreement        : {len(agreement)}/{len(labelled)}")
print(f"false skips      : {len(false_skip)} {payload['false_skip_cases']}")
print(f"false applies    : {len(false_apply)} {payload['false_apply_cases']}")
print(f"severe YES<->NO  : {len(severe)} {payload['severe_disagreement_cases']}")
print(f"near disagreement: {len(near)} {payload['near_disagreement_cases']}")
for a in analysis:
    print(f"\n  {a['job_id']}")
    print(f"    human : {a['human_decisive_factor']}")
    print(f"    engine: {a['engine_decisive_factor']}")
    print(f"    cause : {a['suspected_cause']}")