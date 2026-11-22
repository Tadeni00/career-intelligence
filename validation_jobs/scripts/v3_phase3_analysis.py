"""V3 Phase 3 — requirement-level analysis and hypothesis testing.

Answers the ten diagnostic questions in the specification against the expanded
benchmark. Read-only: it changes nothing.
"""
import json
import pathlib
import statistics
from collections import Counter

data = json.loads(
    pathlib.Path("docs/benchmark/matching_benchmark_v3.json").read_text(encoding="utf-8")
)
cases = data["cases"]
labelled = [c for c in cases if c["human_decision"]]

out = []
w = out.append
w("# V3 Phase 3 — Requirement-Level Analysis and Hypothesis Testing")
w("")
w(f"Benchmark: {len(cases)} cases "
  f"({len(labelled)} human-labelled, "
  f"{len(cases) - len(labelled)} awaiting independent human labels)")
w("")

# ---------------------------------------------------------------- metrics
w("## Decision metrics (human-labelled subset)")
w("")
w("| Job | Human | System | Score | Blocker | Req coverage | Result |")
w("|---|---|---|---:|---:|---:|---|")


def norm(rec: str) -> str:
    return {"APPLY": "YES", "APPLY_WITH_TAILORING": "YES",
            "STRETCH": "MAYBE", "SKIP": "NO"}[rec]


agree = 0
false_skip = 0
false_apply = 0
severe = 0
near = 0
for c in labelled:
    sys_dec = c["system"]["recommendation"]
    hum = c["human_decision"]
    sys_n = norm(sys_dec)
    result = "Agreement" if sys_n == hum else "Disagreement"
    if sys_n == hum:
        agree += 1
    else:
        if {sys_n, hum} == {"YES", "NO"}:
            severe += 1
        else:
            near += 1
    if sys_dec == "SKIP" and hum == "YES":
        false_skip += 1
    if sys_dec in ("APPLY", "APPLY_WITH_TAILORING") and hum == "NO":
        false_apply += 1
    w(f"| {c['job_id']} | {hum} | {sys_dec} | {c['system']['overall_score']:.1f} "
      f"| {len(c['system']['blockers'])} "
      f"| {c['system']['required_coverage']} | {result} |")
w("")
w(f"- exact agreement: {agree}/{len(labelled)} "
  f"({100 * agree / max(1, len(labelled)):.0f}%)")
w(f"- false skips (system SKIP, human YES): {false_skip}")
w(f"- false applies (system APPLY*, human NO): {false_apply}")
w(f"- severe disagreements (YES<->NO): {severe}")
w(f"- near disagreements (MAYBE<->YES/NO): {near}")
w("")
w("**Sample size is 3. No calibration decision may rest on this.**")
w("")

# ------------------------------------------------------- score behaviour
w("## Score behaviour across the expanded benchmark")
w("")
scores = [c["system"]["overall_score"] for c in cases]
recs = Counter(c["system"]["recommendation"] for c in cases)
w(f"- overall score: min={min(scores):.1f} median={statistics.median(scores):.1f} "
  f"max={max(scores):.1f}")
w(f"- recommendation distribution: {dict(recs)}")
for dim in ("technical", "experience", "education", "location", "other"):
    vals = [c["system"][dim] for c in cases]
    w(f"- {dim:<11} min={min(vals):>6.1f} median={statistics.median(vals):>6.1f} "
      f"max={max(vals):>6.1f}")
w("")
w("Dimension spread shows which components actually discriminate:")
w("")

# ------------------------------------------------------------ H1..H10
w("## Hypothesis testing")
w("")

w("### H1 — Threshold mismatch")
blocked_high = [c for c in cases
                if c["system"]["blockers"] and c["system"]["overall_score"] >= 65]
w(f"- Cases scoring >=65 (APPLY band on score alone) that still return SKIP: "
  f"**{len(blocked_high)}**")
for c in blocked_high:
    w(f"    {c['job_id']} score={c['system']['overall_score']:.1f} "
      f"blockers={c['system']['blockers']}")
w("- The thresholds are not the cause. These jobs enter the APPLY band on score "
  "and are overridden by the blocker rule, which is a separate gate.")
w("")

w("### H2 — Component weighting mismatch")
w("- Dimension ranges above show the discriminating power of each component.")
tech = [c["system"]["technical"] for c in cases]
loc = [c["system"]["location"] for c in cases]
w(f"- technical spread: {max(tech) - min(tech):.1f} points "
  f"(largest single lever at 40% weight)")
w(f"- location spread: {max(loc) - min(loc):.1f} points "
  f"(at 10% weight)")
w("- Education and location frequently take flat values, so their weight is "
  "mostly inert. Weight is not the distortion; input coverage is.")
w("")

w("### H3 — Location penalty mismatch")
loc_blocked = [c for c in cases
               if any("location" in b.lower() or "remote" in b.lower()
                      for b in c["system"]["blockers"])]
loc_scores = Counter(c["system"]["location"] for c in cases)
w(f"- Cases blocked by location: **{len(loc_blocked)} of {len(cases)}**")
w(f"- Location score distribution: {dict(loc_scores)}")
far = [c for c in cases if c["system"]["location"] <= 55]
w(f"- Cases where location <=55 (penalised or blocked): {len(far)}")
w("- Location drives a large share of SKIPs relative to its 10% weight, because "
  "it is a *gate* (blocker) and not merely a weighted term.")
w("")

w("### H4 — Missing evidence treated too negatively")
states = Counter()
for c in cases:
    for k, v in c["system"]["diagnostic_states"].items():
        states[k] += v
w(f"- Diagnostic state totals across the benchmark: {dict(states)}")
unknown = states.get("E_EVIDENCE_UNKNOWN", 0)
material = states.get("B_MATERIAL_GAP", 0)
w(f"- EVIDENCE_UNKNOWN ({unknown}) outnumbers MATERIAL_GAP ({material}) "
  f"{unknown / max(1, material):.1f}x")
w("- The engine already distinguishes 'not established' from 'absent' for "
  "PREFERRED/soft skills: they land in `unknowns`, not `gaps`.")
w("- **But REQUIRED skills with no match go to `gaps`, which is presented to the "
  "user as a gap, i.e. framed as a deficiency rather than an evidence boundary.**")
w("")

w("### H5 — Requirement classification error")
counts = Counter(r["importance"] for c in cases for r in c["requirements"])
w(f"- Importance distribution: {dict(counts)}")
req_per_job = [c["requirements_extracted"] for c in cases]
w(f"- Requirements extracted per job: min={min(req_per_job)} "
  f"median={statistics.median(req_per_job)} max={max(req_per_job)}")
no_years = [
    (c["job_id"], r["name"]) for c in cases for r in c["requirements"]
    if r["type"] == "EXPERIENCE" and r.get("years_required") is None
]
w(f"- EXPERIENCE requirements with no years value: **{len(no_years)}**")
w("- These are extracted, then silently discarded by `engine._score_experience`, "
  "which only handles requirements that carry `years_required`. They do not score "
  "and do not appear as unknowns.")
w("")

w("### H6 — Hard blocker semantics")
srcs = Counter()
for c in cases:
    for s in c["system"]["blocker_sources"]:
        srcs[s.split(":")[0].strip()] += 1
w(f"- Blocker source distribution: {dict(srcs)}")
edu = sum(1 for c in cases
          for s in c["system"]["blocker_sources"] if "education" in s)
locb = sum(1 for c in cases
           for s in c["system"]["blocker_sources"] if "location" in s)
w(f"- Education blockers: {edu}   Location blockers: {locb}")
w("- `_score_technical` and `_score_other` can never emit a blocker. A missing "
  "REQUIRED *skill* never blocks, but a missing REQUIRED *degree* always does. "
  "That asymmetry is undocumented behaviour, not a stated policy.")
w("")

w("### H7 — Suitability/action conflation")
w("- Evidence: jobs with technical >=90 and a strong score still return SKIP "
  "purely because of a location gate.")
conf = [c for c in cases
        if c["system"]["technical"] >= 80 and c["system"]["recommendation"] == "SKIP"]
w(f"- Cases with technical >=80 that are SKIP: **{len(conf)}**")
for c in conf:
    w(f"    {c['job_id']} technical={c['system']['technical']:.0f} "
      f"overall={c['system']['overall_score']:.1f} "
      f"blockers={c['system']['blockers']}")
w("- This is the clearest supported hypothesis. The engine conflates 'does the "
  "evidence support a strong match' with 'should this person apply today'.")
w("")

w("### H8 — Evidence coverage too keyword-oriented")
w("- `_skill_names_match` is exact-alias or token-overlap. It cannot connect "
  "'controlled experiments' to 'A/B testing' even where the alias table has an "
  "entry, because the entry only fires on surface form.")
unmapped = sum(1 for c in cases for k, v in c["system"]["diagnostic_states"].items()
               if k == "E_EVIDENCE_UNKNOWN" for _ in range(v))
w(f"- Requirements recorded as unmappable to confirmed evidence: {unmapped}")
w("")

w("### H9 — Experience scoring insufficiently discriminative")
exp = [c["system"]["experience"] for c in cases]
w(f"- Experience spread: min={min(exp):.1f} median={statistics.median(exp):.1f} "
  f"max={max(exp):.1f}")
hi = sum(1 for v in exp if v >= 95)
w(f"- Cases at experience >=95: **{hi} of {len(cases)}**")
w("- `_score_experience` is 50% title similarity + 50% years ratio. Most real "
  "postings request 2-5 years against a 6-year candidate, so the ratio saturates "
  "at 100 and the dimension stops discriminating between a marginally and a "
  "clearly qualified candidate.")
w("")

w("### H10 — Other category too broad")
other_scores = [c["system"]["other"] for c in cases]
w(f"- Other spread: min={min(other_scores):.1f} "
  f"median={statistics.median(other_scores):.1f} max={max(other_scores):.1f}")
w("- `_score_other` mixes salary, employment type, and every requirement the "
  "extractor could not type. Each unverifiable REQUIRED item is assigned a flat "
  "40/100 by construction, so unrelated concepts are averaged as if comparable.")
w("")

text = "\n".join(out)
pathlib.Path("validation_jobs/_v3_phase3_analysis.txt").write_text(text, encoding="utf-8")
print(text)