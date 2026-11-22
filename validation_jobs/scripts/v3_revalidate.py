"""V3 Phase 5 — revalidate the benchmark from FROZEN inputs.

The expanded benchmark's requirements are frozen in the artifact so the run is
reproducible. Requirement extraction is LLM-driven and was found to vary between
runs (20/26 cases differed, 5/26 flipped recommendation); re-extracting would
make every measurement meaningless. The artifact is therefore the source of
truth for job-side inputs, and this runner recomputes the engine result from it.
"""
import json
import pathlib

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Candidate
from app.schemas import ProfileSummary
from app.services import matching as matching_service
from app.services.matching import build_settings

from matching import audit_match, state_counts
from matching.types import JobProfile, Requirement

ARTIFACT = pathlib.Path("docs/benchmark/matching_benchmark_v3.json")
data = json.loads(ARTIFACT.read_text(encoding="utf-8"))
profile = ProfileSummary.model_validate(
    json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8"))
)
db = SessionLocal()
candidate = db.execute(select(Candidate)).scalars().first()
cand_profile = matching_service.to_candidate_profile(candidate)
settings = build_settings()

out = ["# V3 Phase 5 — Revalidation from frozen inputs", ""]
out.append("Requirement extraction is LLM-driven and non-reproducible; the")
out.append("artifact's frozen requirement lists are used as the job-side input.")
out.append("")
out.append("| Job | Frozen rec | Rerun rec | Frozen score | Rerun score | Match | Audit |")
out.append("|---|---|---|---:|---:|---|---|")

mismatches = 0
unverified = 0
rows = []
for case in data["cases"]:
    reqs = [
        Requirement(
            type=r["type"], name=r["name"], importance=r["importance"],
            description=r.get("description", ""),
            years_required=r.get("years_required"),
        )
        for r in case["requirements"]
    ]
    job = JobProfile(
        id=None, title=case["title"], company=case["company"],
        location=case.get("location") or "", remote_status=case.get("remote_status") or "",
        description="", requirements=reqs,
    )
    audit, outcome = audit_match(cand_profile, job, settings)
    same_rec = outcome.recommendation == case["system"]["recommendation"]
    # The artifact stores scores rounded to 2dp; compare at that precision.
    same_score = abs(outcome.overall_score
                     - case["system"]["overall_score"]) < 0.01
    ok = same_rec and same_score and audit.verified
    if not ok:
        mismatches += 1
    if not audit.verified:
        unverified += 1
    rows.append((case["job_id"], outcome.recommendation, outcome.overall_score,
                 audit.verified))
    out.append(
        f"| {case['job_id']} | {case['system']['recommendation']} "
        f"| {outcome.recommendation} | {case['system']['overall_score']:.1f} "
        f"| {outcome.overall_score:.1f} | {'yes' if ok else 'NO'} "
        f"| {'verified' if audit.verified else 'UNVERIFIED'} |"
    )

recs: dict[str, int] = {}
for _jid, rec, _score, _v in rows:
    recs[rec] = recs.get(rec, 0) + 1

out.append("")
out.append(f"- cases: {len(rows)}")
out.append(f"- recommendation + score reproduced from frozen inputs: "
           f"{len(rows) - mismatches}/{len(rows)}")
out.append(f"- audits verified (score fully decomposed): {len(rows) - unverified}/{len(rows)}")
out.append(f"- recommendation distribution: {recs}")

out += ["", "## Decision metrics (human-labelled subset only)", ""]


def norm(rec: str) -> str:
    return {"APPLY": "YES", "APPLY_WITH_TAILORING": "YES",
            "STRETCH": "MAYBE", "SKIP": "NO"}[rec]


agree = false_skip = false_apply = severe = near = 0
for case in data["cases"]:
    if not case["human_decision"]:
        continue
    sys_dec = next(r for jid, r, _s, _v in rows if jid == case["job_id"])
    hum = case["human_decision"]
    out.append(f"- {case['job_id']}: human {hum} / system {sys_dec} "
               f"({'agreement' if norm(sys_dec) == hum else 'DISAGREEMENT'})")
    if norm(sys_dec) == hum:
        agree += 1
    elif {norm(sys_dec), hum} == {"YES", "NO"}:
        severe += 1
    else:
        near += 1
    if sys_dec == "SKIP" and hum == "YES":
        false_skip += 1
    if sys_dec in ("APPLY", "APPLY_WITH_TAILORING") and hum == "NO":
        false_apply += 1

out += ["",
        f"- exact agreement: {agree}/3",
        f"- false skips: {false_skip}",
        f"- false applies: {false_apply}",
        f"- severe (YES<->NO): {severe}",
        f"- near (MAYBE<->): {near}",
        "- sample size 3: insufficient for any calibration decision"]

text = "\n".join(out)
pathlib.Path("validation_jobs/_v3_revalidation.txt").write_text(text, encoding="utf-8")
print(text)