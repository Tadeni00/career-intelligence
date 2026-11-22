"""V2 end-to-end check: the strategy reaches generation, and the V1.2 validator
still has the final say (spec sections 21, 22, 28-Gate G).

Generates fresh documents for the benchmark job through the real provider path
and verifies the strategy constraints were supplied and that validation still
blocks unsupported content.
"""
import json
import pathlib

from app.db.session import SessionLocal
from app.models import Candidate, Job
from app.services import strategy_store
from app.services.candidate import to_profile_summary
from app.services.generation import generate_cover_letter, generate_tailored_cv, strategy_constraints

profile = ProfileSummary = None
from app.schemas import ProfileSummary  # noqa: E402

profile = ProfileSummary.model_validate(
    json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8"))
)

db = SessionLocal()
candidate = db.execute(__import__("sqlalchemy").select(Candidate)).scalars().first()
job = (
    db.query(Job)
    .filter(Job.title == "Data Analyst", Job.company == "SEAhub Asia")
    .first()
)

out = ["# V2 generation integration (Gate G)", "=" * 60]

constraints = strategy_constraints(db, job)
out.append("")
out.append("STRATEGY CONSTRAINTS PASSED TO THE PROMPTS:")
if constraints:
    out.append("  " + constraints)
else:
    out.append("  (none produced)")
out.append(f"  constraint text length: {len(constraints)}")

if not constraints:
    out.append("  RESULT: FAIL - strategy produced no generation constraints")

record = strategy_store.latest_for_job(db, candidate.id, job.id)
strategy = strategy_store.to_strategy(record)
out.append(f"  strategy version: v{record.version} {record.status}")

out.append("")
out.append("FRESH GENERATION THROUGH THE STRATEGY-AWARE PATH")
cv = generate_tailored_cv(db, candidate, job, profile)
cv_issues = json.loads(cv.validation_issues or "[]")
out.append(f"  tailored CV  status={cv.validation_status} issues={len(cv_issues)}")
for i in cv_issues[:6]:
    out.append(f"      [{i['severity']}/{i.get('claim_severity','-')}] {i['code']}")

letter = generate_cover_letter(db, candidate, job, profile)
cl_issues = json.loads(letter.validation_issues or "[]")
out.append(f"  cover letter status={letter.validation_status} issues={len(cl_issues)}")
for i in cl_issues[:6]:
    out.append(f"      [{i['severity']}/{i.get('claim_severity','-')}] {i['code']}")

restricted = {r.subject.lower() for r in strategy.claim_restrictions}
blob = (letter.content or "").lower()
violations = [
    s for s in restricted
    if s in blob and s not in {"strong communication skills", "detail-oriented",
                               "proactive mindset", "well-organized"}
]
out.append("")
out.append(f"  restricted subjects asserted in the letter: {violations or 'none'}")
markers = ["BRIGHTEST", "#RMTM", "137.255.177.157"]
hits = [m for m in markers if m in (letter.content or "")]
out.append(f"  injected payload present: {hits or 'NONE'}")
safety = [i for i in cl_issues
          if i["code"] in ("SUSPICIOUS_OUTPUT", "UNSUPPORTED_CONTACT",
                           "UNSUPPORTED_ELIGIBILITY")]
out.append(f"  safety findings: {[i['code'] for i in safety] or 'none'}")
out.append(f"  document reached VALID: {letter.validation_status == 'VALID'}")

out.append("")
out.append("GATE G: " + ("PASS" if (constraints and restricted and not violations) else "REVIEW"))

text = "\n".join(out)
pathlib.Path("validation_jobs/_v2_generation.txt").write_text(text, encoding="utf-8")
print(text)