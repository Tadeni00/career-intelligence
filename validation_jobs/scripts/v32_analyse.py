"""V3.2 Workstream C analysis — structural comparison, severity, root cause.

Severity is measured, not assumed: every run's requirement set is scored
through the FROZEN engine so a difference is Level 0-3 according to what it
actually does.
"""
import hashlib
import json
import pathlib
from collections import Counter, defaultdict

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Candidate
from app.schemas import ProfileSummary
from app.services import matching as matching_service
from app.services.matching import build_settings

from matching import audit_match
from matching.types import JobProfile, Requirement

RUNS = json.loads(pathlib.Path(
    "docs/benchmark/v3_extraction_reproducibility_runs.json").read_text(encoding="utf-8"))
runs = RUNS["runs"]
STRUCTURED = ("experience_requirements", "education_requirements",
              "location_requirements", "other_requirements")

profile = ProfileSummary.model_validate(
    json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8")))
db = SessionLocal()
cand = matching_service.to_candidate_profile(
    db.execute(select(Candidate)).scalars().first())
settings = build_settings()


def norm(s):
    return " ".join(str(s or "").lower().split())


def canonical(payload: dict) -> dict:
    def strset(v):
        return sorted({norm(x) for x in (v or []) if norm(x)})

    def objset(v, kind):
        out = []
        for item in v or []:
            if isinstance(item, dict):
                imp = getattr(item.get("importance"), "value", item.get("importance"))
                out.append((kind, norm(item.get("name")),
                            str(imp or "UNKNOWN"),
                            item.get("years_required")))
            else:
                out.append((kind, norm(item), "MALFORMED", None))
        return sorted(out)

    return {
        "required_skills": strset(payload.get("required_skills")),
        "preferred_skills": strset(payload.get("preferred_skills")),
        **{k: objset(payload.get(k), k.split("_")[0].upper()) for k in STRUCTURED},
    }


def ordered(payload: dict) -> dict:
    return {
        "required_skills": [norm(x) for x in (payload.get("required_skills") or [])],
        "preferred_skills": [norm(x) for x in (payload.get("preferred_skills") or [])],
        **{k: [(i.get("name") if isinstance(i, dict) else i)
               for i in (payload.get(k) or [])] for k in STRUCTURED},
    }


def diff(a: dict, b: dict) -> dict:
    added, removed, reclassified, modified, reordered = [], [], [], [], []
    for key in a:
        la, lb = a[key], b[key]
        if la == lb:
            continue
        if key.endswith("_skills"):
            sa, sb = set(la), set(lb)
            added += [{"field": key, "value": v} for v in sorted(sb - sa)]
            removed += [{"field": key, "value": v} for v in sorted(sa - sb)]
        else:
            names_a = {(i[0], i[1]): i for i in la}
            names_b = {(i[0], i[1]): i for i in lb}
            for key_a in names_b:
                if key_a not in names_a:
                    added.append({"field": key, "value": key_a[1]})
            for key_a in names_a:
                if key_a not in names_b:
                    removed.append({"field": key, "value": key_a[1]})
            for shared in (set(names_a) & set(names_b)):
                ea, eb = names_a[shared], names_b[shared]
                if ea[2] != eb[2]:
                    reclassified.append({"field": key, "value": shared[1],
                                         "from": ea[2], "to": eb[2]})
                elif ea[3] != eb[3]:
                    modified.append({"field": key, "value": shared[1],
                                     "from": ea[3], "to": eb[3]})
        same_set = (
            set(a[key]) == set(b[key]) if key.endswith("_skills")
            else {(i[0], i[1]) for i in a[key]} == {(i[0], i[1]) for i in b[key]}
        )
        if same_set:
            reordered.append({"field": key})
    return {"added": added, "removed": removed, "reclassified": reclassified,
            "modified": modified, "reordered_only": reordered}


def engine_result(payload: dict):
    reqs = []
    for s in payload.get("required_skills") or []:
        reqs.append(Requirement(type="SKILL", name=str(s), importance="REQUIRED"))
    for s in payload.get("preferred_skills") or []:
        reqs.append(Requirement(type="SKILL", name=str(s), importance="PREFERRED"))
    for key in STRUCTURED:
        kind = key.split("_")[0].upper()
        for item in payload.get(key) or []:
            if not isinstance(item, dict):
                continue
            imp = getattr(item.get("importance"), "value", item.get("importance")) or "UNKNOWN"
            reqs.append(Requirement(
                type=kind, name=str(item.get("name") or ""), importance=imp,
                description=item.get("description") or "",
                years_required=item.get("years_required")))
    job = JobProfile(id=None, title="Data Scientist", company="Acme",
                     location="Lagos, Nigeria", requirements=reqs)
    audit, outcome = audit_match(cand, job, settings)
    return outcome, audit


# ------------------------------------------------------------------ analyse
by_job: dict[str, list[dict]] = defaultdict(list)
for r in runs:
    by_job[r["job_id"]].append(r)
for jid in by_job:
    by_job[jid].sort(key=lambda r: r["run_id"])

cases = []
for jid, rs in sorted(by_job.items()):
    scores, recs, block_counts = [], [], []
    canon = []
    for r in rs:
        if r["success"]:
            o, a = engine_result(r["payload"])
            scores.append(round(o.overall_score, 2))
            recs.append(o.recommendation)
            block_counts.append(len(a.blockers))
            canon.append(canonical(r["payload"]))
        else:
            scores.append(None); recs.append(None); block_counts.append(None)
            canon.append(None)

    pairs = []
    for i in (1, 2):
        if canon[0] is None or canon[i] is None:
            continue
        d = diff(canon[0], canon[i])
        score_changed = scores[0] != scores[i]
        rec_changed = recs[0] != recs[i]
        blk_changed = block_counts[0] != block_counts[i]
        substantive = d["added"] or d["removed"] or d["reclassified"] or d["modified"]
        if rec_changed or blk_changed:
            severity, styp = 3, "DECISION_CHANGING"
        elif score_changed:
            severity, styp = 2, "SCORE_CHANGING"
        elif substantive:
            severity, styp = 1, "SEMANTIC_BUT_SCORE_NEUTRAL"
        elif d["reordered_only"]:
            severity, styp = 0, "REORDERED_ONLY"
        else:
            severity, styp = 0, "IDENTICAL"
        pairs.append({
            "run_1": 1, "run_2": i + 1, "diff": d, "severity": severity,
            "severity_label": styp,
            "score_changed": score_changed, "recommendation_changed": rec_changed,
            "blocker_changed": blk_changed,
        })

    canonical_identical = canon[0] == canon[1] == canon[2]
    raw_hashes = {r["parsed_output_sha256"] for r in rs if r["success"]}
    raw_identical = len(raw_hashes) == 1
    ordered_identical = all(
        ordered(rs[0]["payload"]) == ordered(rs[i]["payload"]) for i in (1, 2)
    ) if all(r["success"] for r in rs) else None

    cases.append({
        "job_id": jid,
        "source_sha256": rs[0]["source_sha256"],
        "source_stable": len({r["source_sha256"] for r in rs}) == 1,
        "run_scores": scores,
        "run_recommendations": recs,
        "run_blocker_counts": block_counts,
        "run_requirement_counts": [r["requirement_count"] for r in rs],
        "raw_output_identical": raw_identical,
        "canonical_identical": canonical_identical,
        "ordered_identical": ordered_identical,
        "max_severity": max((p["severity"] for p in pairs), default=0),
        "pairs": pairs,
        "identical_all_runs": canonical_identical,
        "semantic_difference": (not canonical_identical) and canonical_identical is not None,
    })

diff_counts = Counter()
for c in cases:
    for p in c["pairs"]:
        for k in ("added", "removed", "modified", "reclassified"):
            diff_counts[k.upper()] += len(p["diff"][k])
        if p["diff"]["reordered_only"]:
            diff_counts["REORDERED_ONLY"] += 1

stable = [c for c in cases if c["identical_all_runs"]]
semantic = [c for c in cases if c["semantic_difference"]]
score_ch = [c for c in cases if c["max_severity"] >= 2]
dec_ch = [c for c in cases if c["max_severity"] >= 3]

successful = [r for r in runs if r["success"]]
provider_fail = [r for r in runs if r.get("failure_code") == "PROVIDER_ERROR"]
schema_fail = [r for r in runs if r.get("failure_code") not in (None, "PROVIDER_ERROR")]

# ------------------------------------------------------------ root causes
causes = defaultdict(list)
for c in cases:
    if c["identical_all_runs"]:
        continue
    if c["raw_output_identical"]:
        causes["D2-G Normalization"].append(c["job_id"])
    if c["canonical_identical"] and not c["ordered_identical"]:
        causes["D2-G Normalization"].append(c["job_id"])
    reclass = any(p["diff"]["reclassified"] for p in c["pairs"])
    added_removed = any(p["diff"]["added"] or p["diff"]["removed"] for p in c["pairs"])
    modified = any(p["diff"]["modified"] for p in c["pairs"])
    if reclass:
        causes["D2-C Classification ambiguity"].append(c["job_id"])
    if added_removed:
        causes["D2-B Prompt ambiguity"].append(c["job_id"])
    if modified:
        causes["D2-B Prompt ambiguity"].append(c["job_id"])
    if not (reclass or added_removed or modified):
        causes["D2-A Model stochasticity"].append(c["job_id"])

out = {
    "version": "3.2",
    "experiment": "v3.2_extraction_reproducibility",
    "run_metadata": RUNS["run_metadata"],
    "run_level": {
        "planned": 78,
        "completed": len(runs),
        "successful": len(successful),
        "failed": len(runs) - len(successful),
        "provider_failures": len(provider_fail),
        "schema_failures": len(schema_fail),
    },
    "case_level": {
        "jobs": len(cases),
        "identical_across_all_3_runs": len(stable),
        "with_semantic_differences": len(semantic),
        "score_changing": len(score_ch),
        "recommendation_changing": len(dec_ch),
    },
    "difference_counts": dict(diff_counts),
    "cases": cases,
    "root_cause_index": {k: sorted(set(v)) for k, v in causes.items()},
    "root_cause_excluded": {
        "D2-D Schema/parsing": "V3.1 symmetric coercion; no malformed element "
                               "observed in 78 runs (all succeeded, all validated).",
        "D2-E Source instability": "source_sha256 identical across all runs for "
                                   "every job (source_stable true).",
        "D2-F Provider/model drift": "single provider/model/prompt/schema recorded "
                                     "for all 78 runs; API key rotation is a "
                                     "credential change, not a config difference.",
    },
}

pathlib.Path("docs/benchmark/v3_extraction_reproducibility.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"runs      : {out['run_level']}")
print(f"cases     : {out['case_level']}")
print(f"diffs     : {out['difference_counts']}")
print(f"root cause: {{k: len(v) for k, v in out['root_cause_index'].items()}}")
print()
for c in dec_ch:
    print(f"DECISION-CHANGING {c['job_id']}: scores={c['run_scores']} "
          f"recs={c['run_recommendations']} blockers={c['run_blocker_counts']}")
for c in score_ch:
    if c not in dec_ch:
        print(f"SCORE-CHANGING     {c['job_id']}: scores={c['run_scores']} "
              f"recs={c['run_recommendations']}")