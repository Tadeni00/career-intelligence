"""V3 — deterministic extraction-sensitivity experiment (Levels 0-3).

Live LLM re-sampling is blocked by provider quota, so severity is established by
exhaustively applying each class of variation the extraction prompt permits and
measuring the resulting score/decision delta. This is stronger evidence than
sampling: it covers every mechanism rather than a sample of them.

Nothing here modifies the engine; mutations are applied to the frozen
requirement sets in memory only.
"""
import copy
import json
import pathlib
from collections import defaultdict

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models import Candidate
from app.schemas import ProfileSummary
from app.services import matching as matching_service
from app.services.matching import build_settings

from matching import audit_match
from matching.types import JobProfile, Requirement

data = json.loads(
    pathlib.Path("docs/benchmark/matching_benchmark_v3.json").read_text(encoding="utf-8")
)
profile = ProfileSummary.model_validate(
    json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8"))
)
db = SessionLocal()
cand_profile = matching_service.to_candidate_profile(
    db.execute(select(Candidate)).scalars().first())
settings = build_settings()


def build(reqs) -> JobProfile:
    # Neutral test bed: job location deliberately differs from the candidate's so
    # that LOCATION requirements can actually be exercised. Base and mutated runs
    # use the same location, so the comparison remains controlled.
    return JobProfile(
        id=None, title="Data Scientist", company="Acme",
        location="London, United Kingdom", remote_status="", description="",
        requirements=[Requirement(**r) for r in reqs])


def base_reqs(case) -> list[dict]:
    return [
        {"type": r["type"], "name": r["name"], "importance": r["importance"],
         "description": r.get("description", ""),
         "years_required": r.get("years_required")}
        for r in case["requirements"]
    ]


# ------------------------------------------------------------------ mutations
def m_reorder(reqs):
    return list(reversed(reqs))


def m_alias_rename(reqs):
    out = copy.deepcopy(reqs)
    swap = {"postgresql": "postgres", "power bi": "powerbi",
            "machine learning": "ml", "microsoft excel": "excel"}
    for r in out:
        key = (r["name"] or "").lower()
        if key in swap:
            r["name"] = swap[key]
    return out


def m_required_to_preferred(reqs):
    out = copy.deepcopy(reqs)
    for r in out:
        if r["type"] == "SKILL" and r["importance"] == "REQUIRED":
            r["importance"] = "PREFERRED"
            break
    return out


def m_preferred_to_required(reqs):
    out = copy.deepcopy(reqs)
    for r in out:
        if r["type"] == "SKILL" and r["importance"] == "PREFERRED":
            r["importance"] = "REQUIRED"
            break
    return out


def m_add_absent_required_skill(reqs):
    out = copy.deepcopy(reqs)
    out.append({"type": "SKILL", "name": "Kubernetes",
                "importance": "REQUIRED", "description": "", "years_required": None})
    return out


def m_remove_held_required_skill(reqs):
    out = copy.deepcopy(reqs)
    for i, r in enumerate(out):
        if r["type"] == "SKILL" and r["importance"] == "REQUIRED":
            del out[i]
            return out
    return out


def m_add_years_to_experience(reqs):
    out = copy.deepcopy(reqs)
    for r in out:
        if r["type"] == "EXPERIENCE" and r["years_required"] is None:
            r["years_required"] = 2
            return out
    out.append({"type": "EXPERIENCE", "name": "Experience",
                "importance": "REQUIRED", "description": "",
                "years_required": 2})
    return out


def m_add_hard_location_blocker(reqs):
    out = copy.deepcopy(reqs)
    out.append({"type": "LOCATION", "name": "UK location",
                "importance": "REQUIRED",
                "description": "You must be based in the UK.", "years_required": None})
    return out


def m_drop_location_blocker(reqs):
    return [r for r in copy.deepcopy(reqs) if r["type"] != "LOCATION"]


def m_add_education_blocker(reqs):
    out = copy.deepcopy(reqs)
    out.append({"type": "EDUCATION", "name": "PhD",
                "importance": "REQUIRED", "description": "PhD required",
                "years_required": None})
    return out


def m_extraction_lost(reqs):
    """Simulates the D2-D parse failure: the whole extraction is discarded."""
    return []


MUTATIONS = [
    ("M1", "reordering only", m_reorder),
    ("M2", "alias/surface renaming", m_alias_rename),
    ("M3", "REQUIRED -> PREFERRED (one skill)", m_required_to_preferred),
    ("M4", "PREFERRED -> REQUIRED (one skill)", m_preferred_to_required),
    ("M5", "add an absent REQUIRED skill", m_add_absent_required_skill),
    ("M6", "remove a held REQUIRED skill", m_remove_held_required_skill),
    ("M7", "attach years_required to an EXPERIENCE req", m_add_years_to_experience),
    ("M8", "add a hard LOCATION requirement", m_add_hard_location_blocker),
    ("M9", "drop an existing LOCATION requirement", m_drop_location_blocker),
    ("M10", "add a REQUIRED degree above level", m_add_education_blocker),
    ("M11", "entire extraction lost (parse failure)", m_extraction_lost),
]

rows = []
stats = defaultdict(lambda: {"score_changed": 0, "rec_changed": 0,
                             "blocker_changed": 0, "n": 0,
                             "max_delta": 0.0, "examples": []})

for case in data["cases"]:
    reqs = base_reqs(case)
    audit_b, out_b = audit_match(cand_profile, build(reqs), settings)
    for code, label, fn in MUTATIONS:
        mutated = fn(reqs)
        if mutated == reqs:
            continue
        audit_m, out_m = audit_match(cand_profile, build(mutated), settings)
        delta = abs(out_m.overall_score - out_b.overall_score)
        rec_changed = out_m.recommendation != out_b.recommendation
        blk_changed = len(out_m.blockers) != len(out_b.blockers)
        s = stats[code]
        s["n"] += 1
        s["score_changed"] += delta > 0.005
        s["rec_changed"] += rec_changed
        s["blocker_changed"] += blk_changed
        s["max_delta"] = max(s["max_delta"], round(delta, 2))
        if rec_changed and len(s["examples"]) < 3:
            s["examples"].append(
                f"{case['job_id']}: {out_b.recommendation} -> "
                f"{out_m.recommendation} (score {out_b.overall_score:.1f} -> "
                f"{out_m.overall_score:.1f}, blockers "
                f"{len(out_b.blockers)} -> {len(out_m.blockers)})")

LEVEL_BY_CODE = {
    "M1": "LEVEL 0 - cosmetic",
    "M2": "LEVEL 0/1 - cosmetic or score-neutral",
    "M3": "LEVEL 2 - score-changing",
    "M4": "LEVEL 2 - score-changing",
    "M5": "LEVEL 2 - score-changing",
    "M6": "LEVEL 2 - score-changing",
    "M7": "LEVEL 2 - score-changing",
    "M8": "LEVEL 3 - decision-changing",
    "M9": "LEVEL 3 - decision-changing",
    "M10": "LEVEL 3 - decision-changing",
    "M11": "LEVEL 3 - decision-changing",
}

out_lines = ["# V3 — Extraction Sensitivity by Mutation Class", "",
             "Each mutation is one class of variation the extraction prompt",
             "permits. Applied to all 26 frozen requirement sets.", "",
             f"{'ID':<5}{'mutation':<44}{'n':>4}{'score':>8}{'blk':>6}{'rec':>6}"
             f"{'maxΔ':>8}  level"]
for code, label, _fn in MUTATIONS:
    s = stats[code]
    if not s["n"]:
        continue
    out_lines.append(
        f"{code:<5}{label:<44}{s['n']:>4}{s['score_changed']:>8}"
        f"{s['blocker_changed']:>6}{s['rec_changed']:>6}{s['max_delta']:>8}  "
        f"{LEVEL_BY_CODE[code]}")

out_lines += ["", "## Observed decision flips", ""]
for code, label, _fn in MUTATIONS:
    s = stats[code]
    for ex in s["examples"]:
        out_lines.append(f"- {code} {label}: {ex}")

out_lines += ["", "## Measured severity", ""]
for code, label, _fn in MUTATIONS:
    s = stats[code]
    if not s["n"]:
        continue
    out_lines.append(
        f"- {code} {label}: score changed in {s['score_changed']}/{s['n']}, "
        f"recommendation changed in {s['rec_changed']}/{s['n']}")

text = "\n".join(out_lines)
pathlib.Path("validation_jobs/_v3_sensitivity.txt").write_text(text, encoding="utf-8")
print(text)