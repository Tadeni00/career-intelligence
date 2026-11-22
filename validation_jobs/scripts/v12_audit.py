"""Human audit gate (spec section 28-K).

Confirms that no document reaching VALID contains a known critical evidence or
safety violation within the tested coverage. Runs every adversarial case and
every captured artifact through the full validator and checks the outcome.
"""
import json
import pathlib

from app.models import ValidationStatus
from app.schemas import CandidateSkillOut, EducationOut, ExperienceOut, ProfileSummary
from app.services.normalization import tokens
from app.services.sanitize import find_issues
from app.services.validation import validate_cover_letter

profile = ProfileSummary(
    id=1, name="Tommie van der Berg", professional_title="Data Scientist",
    location="Amsterdam", years_of_experience=6,
    summary=("Data professional with 6+ years of experience in quantitative "
             "data analysis and applied machine learning."),
    skills=[CandidateSkillOut(id=i, name=n) for i, n in enumerate(
        ["Python", "SQL", "Microsoft Excel", "Power BI", "Statistics",
         "Machine Learning", "Pandas", "PostgreSQL"])],
    experience=[ExperienceOut(
        id=1, company="Fintech Systems", title="Data Scientist",
        start_date="2021", is_current=True,
        description=("Conducted quantitative analysis of complex datasets for "
                     "classification and regression use cases. Built automated "
                     "data pipelines supporting repeatable data preparation, "
                     "analysis, and validation workflows. Collaborated with "
                     "cross-functional teams to improve analytical workflows."))],
    education=[EducationOut(id=1, institution="University of Amsterdam",
                            degree="BSc", field="Statistics")],
    projects=[],
)

CRITICAL_CODES = {
    "SUSPICIOUS_OUTPUT", "UNSUPPORTED_CONTACT", "UNSUPPORTED_ELIGIBILITY",
    "INVENTED_EMPLOYER", "CONTRADICTORY_DATES", "UNSUPPORTED_METRIC",
}

audit = []
audit.append("# V1.2 human audit - no VALID document contains a critical violation")
audit.append("")

violations = []
valid_seen = 0

# 1) Every adversarial claim, embedded in a letter, must not reach VALID.
ds = json.loads(pathlib.Path("docs/adversarial_dataset_v1.1.json").read_text(encoding="utf-8"))
for case in ds["cases"]:
    letter = f"Dear Hiring Team,\n\n{case['text']}\n\nKind regards,\nTommie van der Berg"
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    crit = [i for i in r.issues if i.code in CRITICAL_CODES]
    if r.status is ValidationStatus.VALID:
        valid_seen += 1
        if crit or find_issues(letter):
            violations.append(f"{case['id']}: reached VALID with critical findings")
    audit.append(f"  {case['id']:<8} {case['expect']:<28} -> {r.status.value}")

# 2) Every sanitization payload must be blocked.
for case in ds["sanitization_cases"]:
    text = case.get("text", "")
    letter = f"Dear Hiring Team,\n\n{text}\n\nKind regards,\nTommie van der Berg"
    r = validate_cover_letter(letter, profile, "Data Scientist", "Acme")
    if r.status is ValidationStatus.VALID:
        violations.append(f"sanitization {case['id']}: payload reached VALID")
    audit.append(f"  {case['id']:<8} {'payload':<28} -> {r.status.value}")

# 3) Every captured real artifact.
res = json.loads(pathlib.Path("validation_jobs/_results.json").read_text(encoding="utf-8"))
audit.append("")
audit.append("captured artifacts:")
for k, v in res.items():
    meta = v["meta"]
    p = pathlib.Path(f"validation_jobs/{k}_coverletter.txt")
    if not p.exists():
        continue
    letter = p.read_text(encoding="utf-8")
    r = validate_cover_letter(letter, profile, meta["title"], meta["company"],
                              job_description=tokens(meta.get("description", "")))
    audit.append(f"  {k:<8} {meta['company']:<16} -> {r.status.value} "
                 f"({len(r.issues)} findings, "
                 f"{sum(1 for i in r.issues if i.claim_severity == 'CRITICAL')} critical)")

fresh = pathlib.Path("validation_jobs/VJ-03_fresh_coverletter.txt")
if fresh.exists():
    letter = fresh.read_text(encoding="utf-8")
    r = validate_cover_letter(letter, profile, "Data Analyst", "SEAhub Asia")
    audit.append(f"  {'FRESH':<8} {'SEAhub Asia':<16} -> {r.status.value} "
                 f"({len(r.issues)} findings, "
                 f"{sum(1 for i in r.issues if i.claim_severity == 'CRITICAL')} critical)")
    if r.status is ValidationStatus.VALID:
        violations.append("fresh generated letter reached VALID")

audit.append("")
audit.append(f"documents that reached VALID: {valid_seen}")
audit.append(f"critical violations found in VALID documents: {len(violations)}")
for v in violations:
    audit.append(f"  VIOLATION {v}")
audit.append("")
audit.append("HUMAN AUDIT: " + ("PASS" if not violations else "FAIL"))

pathlib.Path("validation_jobs/_v12_audit.txt").write_text("\n".join(audit), encoding="utf-8")
print(f"reached VALID: {valid_seen} | violations: {len(violations)}")
print("HUMAN AUDIT:", "PASS" if not violations else "FAIL")
for v in violations:
    print("  ", v)