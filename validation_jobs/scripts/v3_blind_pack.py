"""V3 Workstream B — build the BLIND human labelling package.

The reviewer receives the candidate profile and the frozen job postings, and
nothing else. System scores, recommendations, component scores, blockers, V3
root-cause findings and calibration hypotheses are all withheld.

Labels themselves are left PENDING: they must be supplied by an independent
human reviewer, never inferred here.
"""
import json
import pathlib

BENCH = json.loads(
    pathlib.Path("docs/benchmark/matching_benchmark_v3.json").read_text(encoding="utf-8")
)
POSTINGS = {
    j["job_id"]: j for j in json.loads(
        pathlib.Path("validation_jobs/postings/collected.json").read_text(encoding="utf-8"))
}
PROFILE_RAW = json.loads(
    pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8"))

OUT = pathlib.Path("docs/benchmark")
OUT.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------- candidate
candidate = {
    "note": (
        "This is the authoritative candidate profile used by the benchmark. It "
        "was completed verbatim from the candidate's CV. Fields absent from the "
        "CV are genuinely unknown and are NOT treated as negative evidence."
    ),
    "name": PROFILE_RAW.get("name"),
    "professional_title": PROFILE_RAW.get("professional_title"),
    "location": PROFILE_RAW.get("location"),
    "years_of_experience": PROFILE_RAW.get("years_of_experience"),
    "summary": PROFILE_RAW.get("summary"),
    "skills": sorted(s["name"] for s in PROFILE_RAW.get("skills", [])),
    "experience": [
        {
            "title": e.get("title"),
            "company": e.get("company"),
            "start_date": e.get("start_date"),
            "end_date": e.get("end_date"),
            "description": e.get("description"),
        }
        for e in PROFILE_RAW.get("experience", [])
    ],
    "education": [
        {"institution": e.get("institution"), "degree": e.get("degree"),
         "field": e.get("field"), "end_date": e.get("end_date")}
        for e in PROFILE_RAW.get("education", [])
    ],
    "projects": [
        {"name": p.get("name"), "description": p.get("description"),
         "technologies": p.get("technologies")}
        for p in PROFILE_RAW.get("projects", [])
    ],
    "deliberately_unset": [
        "preferred_roles", "preferred_locations", "remote_preference",
        "minimum_salary",
    ],
    "work_authorisation_status": (
        "NOT RECORDED. No evidence of citizenship, residency, visa status or "
        "right to work exists. Do not infer any."
    ),
}

# ------------------------------------------------------------- label form
LABEL_FORM = """Job ID:

Decision:
YES | MAYBE | NO

Primary reason:
<1-3 sentences. Explain what actually drove the decision.>

Material strengths:
- ...
- ...

Material concerns:
- ...
- ...

Hard blocker:
YES | NO

If YES, specify:
<the specific objective condition that makes an application unreasonable>

Would I personally apply?
YES | NO

Confidence:
HIGH | MEDIUM | LOW
"""

GUIDANCE = [
    "Label from the candidate's ACTUAL recorded evidence and the job posting.",
    "Judge this job only. Do not consider any other job or the overall picture.",
    "NO means: given this evidence and this opportunity, you would not recommend "
    "applying. It does NOT mean the candidate is incapable of the work.",
    "YES means: you would consider this sufficiently viable to apply.",
    "MAYBE means: genuinely balanced, or a real condition that could be resolved.",
    "A skill absent from the candidate's evidence is an EVIDENCE BOUNDARY. It is "
    "not proof the candidate lacks it. Say so in the reason.",
    "Do not infer work authorisation, relocation feasibility or salary "
    "expectations. They are not recorded.",
    "A label of 'YES - good fit' is insufficient. State the reason.",
]

# --------------------------------------------------------- blind case set
cases = []
for case in BENCH["cases"]:
    jid = case["job_id"]
    if case.get("frozen_regression_case"):
        continue  # already labelled pre-V3
    posting = POSTINGS.get(jid, {})
    cases.append({
        "job_id": jid,
        "title": case["title"],
        "company": case["company"],
        "location_field": case.get("location"),
        "source_url": case.get("source_url"),
        "source": case.get("source"),
        "full_posting_text": posting.get("description", ""),
    })

labels = {
    "version": "3.0",
    "status": "PENDING_INDEPENDENT_HUMAN_REVIEW",
    "instructions": (
        "These labels must be completed by an independent human reviewer who has "
        "not seen any system score, recommendation, component score, blocker, "
        "V3 finding or calibration hypothesis. Labels were deliberately NOT "
        "inferred from system output, keyword coverage or previous analysis."
    ),
    "label_form": LABEL_FORM,
    "guidance": GUIDANCE,
    "decision_semantics": {
        "YES": "would consider this sufficiently viable to apply",
        "MAYBE": "genuinely balanced, or a real condition that could be resolved",
        "NO": "would not recommend applying; NOT a statement about capability",
    },
    "labels": [
        {
            "job_id": c["job_id"],
            "decision": None,
            "primary_reason": None,
            "material_strengths": [],
            "material_concerns": [],
            "hard_blocker": None,
            "hard_blocker_detail": None,
            "would_apply": None,
            "confidence": None,
        }
        for c in cases
    ],
}

reviewer = {
    "version": "3.0",
    "note": (
        "Blind review material. Contains the candidate profile, the frozen job "
        "postings and the label form ONLY. No system output is present."
    ),
    "candidate": candidate,
    "guidance": GUIDANCE,
    "label_form": LABEL_FORM,
    "jobs": cases,
}

(OUT / "human_labels_v3.json").write_text(
    json.dumps(labels, indent=2, ensure_ascii=False), encoding="utf-8")
(OUT / "blind_review_pack_v3.json").write_text(
    json.dumps(reviewer, indent=2, ensure_ascii=False), encoding="utf-8")

# Blindness verification: no SYSTEM OUTPUT may reach the reviewer. Checking
# structure (forbidden keys) and values (each case's own score/recommendation),
# not vocabulary - "Hard blocker" and "recommend" are mandated form wording.
SYSTEM_KEYS = {
    "recommendation", "overall_score", "technical_score", "experience_score",
    "education_score", "location_score", "other_score", "confidence",
    "matched_items", "gap_items", "blocker_items", "unknown_items",
    "diagnostic_states", "required_coverage", "preferred_coverage",
    "audit_verified", "system", "blocker_sources", "score",
}
leaks: list[str] = []
for job in cases:
    bad = SYSTEM_KEYS & set(job.keys())
    if bad:
        leaks.append(f"{job['job_id']}: forbidden keys {sorted(bad)}")
    own = next(c for c in BENCH["cases"] if c["job_id"] == job["job_id"])
    if str(own["system"]["overall_score"]) in job["full_posting_text"]:
        leaks.append(f"{job['job_id']}: score value appears in posting text")

assert "system" not in reviewer and "system" not in candidate, \
    "reviewer pack must not contain a system block"
assert labels["labels"], "label slots must exist"

print(f"blind pack jobs      : {len(cases)}")
print(f"label slots (PENDING): {len(labels['labels'])}")
print(f"already labelled     : 0 (must stay 0 until a human completes them)")
print(f"system-output leaks  : {leaks or 'none'}")
print(f"full posting text    : "
      f"{sum(1 for c in cases if len(c['full_posting_text']) > 500)}/{len(cases)}")
print(f"candidate skills     : {len(candidate['skills'])}")
print(f"candidate roles      : {len(candidate['experience'])}")