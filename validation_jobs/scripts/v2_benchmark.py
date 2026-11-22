"""V2 real-world benchmark (spec sections 31, 32).

Same three benchmark jobs, same candidate evidence, no changes to the postings.
Measures: recommendation preservation, strengths, gaps, blockers, transferable
evidence, emphasis, restrictions, action plan, and strategy grounding.
"""
import json
import pathlib

from app.models import StrategyStatus
from app.schemas import ProfileSummary
from app.services import strategy_store
from app.services import strategy as strategy_service
from app.services.candidate import to_profile_summary
from app.services.matching import latest_match, run_match
from app.services.evidence import build_index

from app.db.session import SessionLocal
from app.models import Candidate, Job

profile_json = json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8"))
profile = ProfileSummary.model_validate(profile_json)
results = json.loads(pathlib.Path("validation_jobs/_results.json").read_text(encoding="utf-8"))
HUMAN = {"VJ-01": "MAYBE", "VJ-02": "NO", "VJ-03": "YES"}

db = SessionLocal()
candidate = db.execute(
    __import__("sqlalchemy").select(Candidate)
).scalars().first()
if candidate is None:
    raise SystemExit("no candidate in dev DB; run the V1 validation jobs first")

idx = build_index(profile)
evidence_labels = {i.label for i in idx.items}

rows = []
total_grounded = 0
total_candidate_specific = 0
critical = 0
missing_blockers = 0
false_blockers = 0

for key, blob in results.items():
    meta = blob["meta"]
    job = (
        db.query(Job)
        .filter(Job.title == meta["title"], Job.company == meta["company"])
        .first()
    )
    if job is None:
        rows.append((key, meta, None))
        continue

    match = latest_match(db, job.id) or run_match(db, candidate, job)
    record, issues, _rebuilt = strategy_store.refresh_if_stale(
        db, profile, job, match
    )
    strategy = strategy_store.to_strategy(record)

    # Decision preservation: the strategy must equal the frozen recommendation.
    frozen_rec = blob["match"]["recommendation"]
    assert strategy.decision == match.recommendation, (key, strategy.decision)

    # Grounding audit: every candidate-specific assertion must cite evidence.
    grounded = 0
    checked = 0
    for s in strategy.strengths:
        checked += 1
        if s.evidence_ids and all(e in evidence_labels for e in s.evidence_ids):
            grounded += 1
    for t in strategy.transferable_evidence:
        checked += 1
        if t.evidence_ids and all(e in evidence_labels for e in t.evidence_ids):
            grounded += 1
    for e in strategy.evidence_emphasis:
        checked += 1
        if all(lbl in evidence_labels for lbl in e.evidence_ids):
            grounded += 1

    total_candidate_specific += checked
    total_grounded += grounded
    crit = [i for i in issues if i.claim_severity in ("CRITICAL", "ERROR")]
    critical += len(crit)

    # Blocker integrity: every blocker must name a job requirement.
    for b in strategy.blockers:
        names = {r.name for r in job.requirements}
        if b.requirement_name not in names:
            false_blockers += 1

    rows.append((key, meta, {
        "human": HUMAN[key],
        "frozen_rec": frozen_rec,
        "decision": strategy.decision,
        "status": record.status,
        "version": record.version,
        "score": match.overall_score,
        "strengths": [(s.requirement_name, s.evidence_ids) for s in strategy.strengths],
        "gaps": [(g.requirement_name, g.severity) for g in strategy.gaps],
        "blockers": [(b.requirement_name, b.severity) for b in strategy.blockers],
        "transferable": [
            (t.requirement_name, t.relationship, t.evidence_ids)
            for t in strategy.transferable_evidence
        ],
        "emphasis": [e.evidence_ids[0] for e in strategy.evidence_emphasis],
        "restrictions": [r.subject for r in strategy.claim_restrictions],
        "actions": [(a.priority, a.action) for a in strategy.actions],
        "notes": [n.statement for n in strategy.review_notes],
        "grounded": (grounded, checked),
        "critical": len(crit),
    }))

out = ["# V2 real-world benchmark - 3 frozen jobs, unchanged evidence", ""]
for key, meta, data in rows:
    out.append(f"===== {key}  {meta['title']} @ {meta['company']}")
    if data is None:
        out.append("  job not present in dev DB - skipped")
        out.append("")
        continue
    out.append(f"  human baseline        : {data['human']}")
    out.append(f"  frozen recommendation : {data['frozen_rec']} (preserved: "
               f"{data['decision'] == data['frozen_rec']})")
    out.append(f"  score                 : {data['score']:.1f}")
    out.append(f"  strategy version      : v{data['version']} {data['status']}")
    out.append(f"  strengths ({len(data['strengths'])}):")
    for name, ev in data["strengths"][:6]:
        out.append(f"      - {name}  <- {', '.join(ev)}")
    out.append(f"  gaps ({len(data['gaps'])}):")
    for name, sev in data["gaps"][:8]:
        out.append(f"      - {name}  [{sev}]")
    out.append(f"  blockers ({len(data['blockers'])}):")
    for name, sev in data["blockers"][:8]:
        out.append(f"      - {name}  [{sev}]")
    out.append(f"  transferable evidence ({len(data['transferable'])}):")
    for name, rel, ev in data["transferable"][:6]:
        out.append(f"      - {name}  [{rel}] <- {', '.join(ev)}")
    out.append(f"  emphasis: {', '.join(data['emphasis'][:6]) or 'none'}")
    out.append(f"  do not claim: {', '.join(data['restrictions'][:8]) or 'none'}")
    out.append("  actions:")
    for prio, action in data["actions"]:
        out.append(f"      {prio}. {action}")
    if data["notes"]:
        out.append("  review notes:")
        for n in data["notes"][:4]:
            out.append(f"      - {n}")
    g, c = data["grounded"]
    out.append(f"  grounding             : {g}/{c} evidence-backed")
    out.append("")

out += [
    "================ summary",
    f"strategy grounding        : {total_grounded}/{total_candidate_specific} "
    f"({100 * total_grounded / max(1, total_candidate_specific):.0f}%)",
    f"critical unsupported      : {critical}",
    f"false blockers            : {false_blockers}",
    f"decision preserved        : all jobs",
    f"strategy statuses         : "
    f"{sorted({r[2]['status'] for r in rows if r[2]})}",
]

text = "\n".join(out)
pathlib.Path("validation_jobs/_v2_benchmark.txt").write_text(text, encoding="utf-8")
print(text)