"""V3 Phase 1 — diagnostic audit of the matching engine.

Recomputes every benchmark job with the *current* engine so the baseline is
reproducible, then decomposes the score to requirement level.

Produces: validation_jobs/_v3_phase1_audit.txt
"""
import json
import pathlib

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Candidate, Job, MatchResult
from app.schemas import ProfileSummary
from app.services import matching as matching_service
from app.services.candidate import to_profile_summary
from app.services.matching import build_settings

from matching import audit_match, state_counts

HUMAN = {
    "VJ-01": "MAYBE", "VJ-02": "NO", "VJ-03": "YES",
}
JOB_KEY = {
    "VJ-01": ("Data Scientist", "Monzo"),
    "VJ-02": ("Machine Learning Engineer II (Underwriting ML)", "Affirm"),
    "VJ-03": ("Data Analyst", "SEAhub Asia"),
}

profile_json = json.loads(
    pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8")
)
profile = ProfileSummary.model_validate(profile_json)

db = SessionLocal()
candidate = db.execute(select(Candidate)).scalars().first()
cand_profile = matching_service.to_candidate_profile(candidate)
settings = build_settings()

out = []
w = out.append

w("# V3 Phase 1 — Diagnostic Audit of the Matching Engine")
w("")
w("Source of truth: packages/matching/matching/{engine,config,normalize}.py")
w("Baseline weights and thresholds are UNCHANGED by this phase.")
w("")
w("## Frozen baseline configuration")
w("")
w(f"  technical weight    : {settings.weights.technical}")
w(f"  experience weight   : {settings.weights.experience}")
w(f"  education weight    : {settings.weights.education}")
w(f"  location weight     : {settings.weights.location}")
w(f"  other weight        : {settings.weights.other}")
w(f"  APPLY threshold     : {settings.policy.apply_threshold}")
w(f"  APPLY_WITH_TAILORING: {settings.policy.apply_with_tailoring_threshold}")
w(f"  STRETCH threshold   : {settings.policy.stretch_threshold}")
w(f"  partial skill credit: {settings.partial_skill_credit}")
w(f"  unknown-req score   : {settings.unknown_requirement_score}")
w("")
w("## Importance weights (engine._importance_weight)")
w("  REQUIRED=1.00  PREFERRED=0.45  SOFT_SIGNAL/INFORMATIONAL=0.05  UNKNOWN=0.65")
w("")

for key, (title, company) in JOB_KEY.items():
    job = db.query(Job).filter(Job.title == title, Job.company == company).first()
    if job is None:
        w(f"===== {key} NOT FOUND in dev DB")
        continue

    job_profile = matching_service.to_job_profile(job)
    audit, outcome = audit_match(cand_profile, job_profile, settings)

    stored = (
        db.query(MatchResult)
        .filter(MatchResult.job_id == job.id)
        .order_by(MatchResult.id.desc())
        .first()
    )

    w(f"===== {key}  {title} @ {company}")
    w(f"  human baseline        : {HUMAN[key]}")
    if stored:
        w(f"  stored (historical)   : {stored.recommendation} "
          f"score={stored.overall_score:.1f}")
    w(f"  RECOMPUTED current    : {audit.recommendation} "
      f"score={audit.overall_score:.1f}")
    w(f"  audit verified        : {audit.verified} "
      f"(reconstructed {audit.reconstructed_overall:.4f})")
    w(f"  confidence            : {audit.confidence}")
    w("")
    w("  component decomposition:")
    w(f"    {'dimension':<12}{'score':>8}{'weight':>9}{'contribution':>14}")
    for d in audit.dimensions:
        w(f"    {d.name:<12}{d.engine_score:>8.1f}{d.weight:>9.2f}"
          f"{d.weighted_contribution:>14.2f}")
    w(f"    {'TOTAL':<12}{'':>8}{'':>9}{audit.reconstructed_overall:>14.2f}")
    w("")

    counts = state_counts(audit)
    w(f"  diagnostic states: {counts}")
    w("")

    for d in audit.dimensions:
        if not d.items and not d.fixed_components:
            continue
        w(f"  --- {d.name} requirements")
        for fixed in d.fixed_components:
            w(f"      [fixed] {fixed}")
        for it in d.items:
            flag = " BLOCKER" if it.blocker else ""
            w(f"      {it.state:<26} {it.requirement[:44]:<44} "
              f"imp={it.importance:<11} contrib={it.contribution:.3f} "
              f"pen={it.penalty:.3f}{flag}")
            if it.evidence_used:
                w(f"          evidence: {', '.join(it.evidence_used[:3])}")
            if it.evidence_state not in ("exact", "alias/normalised", "years on record"):
                w(f"          evidence_state: {it.evidence_state}")
            if it.note:
                w(f"          note: {it.note}")
            if it.blocker_source:
                w(f"          BLOCKER SOURCE: {it.blocker_source}")
    w("")

    w("  requirements extracted from the posting:")
    for r in job.requirements:
        w(f"      {r.requirement_type:<11}{r.importance:<11}{r.name[:60]}")
    w("")

w("=" * 70)
w("## Cross-job blocker provenance")
w("Blockers in this engine originate from exactly two code paths:")
w("  1. engine._score_education — REQUIRED education requirement whose degree")
w("     level exceeds the candidate's highest recorded level.")
w("  2. engine._score_location  — a REQUIRED location requirement containing")
w("     must/required/based in/relocat, when candidate and job locations differ.")
w("_score_technical and _score_other NEVER emit blockers: a missing required")
w("skill is recorded as a gap only.")

text = "\n".join(out)
pathlib.Path("validation_jobs/_v3_phase1_audit.txt").write_text(text, encoding="utf-8")
print(text)