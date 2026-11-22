"""V2 human audit (Gate J).

Checks that the generated strategies are useful, understandable,
evidence-grounded, non-inventive and actionable. Each criterion is evaluated
explicitly rather than asserted.
"""
import json
import pathlib
import re

from app.db.session import SessionLocal
from app.models import ApplicationStrategy, Candidate, Job
from app.schemas import ProfileSummary
from app.services import strategy_store
from app.services.evidence import build_index

profile = ProfileSummary.model_validate(
    json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8"))
)
idx = build_index(profile)
labels = {i.label for i in idx.items}

ABSENCE_CLAIMS = ("does not have", "has no experience", "lacks", "never used",
                  "cannot do", "is not authorized", "is not authorised",
                  "has never", "no experience with")
ELIGIBILITY_CLAIMS = ("authorized to work", "authorised to work", "eligible for",
                      "no sponsorship", "security clearance", "citizen of",
                      "require sponsorship")

db = SessionLocal()
candidate = db.execute(__import__("sqlalchemy").select(Candidate)).scalars().first()
records = db.query(ApplicationStrategy).filter(
    ApplicationStrategy.candidate_id == candidate.id
).order_by(ApplicationStrategy.job_id).all()

findings: list[str] = []
lines = ["# V2 human audit", ""]

for record in records:
    s = strategy_store.to_strategy(record)
    job = db.get(Job, record.job_id)
    name = f"{job.title} @ {job.company}"
    lines.append(f"===== {name}  ({record.decision})")

    # 1. Useful + understandable: non-empty decision and summary.
    if not s.decision_summary.strip():
        findings.append(f"{name}: no decision summary")
    if len(s.decision_summary.split()) < 8:
        findings.append(f"{name}: decision summary too thin to be useful")
    if len(s.decision_summary.split()) > 180:
        findings.append(f"{name}: decision summary is not scannable")

    # 2. Evidence-grounded: every candidate-specific item cites real evidence.
    for strength in s.strengths:
        if not strength.evidence_ids or any(
            e not in labels for e in strength.evidence_ids
        ):
            findings.append(f"{name}: ungrounded strength {strength.requirement_name}")
    for t in s.transferable_evidence:
        if not t.evidence_ids or any(e not in labels for e in t.evidence_ids):
            findings.append(f"{name}: ungrounded transfer {t.requirement_name}")
    for e in s.evidence_emphasis:
        if any(lbl not in labels for lbl in e.evidence_ids):
            findings.append(f"{name}: ungrounded emphasis {e.evidence_ids}")

    # 3. Non-inventive: no absence claims, no eligibility claims anywhere.
    blob = " ".join([
        s.decision_summary,
        *[g.statement for g in s.gaps],
        *[b.statement for b in s.blockers],
        *[t.statement for t in s.transferable_evidence],
        *[st.statement for st in s.strengths],
        *[r.reason for r in s.claim_restrictions],
    ]).lower()
    for phrase in ABSENCE_CLAIMS:
        if phrase in blob:
            findings.append(f"{name}: asserts factual absence ('{phrase}')")
    for phrase in ELIGIBILITY_CLAIMS:
        if phrase in blob:
            findings.append(f"{name}: asserts eligibility ('{phrase}')")

    # 4. Gap integrity: every gap says "not established".
    for gap in s.gaps:
        if "not established" not in gap.statement.lower():
            findings.append(f"{name}: gap lacks 'not established' phrasing")

    # 5. Blocker integrity: blockers name a real requirement.
    req_names = {r.name for r in job.requirements}
    for b in s.blockers:
        if b.requirement_name not in req_names:
            findings.append(f"{name}: blocker not tied to a requirement")

    # 6. Actionable: ordered, prioritised, each with a rationale.
    if not s.actions:
        findings.append(f"{name}: no action plan")
    prios = [a.priority for a in s.actions]
    if prios != sorted(prios) or prios[0] != 1:
        findings.append(f"{name}: action plan is not ordered from 1")
    for a in s.actions:
        if not a.action.strip() or not a.rationale.strip():
            findings.append(f"{name}: action {a.priority} lacks rationale")

    # 7. SKIP must not tell the candidate to apply.
    if s.decision == "SKIP":
        blob_actions = " ".join(a.action.lower() for a in s.actions)
        if "submit the application" in blob_actions:
            findings.append(f"{name}: SKIP strategy still tells the user to submit")

    # 8. Decision consistency with the frozen match.
    if s.decision != record.decision:
        findings.append(f"{name}: stored decision drift")

    lines.append(f"  summary words        : {len(s.decision_summary.split())}")
    lines.append(f"  strengths/gaps       : {len(s.strengths)}/{len(s.gaps)}")
    lines.append(f"  blockers/restrictions: {len(s.blockers)}/{len(s.claim_restrictions)}")
    lines.append(f"  actions/review notes : {len(s.actions)}/{len(s.review_notes)}")
    lines.append(f"  evidence grounding   : OK" if not any(
        f.startswith(name) and "ungrounded" in f for f in findings) else "  GROUNDING ISSUE")
    lines.append("")

lines += ["================ summary",
          f"strategies audited: {len(records)}",
          f"findings: {len(findings)}"]
for f in findings:
    lines.append(f"  - {f}")
lines += ["", "HUMAN AUDIT: " + ("PASS" if not findings else "FAIL")]

text = "\n".join(lines)
pathlib.Path("validation_jobs/_v2_audit.txt").write_text(text, encoding="utf-8")
print(text)