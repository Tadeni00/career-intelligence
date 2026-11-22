"""V3 Phase 2/3 — build the machine-readable benchmark and run the audit.

Postings are real (see validation_jobs/postings/collected.json). Requirements are
extracted with the SAME extractor the product uses, so the diagnostic reflects
production behaviour rather than a curated ideal.

Human decision labels are NOT generated here. The three frozen jobs carry the
labels recorded before V3; new jobs carry null and await an independent human
reviewer (spec section 10, Gate D).
"""
import json
import pathlib
import re

from sqlalchemy import select

from app.ai import get_ai_provider
from app.db.session import SessionLocal
from app.models import Candidate, Job
from app.schemas import ProfileSummary
from app.services import matching as matching_service
from app.services.candidate import to_profile_summary
from app.services.matching import build_settings
from app.services.normalization import canonical_tech

from matching import audit_match, state_counts
from matching.types import JobProfile, Requirement

FROZEN = {
    "VJ-01": {"title": "Data Scientist", "company": "Monzo",
              "human": "MAYBE", "blocker": False,
              "reason": "Strong technical and experience match, but the role is "
                        "restricted to UK-based candidates and the candidate is "
                        "in Lagos."},
    "VJ-02": {"title": "Machine Learning Engineer II (Underwriting ML)",
              "company": "Affirm", "human": "NO", "blocker": False,
              "reason": "Remote (US) only, and the candidate lacks the core ML "
                        "stack the role is built around."},
    "VJ-03": {"title": "Data Analyst", "company": "SEAhub Asia",
              "human": "YES", "blocker": False,
              "reason": "Directly aligned with the candidate's confirmed data "
                        "analysis experience; tooling gap is manageable."},
}

profile = ProfileSummary.model_validate(
    json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8"))
)
db = SessionLocal()
candidate = db.execute(select(Candidate)).scalars().first()
cand_profile = matching_service.to_candidate_profile(candidate)
settings = build_settings()
provider = get_ai_provider()

collected = json.loads(
    pathlib.Path("validation_jobs/postings/collected.json").read_text(encoding="utf-8")
)

# Cap near-duplicate employers so one company's ladder does not dominate.
per_company: dict[str, int] = {}
selected = []
for job in collected:
    key = job["company"].lower()
    if per_company.get(key, 0) >= 2:
        continue
    per_company[key] = per_company.get(key, 0) + 1
    selected.append(job)


def classify_remote(location: str, explicit: bool) -> str:
    low = (location or "").lower()
    if explicit:
        return "REMOTE"
    if "hybrid" in low:
        return "HYBRID"
    if any(w in low for w in ("remote", "anywhere", "worldwide", "americas",
                              "europe", "emea", "latam", "global")):
        return "HYBRID"
    return "ONSITE"


def build_case(job_id, title, company, location, remote, description,
               salary_min, salary_max, human=None, blocker=False, reason=None):
    job_profile = JobProfile(
        id=None, title=title, company=company, location=location,
        remote_status=remote, description=description,
        salary_min=salary_min, salary_max=salary_max,
    )
    extracted = provider.extract_job_requirements(description)
    reqs: list[Requirement] = []
    for r in extracted.required_skills:
        reqs.append(Requirement(type="SKILL", name=r,
                                importance="REQUIRED", description=""))
    for r in extracted.preferred_skills:
        reqs.append(Requirement(type="SKILL", name=r,
                                importance="PREFERRED", description=""))
    for attr, rtype in (
        ("experience_requirements", "EXPERIENCE"),
        ("education_requirements", "EDUCATION"),
        ("location_requirements", "LOCATION"),
        ("other_requirements", "OTHER"),
    ):
        for r in getattr(extracted, attr, []):
            reqs.append(Requirement(
                type=rtype, name=r.name,
                importance=getattr(r.importance, "value", r.importance),
                description=r.description or "",
                years_required=r.years_required))
    job_profile.requirements = reqs

    audit, outcome = audit_match(cand_profile, job_profile, settings)
    counts = state_counts(audit)
    req_total = len(reqs)
    required = [r for r in reqs if r.importance == "REQUIRED"]
    preferred = [r for r in reqs if r.importance == "PREFERRED"]
    covered = {
        i.requirement for d in audit.dimensions for i in d.items
        if i.state == "F_SUPPORTED"
    }
    return {
        "job_id": job_id,
        "title": title,
        "company": company,
        "location": location,
        "remote_status": remote,
        "source_url": description_url if False else None,
        "human_decision": human,
        "human_reason": reason,
        "material_strengths": [],
        "material_concerns": [],
        "hard_blocker": blocker,
        "requirements_extracted": req_total,
        "required_requirements": len(required),
        "preferred_requirements": len(preferred),
        "system": {
            "recommendation": outcome.recommendation,
            "overall_score": round(outcome.overall_score, 2),
            "technical": round(outcome.technical_score, 2),
            "experience": round(outcome.experience_score, 2),
            "education": round(outcome.education_score, 2),
            "location": round(outcome.location_score, 2),
            "other": round(outcome.other_score, 2),
            "confidence": outcome.confidence,
            "blockers": [b.requirement for b in audit.blockers],
            "blocker_sources": sorted({b.blocker_source for b in audit.blockers}),
            "diagnostic_states": counts,
            "required_coverage": (
                round(
                    sum(1 for r in required
                        if canonical_tech(r.name) and r.name in covered)
                    / len(required), 3
                ) if required else None
            ),
            "preferred_coverage": (
                round(
                    sum(1 for r in preferred
                        if canonical_tech(r.name) and r.name in covered)
                    / len(preferred), 3
                ) if preferred else None
            ),
            "audit_verified": audit.verified,
        },
        "requirements": [
            {"name": r.name, "type": r.type, "importance": r.importance,
             "years_required": r.years_required,
             "description": r.description or ""}
            for r in reqs
        ],
    }


cases = []

# --- frozen regression cases (human labels recorded before V3) -------------
for jid, meta in FROZEN.items():
    job = db.query(Job).filter(
        Job.title == meta["title"], Job.company == meta["company"]).first()
    if job is None:
        continue
    jp = matching_service.to_job_profile(job)
    audit, outcome = audit_match(cand_profile, jp, settings)
    counts = state_counts(audit)
    required = [r for r in jp.requirements if r.importance == "REQUIRED"]
    preferred = [r for r in jp.requirements if r.importance == "PREFERRED"]
    covered = {
        i.requirement for d in audit.dimensions for i in d.items
        if i.state == "F_SUPPORTED"
    }
    cases.append({
        "job_id": jid, "title": meta["title"], "company": meta["company"],
        "location": job.location, "remote_status": job.remote_status,
        "source_url": job.url, "frozen_regression_case": True,
        "human_decision": meta["human"], "human_reason": meta["reason"],
        "material_strengths": [], "material_concerns": [],
        "hard_blocker": meta["blocker"],
        "requirements_extracted": len(jp.requirements),
        "required_requirements": len(required),
        "preferred_requirements": len(preferred),
        "system": {
            "recommendation": outcome.recommendation,
            "overall_score": round(outcome.overall_score, 2),
            "technical": round(outcome.technical_score, 2),
            "experience": round(outcome.experience_score, 2),
            "education": round(outcome.education_score, 2),
            "location": round(outcome.location_score, 2),
            "other": round(outcome.other_score, 2),
            "confidence": outcome.confidence,
            "blockers": [b.requirement for b in audit.blockers],
            "blocker_sources": sorted({b.blocker_source for b in audit.blockers}),
            "diagnostic_states": counts,
            "required_coverage": (
                round(sum(1 for r in required if r.name in covered) / len(required), 3)
                if required else None),
            "preferred_coverage": (
                round(sum(1 for r in preferred if r.name in covered) / len(preferred), 3)
                if preferred else None),
            "audit_verified": audit.verified,
        },
        "requirements": [
            {"name": r.name, "type": r.type, "importance": r.importance,
             "years_required": r.years_required,
             "description": r.description or ""}
            for r in jp.requirements
        ],
    })

# --- expanded real-posting cases (human labels pending) ------------------
for job in selected:
    case = build_case(
        job["job_id"], job["title"], job["company"], job["location"],
        classify_remote(job["location"], job.get("remote", False)),
        job["description"], job.get("salary_min"), job.get("salary_max"),
    )
    case["source"] = job["source"]
    case["source_url"] = job["url"]
    case["frozen_regression_case"] = False
    cases.append(case)

out = {
    "version": "3.0",
    "description": (
        "V3 matching benchmark. 3 frozen regression cases with human labels "
        "recorded before V3, plus real job postings collected from public job "
        "boards. Human decision labels for the expanded set are PENDING: they "
        "must be supplied by an independent human reviewer before any "
        "calibration is justified (spec section 10, Gate D)."
    ),
    "candidate_profile": "val_profile_fixed.json (unchanged since V1)",
    "engine_baseline": {
        "weights": {"technical": 0.40, "experience": 0.25, "education": 0.10,
                    "location": 0.10, "other": 0.15},
        "thresholds": {"apply": 80.0, "apply_with_tailoring": 65.0,
                       "stretch": 50.0},
    },
    "counts": {
        "total": len(cases),
        "human_labelled": sum(1 for c in cases if c["human_decision"]),
        "pending_human_label": sum(1 for c in cases if not c["human_decision"]),
    },
    "cases": cases,
}

pathlib.Path("docs/benchmark").mkdir(parents=True, exist_ok=True)
pathlib.Path("docs/benchmark/matching_benchmark_v3.json").write_text(
    json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"cases: {out['counts']}")
print(f"all audits verified: {all(c['system']['audit_verified'] for c in cases)}")
blocked = [c for c in cases if c["system"]["blockers"]]
print(f"cases with blockers: {len(blocked)}")
recs: dict[str, int] = {}
for c in cases:
    recs[c["system"]["recommendation"]] = recs.get(c["system"]["recommendation"], 0) + 1
print("recommendation distribution:", recs)