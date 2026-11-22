"""V3 diagnostic continuation — Workstream A: controlled extraction experiment.

Runs each benchmark posting three times under identical conditions, records full
run identity (model, provider, temperature, seed, prompt/schema hashes, source
hash, profile hash), then compares extractions STRUCTURALLY rather than as raw
strings.

Reads only. Changes no prompt, model, temperature or parsing rule.
"""
import hashlib
import json
import pathlib
from datetime import datetime, timezone

from app.ai import get_ai_provider
from app.core.config import get_settings
from app.services.normalization import normalize_text

SETTINGS = get_settings()
PROVIDER = get_ai_provider()
RUNS = 3
OUT_DIR = pathlib.Path("validation_jobs/extraction_runs")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def prompts() -> tuple[str, str]:
    """Reproduce the exact prompt pair used by extract_job_requirements."""
    system = (
        "You extract explicit requirements from job descriptions. "
        "Return a single JSON object containing exactly these keys.\n"
        "TYPE RULES - follow them exactly:\n"
        "- required_skills: array of PLAIN STRINGS, e.g. [\"Python\", \"SQL\"]. "
        "Not objects. Just the skill name as text.\n"
        "- preferred_skills: array of PLAIN STRINGS, same rule as required_skills.\n"
        "- responsibilities: array of PLAIN STRINGS.\n"
        "- issues: array of PLAIN STRINGS.\n"
        "- experience_requirements, education_requirements, location_requirements and "
        "other_requirements: arrays of OBJECTS. Each object has keys "
        "name (string), description (string or null), "
        "importance (string: REQUIRED or PREFERRED or UNKNOWN), "
        "years_required (number or null).\n"
        "The object form applies ONLY to those four *_requirements arrays. "
        "It must NOT be used for required_skills or preferred_skills.\n"
        "Do not treat every sentence as a hard requirement. Only record work-authorisation "
        "conditions when they are explicitly stated."
    )
    return system, "Job description:\n\n{SOURCE}"

RUN_META = {
    "provider": getattr(PROVIDER, "name", "unknown"),
    "base_model": SETTINGS.ai_model,
    "base_url": SETTINGS.ai_base_url,
    "temperature": 0.1,
    "seed": None,
    "seed_supported": False,
    "response_format": {"type": "json_object"},
    "max_retries": SETTINGS.ai_max_retries,
    "schema_version": "ExtractedJobRequirements@1",
    "runs_per_posting": RUNS,
}


def canonical(extraction: dict) -> dict:
    """Order-insensitive, normalisation-aware view of one extraction."""
    def strset(values):
        return sorted({normalize_text(v) for v in (values or []) if v})

    def objset(values, kind):
        out = []
        for v in values or []:
            if not isinstance(v, dict):
                out.append({"kind": kind, "name": normalize_text(str(v)),
                            "importance": "", "years": None,
                            "description": "", "malformed": True})
                continue
            imp = v.get("importance")
            out.append({
                "kind": kind,
                "name": normalize_text(v.get("name") or ""),
                "importance": getattr(imp, "value", imp) or "UNKNOWN",
                "years": v.get("years_required"),
                "description": normalize_text(v.get("description") or ""),
                "malformed": False,
            })
        return sorted(out, key=lambda r: (r["kind"], r["name"], r["importance"]))

    return {
        "required_skills": strset(extraction.get("required_skills")),
        "preferred_skills": strset(extraction.get("preferred_skills")),
        "experience_requirements": objset(
            extraction.get("experience_requirements"), "EXPERIENCE"),
        "education_requirements": objset(
            extraction.get("education_requirements"), "EDUCATION"),
        "location_requirements": objset(
            extraction.get("location_requirements"), "LOCATION"),
        "other_requirements": objset(
            extraction.get("other_requirements"), "OTHER"),
    }


def to_engine(extraction: dict) -> dict:
    """Canonical form -> the flat requirement list the engine consumes."""
    from matching.types import Requirement

    c = canonical(extraction)
    reqs = []
    for s in c["required_skills"]:
        reqs.append(Requirement(type="SKILL", name=s, importance="REQUIRED"))
    for s in c["preferred_skills"]:
        reqs.append(Requirement(type="SKILL", name=s, importance="PREFERRED"))
    for key in ("experience_requirements", "education_requirements",
                "location_requirements", "other_requirements"):
        kind = key.split("_")[0].upper()
        for item in c[key]:
            reqs.append(Requirement(
                type=kind, name=item["name"], importance=item["importance"],
                description=item["description"], years_required=item["years"]))
    return reqs


def compare(a: dict, b: dict) -> dict:
    """Structural diff between two canonical extractions."""
    added, removed, modified, reclassified, reordered_only = [], [], [], [], []
    for key in a:
        la, lb = a[key], b[key]
        if la == lb:
            continue
        sa = {(i["name"], i["importance"]) if isinstance(i, dict) else (i, "")
              for i in la}
        sb = {(i["name"], i["importance"]) if isinstance(i, dict) else (i, "")
              for i in lb}
        names_a = {(i["name"], i["importance"]) if isinstance(i, dict) else (i, "")
                   for i in la}
        names_b = {(i["name"], i["importance"]) if isinstance(i, dict) else (i, "")
                   for i in lb}
        only_a_names = {n for n, _ in names_a}
        only_b_names = {n for n, _ in names_b}
        # Same name set, different importance => RECLASSIFIED.
        for name in sorted(only_a_names & only_b_names):
            imp_a = {i for n, i in [(x["name"], x["importance"]) for x in la
                                    if isinstance(x, dict)] if n == name} \
                if any(isinstance(x, dict) for x in la) else set()
            imp_b = {i for n, i in [(x["name"], x["importance"]) for x in lb
                                    if isinstance(x, dict)] if n == name} \
                if any(isinstance(x, dict) for x in lb) else set()
            if imp_a != imp_b:
                reclassified.append(
                    {"field": key, "name": name,
                     "from": sorted(imp_a), "to": sorted(imp_b)})
        for n in sorted(only_b_names - only_a_names):
            added.append({"field": key, "name": n})
        for n in sorted(only_a_names - only_b_names):
            removed.append({"field": key, "name": n})
        if not (only_a_names ^ only_b_names):
            # Same names, different ordering only.
            reordered_only.append({"field": key})
    if not (added or removed or reclassified):
        modified = [{"field": k} for k in a if a[k] != b[k] and not reordered_only
                    or any(x["field"] == k for x in reordered_only)]
        modified = [{"field": x["field"]} for x in modified]
    return {"added": added, "removed": removed, "reclassified": reclassified,
            "modified": modified, "reordered_only": reordered_only}


# --------------------------------------------------------------------------- #
# run
# --------------------------------------------------------------------------- #

postings = json.loads(
    pathlib.Path("validation_jobs/postings/collected.json").read_text(encoding="utf-8")
)
system_prompt, user_template = prompts()
records = []

for job in postings[:26]:
    source = job["description"]
    per_run = []
    for run in range(1, RUNS + 1):
        extracted = PROVIDER.extract_job_requirements(source)
        raw = extracted.model_dump()
        canon = canonical(raw)
        per_run.append({
            "run": run,
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_sha256": sha(source),
            "canonical": canon,
            "counts": {
                "required_skills": len(canon["required_skills"]),
                "preferred_skills": len(canon["preferred_skills"]),
                "experience": len(canon["experience_requirements"]),
                "education": len(canon["education_requirements"]),
                "location": len(canon["location_requirements"]),
                "other": len(canon["other_requirements"]),
            },
        })
    base = per_run[0]["canonical"]
    diffs = [compare(base, r["canonical"]) for r in per_run[1:]]
    unstable = any(
        d["added"] or d["removed"] or d["reclassified"] or d["modified"]
        for d in diffs
    )
    records.append({
        "job_id": job["job_id"],
        "title": job["title"],
        "company": job["company"],
        "source": job["url"],
        "source_sha256": sha(source),
        "source_chars": len(source),
        "system_prompt_sha256": sha(system_prompt),
        "user_prompt_sha256": sha(user_template.replace("{SOURCE}", "")),
        "runs": per_run,
        "diffs": diffs,
        "stable": not unstable,
        "diff_class": (
            "REORDERED_ONLY" if not unstable and any(d["reordered_only"] for d in diffs)
            else ("UNSTABLE" if unstable else "IDENTICAL")
        ),
    })
    print(f"{job['job_id']:<8}{'STABLE' if not unstable else 'UNSTABLE':<9}"
          f"runs={len(per_run)} counts={[r['counts']['required_skills'] for r in per_run]}")

payload = {"run_metadata": RUN_META, "records": records}
pathlib.Path("validation_jobs/_v3_extraction_experiment.json").write_text(
    json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

stable = sum(1 for r in records if r["stable"])
print(f"\nstable: {stable}/{len(records)}   "
      f"unstable: {len(records) - stable}/{len(records)}")