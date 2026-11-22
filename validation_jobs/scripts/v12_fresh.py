"""Fresh provider validation (spec section 25): new LLM generations against the
live provider, verified end to end. Distinct from revalidating captured output.
"""
import json, pathlib
from pathlib import Path

import httpx

from app.schemas import ProfileSummary
from app.services.validation import validate_cover_letter, validate_tailored_cv
from app.services.generation import generate_cover_letter, generate_tailored_cv
from app.db.session import SessionLocal
from app.models import Job
from sqlalchemy import select

prof = json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8"))
profile = ProfileSummary.model_validate(prof)
job_meta = json.loads(pathlib.Path("validation_jobs/VJ-03_job3.json").read_text(encoding="utf-8"))

db = SessionLocal()
job = db.execute(select(Job).where(Job.url == job_meta["source_url"])).scalars().first()
if job is None:
    job = Job(title=job_meta["title"], company=job_meta["company"],
              location=job_meta["location"], url=job_meta["source_url"],
              description=job_meta["description"])
    db.add(job); db.commit(); db.refresh(job)

out = [f"FRESH PROVIDER VALIDATION - {job.title} @ {job.company}", "=" * 66]

from app.models import Candidate
cand = db.execute(select(Candidate)).scalars().first()
rec = generate_tailored_cv(db, cand, job, profile)
iss = json.loads(rec.validation_issues or "[]")
out.append(f"TAILORED CV  status={rec.validation_status}  issues={len(iss)}")
for i in iss[:8]:
    out.append(f"   [{i['severity']}/{i.get('claim_severity','-')}] {i['code']}: {i['message'][:88]}")

cl = generate_cover_letter(db, cand, job, profile)
ciss = json.loads(cl.validation_issues or "[]")
out.append(f"COVER LETTER status={cl.validation_status}  issues={len(ciss)}")
for i in ciss[:10]:
    out.append(f"   [{i['severity']}/{i.get('claim_severity','-')}] {i['code']}: {i['message'][:88]}")

text = cl.content
markers = ["BRIGHTEST", "#RMTM", "137.255.177.157"]
hits = [m for m in markers if m in text]
out.append(f"injected payload present in fresh letter: {hits if hits else 'NONE'}")
out.append(f"safety findings on fresh letter: "
           f"{[i['code'] for i in ciss if i['code'] in ('SUSPICIOUS_OUTPUT','UNSUPPORTED_CONTACT','UNSUPPORTED_ELIGIBILITY')] or 'none'}")
out.append(f"fresh document reached VALID: {cl.validation_status == 'VALID'}")
pathlib.Path("validation_jobs/_v12_fresh.txt").write_text("\n".join(out), encoding="utf-8")
Path("validation_jobs/VJ-03_fresh_coverletter.txt").write_text(text, encoding="utf-8")
print("\n".join(out))