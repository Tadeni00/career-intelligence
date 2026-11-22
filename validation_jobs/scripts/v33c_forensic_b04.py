"""V3.3c Task A - VJ-B04 forensic audit. DIAGNOSTIC ONLY.

Reads the authoritative V3.3c run artifact. Modifies nothing. Imports the
production marker vocabularies read-only for diagnostic labelling.
"""
import collections
import hashlib
import json
import pathlib
from datetime import datetime, timezone

from app.services.normalization import normalize_text
from app.services.requirements import (
    _DOMAIN_HINTS,
    _MANDATORY_MARKERS,
    _PREFERENCE_MARKERS,
    _SOFT_HINTS,
    _ELIGIBILITY_HINTS,
    _WORK_CONDITION_HINTS,
)

RUNS = json.loads(pathlib.Path(
    "docs/benchmark/v3_3c_extraction_reproducibility_runs.json").read_text(encoding="utf-8"))
META = RUNS["run_metadata"]
POSTINGS = {j["job_id"]: j for j in json.loads(
    pathlib.Path("validation_jobs/postings/collected.json").read_text(encoding="utf-8"))}

JOB = "VJ-B04"
runs = {r["run_id"]: r for r in RUNS["runs"] if r["job_id"] == JOB}
assert sorted(runs) == [1, 2, 3], sorted(runs)

# Diagnostic-only source-context classifier. Not part of production.
MARKETING = ("we are", "we're ", "our mission", "our vision", "our values",
             "we believe", "we offer", "we celebrate", "we're proud",
             "competitive salary", "benefits", "perks", "equal opportunity",
             "diversity", "inclusion", "about us", "founded", "join our",
             "exciting", "innovative company", "next level", "world class")
NARRATIVE = ("about the company", "our story", "our history", "why join",
             "what we do", "our technology", "our products", "press",
             "news", "read more")


def source_context(source: str, name: str) -> str:
    low = normalize_text(f"{source} {name}")
    if any(m in low for m in NARRATIVE):
        return "UNRELATED_NARRATIVE"
    if any(m in low for m in MARKETING):
        return "EMPLOYER_MARKETING"
    if any(m in low for m in _PREFERENCE_MARKERS):
        return "PREFERENCE"
    if any(m in low for m in _MANDATORY_MARKERS):
        return "EXPLICIT_REQUIREMENT"
    if any(m in low for m in _SOFT_HINTS):
        return "BEHAVIORAL_EXPECTATION"
    if any(m in low for m in _ELIGIBILITY_HINTS):
        return "ELIGIBILITY"
    if any(m in low for m in _WORK_CONDITION_HINTS):
        return "WORK_CONDITION"
    if any(m in low for m in _DOMAIN_HINTS):
        return "DOMAIN_CONTEXT"
    return "AMBIGUOUS"


def quote_in_posting(quote: str, posting: str) -> bool:
    q, d = normalize_text(quote), normalize_text(posting)
    if not q:
        return False
    return q in d


posting = POSTINGS[JOB]["description"]

# ---------------------------------------------------------------- matrix
by_run = {rid: {c["name"]: c for c in runs[rid].get("canonical_requirements", [])}
          for rid in (1, 2, 3)}
all_names = sorted({n for r in by_run.values() for n in r})

rows = []
for name in all_names:
    present = {rid: (name in by_run[rid]) for rid in (1, 2, 3)}
    imps = {rid: (by_run[rid][name]["importance"] if present[rid] else None)
            for rid in (1, 2, 3)}
    srcs = {rid: (by_run[rid][name].get("source_text") or "" if present[rid] else "")
            for rid in (1, 2, 3)}
    cats = {by_run[rid][name]["category"] for rid in (1, 2, 3) if present[rid]}

    if all(present.values()):
        selection = "STABLE_ALL_RUNS"
    elif present[1] and not present[2] and not present[3]:
        selection = "RUN_1_ONLY"
    elif present[2] and not present[1] and not present[3]:
        selection = "RUN_2_ONLY"
    elif present[3] and not present[1] and not present[2]:
        selection = "RUN_3_ONLY"
    else:
        selection = "PARTIAL_PRESENCE"

    seen_imps = {imps[r] for r in (1, 2, 3) if present[r]}
    if not all(present.values()):
        classification = "NOT_APPLICABLE"
    elif len(seen_imps) > 1:
        classification = "IMPORTANCE_DRIFT"
    else:
        classification = "STABLE_IMPORTANCE"

    ctx = source_context(srcs[3] or srcs[1] or srcs[2] or "", name)
    evidence_ok = {r: (quote_in_posting(srcs[r], posting) if srcs[r] else None)
                   for r in (1, 2, 3)}

    rows.append({
        "requirement": name,
        "category": sorted(cats)[0] if len(cats) == 1 else sorted(cats),
        "run_1_present": present[1], "run_1_importance": imps[1],
        "run_1_source": srcs[1], "run_1_evidence_in_posting": evidence_ok[1],
        "run_2_present": present[2], "run_2_importance": imps[2],
        "run_2_source": srcs[2], "run_2_evidence_in_posting": evidence_ok[2],
        "run_3_present": present[3], "run_3_importance": imps[3],
        "run_3_source": srcs[3], "run_3_evidence_in_posting": evidence_ok[3],
        "selection_status": selection,
        "classification_status": classification,
        "source_context": ctx,
    })

run3_only = [r for r in rows if r["selection_status"] == "RUN_3_ONLY"]
absent_from_r3 = [r for r in rows if r["run_3_present"] is False]
present_all = [r for r in rows if r["selection_status"] == "STABLE_ALL_RUNS"]
drift = [r for r in rows if r["classification_status"] == "IMPORTANCE_DRIFT"]
ctx_counts = collections.Counter(r["source_context"] for r in run3_only)

# Diagnostic labels per unstable requirement
for r in rows:
    labels = []
    if r["selection_status"] != "STABLE_ALL_RUNS":
        if r["source_context"] in ("EMPLOYER_MARKETING", "UNRELATED_NARRATIVE"):
            labels.append("POSSIBLE_OVER_EXTRACTION")
        elif r["selection_status"] == "RUN_3_ONLY":
            labels.append("POSSIBLE_UNDER_EXTRACTION"
                          if r["source_context"] in ("EXPLICIT_REQUIREMENT",
                                                     "PREFERENCE")
                          else "AMBIGUOUS_SOURCE_LANGUAGE")
        else:
            labels.append("SELECTION_TRUE_VARIANCE")
    if r["classification_status"] == "IMPORTANCE_DRIFT":
        labels.append("CLASSIFICATION_VARIANCE")
    r["diagnostic_label"] = labels or ["STABLE"]

audit = {
    "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "job_id": JOB,
    "provenance": {
        "implementation_identifier": "dcc4f506965d57e99bf0bb54bdd1c429",
        "prompt_sha256": META["system_prompt_sha256"],
        "schema_version": META["schema_version"],
        "provider": META["provider"],
        "model": META["model"],
        "temperature": META["temperature"],
        "seed": META["seed"],
        "profile_sha256": META["profile_sha256"],
        "experiment_artifact_sha256": hashlib.sha256(
            pathlib.Path("docs/benchmark/v3_3c_extraction_reproducibility_runs.json")
            .read_bytes()).hexdigest(),
        "source_sha256": runs[1]["source_sha256"],
        "run_identifiers": [f"{JOB}:run{runs[r]['run_id']}@{runs[r]['timestamp']}"
                            for r in (1, 2, 3)],
        "payload_hashes": {str(r): runs[r].get("payload_hash") for r in (1, 2, 3)},
    },
    "run_counts": {str(r): runs[r]["canonical_requirement_count"] for r in (1, 2, 3)},
    "raw_counts": {str(r): runs[r]["raw_requirement_count"] for r in (1, 2, 3)},
    "scores": {str(r): runs[r]["score"] for r in (1, 2, 3)},
    "recommendations": {str(r): runs[r]["recommendation"] for r in (1, 2, 3)},
    "distinct_requirements_across_runs": len(all_names),
    "run_3_only_requirements": [r["requirement"] for r in run3_only],
    "absent_from_run_3": [r["requirement"] for r in absent_from_r3],
    "stable_all_runs": [r["requirement"] for r in present_all],
    "importance_drift_here": [r["requirement"] for r in drift],
    "run_3_only_source_context_counts": dict(ctx_counts),
    "matrix": rows,
    "canonical_notes": {str(r): runs[r].get("canonical_notes") or [] for r in (1, 2, 3)},
}

pathlib.Path("docs/benchmark").mkdir(parents=True, exist_ok=True)
pathlib.Path("docs/benchmark/vj_b04_forensic_audit.json").write_text(
    json.dumps(audit, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"counts run1/2/3 : {audit['run_counts']}")
print(f"distinct reqs   : {len(all_names)}")
print(f"stable all runs : {len(present_all)}")
print(f"RUN_3 ONLY ({len(run3_only)}):")
for r in run3_only:
    print(f"   - {r['requirement'][:44]:<46} imp={r['run_3_importance']:<10} "
          f"ctx={r['source_context']:<24} evid={r['run_3_evidence_in_posting']}")
print(f"ABSENT FROM RUN 3 ({len(absent_from_r3)}):")
for r in absent_from_r3:
    print(f"   - {r['requirement'][:44]:<46} run1={r['run_1_importance']} "
          f"run2={r['run_2_importance']}")
print(f"IMPORTANCE DRIFT here ({len(drift)}):")
for r in drift:
    print(f"   - {r['requirement'][:40]:<42} "
          f"{r['run_1_importance']}->{r['run_2_importance']}->{r['run_3_importance']}")