"""V3.2 Workstream C — three-run extraction reproducibility experiment.

26 frozen postings x 3 runs = 78 production-path extraction calls, using the
same provider, model, temperature, prompt and schema as the frozen V3
experiment. No seed is added. No prompt is changed. No benchmark job is
re-extracted into the frozen artifact: this is observational and writes to a
separate versioned artifact.

Records, per run: provider, model, temperature, seed, source_sha256,
source_chars, profile hash, prompt hash, schema_version, timestamp, success,
failure_code, parsed-output hash, requirement_count.

Never stores or transmits the API key.
"""
import hashlib
import json
import pathlib
import time
from datetime import datetime, timezone

from app.ai import get_ai_provider
from app.ai.base import AIProviderError
from app.core.config import get_settings

SETTINGS = get_settings()
PROVIDER = get_ai_provider()

POSTINGS = json.loads(
    pathlib.Path("validation_jobs/postings/collected.json").read_text(encoding="utf-8"))
PROFILE_HASH = hashlib.sha256(
    pathlib.Path("val_profile_fixed.json").read_bytes()).hexdigest()[:16]

# The exact prompts the production provider uses, captured for the record.
PROMPT_SYS = (
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
PROMPT_USER = "Job description:\n\n{SOURCE}"
PROMPT_HASH = hashlib.sha256(
    (PROMPT_SYS + PROMPT_USER).encode("utf-8")).hexdigest()[:16]

RUN_META = {
    "experiment": "v3.2_extraction_reproducibility",
    "provider": getattr(PROVIDER, "name", "unknown"),
    "model": SETTINGS.ai_model,
    "temperature": 0.1,
    "seed": None,
    "seed_used": False,
    "schema_version": "ExtractedJobRequirements@1",
    "response_format": {"type": "json_object"},
    "max_retries": SETTINGS.ai_max_retries,
    "system_prompt_sha256": hashlib.sha256(PROMPT_SYS.encode()).hexdigest()[:16],
    "user_prompt_sha256": hashlib.sha256(PROMPT_USER.encode()).hexdigest()[:16],
    "prompt_sha256": PROMPT_HASH,
    "profile_sha256": PROFILE_HASH,
    "runs_per_job": 3,
    "api_key_recorded": False,
    "note": ("API key rotation is an operational credential change and is "
             "deliberately not recorded as an experimental difference."),
}

OUT = pathlib.Path("docs/benchmark/v3_extraction_reproducibility_runs.json")
STRUCTURED = ("experience_requirements", "education_requirements",
              "location_requirements", "other_requirements")


def sha(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def count(payload: dict) -> int:
    return (
        len(payload.get("required_skills") or [])
        + len(payload.get("preferred_skills") or [])
        + sum(len(payload.get(k) or []) for k in STRUCTURED)
    )


runs: list[dict] = []
failed = 0
completed = 0

for job in POSTINGS[:26]:
    source = job["description"]
    for run_id in (1, 2, 3):
        started = datetime.now(timezone.utc).isoformat(timespec="seconds")
        record = {
            "job_id": job["job_id"],
            "run_id": run_id,
            "provider": RUN_META["provider"],
            "model": RUN_META["model"],
            "temperature": RUN_META["temperature"],
            "seed": None,
            "source_sha256": sha(source),
            "source_chars": len(source),
            "profile_sha256": PROFILE_HASH,
            "prompt_sha256": PROMPT_HASH,
            "schema_version": RUN_META["schema_version"],
            "timestamp": started,
            "success": False,
            "failure_code": None,
            "failure_detail": None,
            "parsed_output_sha256": None,
            "requirement_count": None,
        }
        try:
            extracted = PROVIDER.extract_job_requirements(source)
            payload = extracted.model_dump()
            record["success"] = True
            record["parsed_output_sha256"] = sha(extracted.model_dump_json())[:32]
            record["requirement_count"] = count(payload)
            record["payload"] = payload
        except AIProviderError as exc:
            failed += 1
            msg = str(exc)
            record["failure_code"] = (
                "PROVIDER_ERROR" if "429" in msg or "rate" in msg.lower()
                else "EXTRACTION_FAILED"
            )
            record["failure_detail"] = msg[:300]
        except Exception as exc:  # noqa: BLE001 - record and continue
            failed += 1
            record["failure_code"] = f"{type(exc).__name__}"
            record["failure_detail"] = str(exc)[:300]

        completed += 1
        runs.append(record)
        print(f"{record['job_id']} run{run_id} "
              f"{'ok n=' + str(record['requirement_count']) if record['success'] else 'FAIL ' + str(record['failure_code'])}",
              flush=True)

    # Incremental persistence: a quota abort must not lose completed work.
    OUT.write_text(json.dumps({"run_metadata": RUN_META, "runs": runs},
                              indent=2, ensure_ascii=False), encoding="utf-8")

payload = {"run_metadata": RUN_META, "runs": runs}
OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

ok = sum(1 for r in runs if r["success"])
print(f"\nplanned 78 | completed {completed} | success {ok} | failed {failed}")
print(f"written: {OUT}")
print(f"elapsed: {time.strftime('%H:%M:%S')}")