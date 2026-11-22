"""V3.3 Workstream — 26 frozen jobs x 3 runs = 78 production-path extractions.

Uses the same provider, model, temperature, schema and source text as V3.2. No
seed. No prompt change beyond the V3.3 contract already in place. The frozen V3
benchmark is not touched; results go to separate V3.3 artifacts.

Per run records job_id, run_id, provider, model, temperature, seed, prompt and
schema version, source_sha256, raw and canonical requirement counts, extraction
status, the canonical requirement set, and the engine score/recommendation.

Never records the API key.
"""
import hashlib
import json
import pathlib
import sys
from datetime import UTC, datetime

_REPO = pathlib.Path(__file__).resolve().parents[2]
if str(_REPO / "validation_jobs") not in sys.path:
    sys.path.insert(0, str(_REPO / "validation_jobs"))

from app.ai import get_ai_provider
from app.ai.base import AIProviderError
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models import Candidate
from app.schemas import ProfileSummary
from app.services import matching as matching_service
from app.services.extraction import (
    canonical_requirements,
    coerce_requirements_payload,
)
from app.services.matching import build_settings
from benchmark_selector import (  # noqa: E402
    benchmark_members,
    build_population,
    select_window,
)
from harness_scheduling import (  # noqa: E402
    authoritative_successes,
    live_provider_error,
    plan_window,
)
from matching import audit_match
from matching.types import JobProfile, Requirement
from sqlalchemy import select

SETTINGS = get_settings()
PROVIDER = get_ai_provider()
# Population = explicit membership in the frozen benchmark, in the frozen
# benchmark's own case order. Never a slice of the collected-postings file.
BENCHMARK_MEMBERS = benchmark_members(_REPO)
POPULATION = {r["job_id"]: r for r in build_population(_REPO)}
PROFILE = ProfileSummary.model_validate(
    json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8")))
PROFILE_HASH = hashlib.sha256(
    pathlib.Path("val_profile_fixed.json").read_bytes()).hexdigest()[:16]

db = SessionLocal()
CAND = matching_service.to_candidate_profile(
    db.execute(select(Candidate)).scalars().first())
SETTINGS_M = build_settings()

from app.ai.openai_provider import REQUIREMENT_CONTRACT_PROMPT  # noqa: E402

PROMPT_HASH = hashlib.sha256(
    REQUIREMENT_CONTRACT_PROMPT.encode("utf-8")).hexdigest()[:16]

RUN_META = {
    "experiment": "v3.3_deterministic_extraction",
    "contract_version": "v3.3",
    "provider": getattr(PROVIDER, "name", "unknown"),
    "model": SETTINGS.ai_model,
    "temperature": 0.1,
    "seed": None,
    "seed_used": False,
    "schema_version": "ExtractedJobRequirements@2",
    "system_prompt_sha256": PROMPT_HASH,
    "schema_sha256": hashlib.sha256(
        b"ExtractedJobRequirements@2+source_text+category").hexdigest()[:16],
    "profile_sha256": PROFILE_HASH,
    "runs_per_job": 3,
    "population_definition": "explicit membership in the frozen benchmark "
                             "docs/benchmark/matching_benchmark_v3.json",
    "population_order": "the frozen benchmark's own case order",
    "benchmark_case_count": len(BENCHMARK_MEMBERS),
    "api_key_recorded": False,
    "note": "API key rotation is an operational credential change, not an "
            "experimental configuration difference.",
}

STRUCTURED = ("experience_requirements", "education_requirements",
              "location_requirements", "other_requirements")


def sha(t: str) -> str:
    return hashlib.sha256((t or "").encode("utf-8")).hexdigest()


def raw_count(payload: dict) -> int:
    return (len(payload.get("required_skills") or [])
            + len(payload.get("preferred_skills") or [])
            + sum(len(payload.get(k) or []) for k in STRUCTURED))


def snapshot_usage(rec: dict) -> None:
    """Copy the provider's per-call token telemetry onto a run record.

    Measurement only. Historical runs carry no usage fields at all: token
    counts are never estimated and never backfilled into a measured value.
    """
    usage = getattr(PROVIDER, "last_usage", None)
    if not isinstance(usage, dict):
        rec["token_usage_available"] = False
        rec["input_tokens"] = None
        rec["output_tokens"] = None
        rec["total_tokens"] = None
        rec["token_usage_attempts"] = None
        rec["token_usage_timestamp"] = None
        rec["token_usage_extra"] = None
        return
    rec["token_usage_available"] = bool(usage.get("available"))
    rec["input_tokens"] = usage.get("input_tokens")
    rec["output_tokens"] = usage.get("output_tokens")
    rec["total_tokens"] = usage.get("total_tokens")
    rec["token_usage_attempts"] = usage.get("attempts")
    rec["token_usage_timestamp"] = usage.get("timestamp")
    rec["token_usage_extra"] = usage.get("extra")


def engine_for(canon) -> tuple[float, str, int]:
    reqs = []
    for c in canon:
        if c.type == "SKILL":
            reqs.append(Requirement(type="SKILL", name=c.name,
                                    importance=c.importance))
        else:
            reqs.append(Requirement(type=c.type, name=c.name,
                                    importance=c.importance,
                                    description=c.source_text,
                                    years_required=c.years_required))
    job = JobProfile(id=None, title="Data Scientist", company="Acme",
                     location="Lagos, Nigeria", requirements=reqs)
    audit, outcome = audit_match(CAND, job, SETTINGS_M)
    return round(outcome.overall_score, 2), outcome.recommendation, len(audit.blockers)


OUT = pathlib.Path("docs/benchmark/v3_3_extraction_reproducibility_runs.json")
runs = []

# --- V3.3c multi-window scheduler -------------------------------------------
# Only scheduling was added: which jobs this window covers, where results are
# written, and the atomic-triplet / stop-on-quota guard. The per-run
# experiment block below is unchanged from the frozen V3.3 harness.
import argparse  # noqa: E402

_ap = argparse.ArgumentParser()
_ap.add_argument("--from", dest="start", type=int, default=0)
_ap.add_argument("--to", dest="end", type=int, default=26)
_ap.add_argument("--out", dest="out", default=None)
_ap.add_argument("--resume", dest="resume", action="store_true")
_ap.add_argument("--no-quota-guard", dest="stop_on_quota",
                 action="store_false")
START, END = _ap.parse_args().start, _ap.parse_args().end
_args = _ap.parse_args()
START, END, STOP_ON_QUOTA = _args.start, _args.end, _args.stop_on_quota
if _args.out:
    OUT = pathlib.Path(_args.out)
if _args.resume and OUT.exists():
    runs = json.loads(OUT.read_text(encoding="utf-8")).get("runs", [])
WINDOW = select_window(BENCHMARK_MEMBERS, START, END)

# Boundary of the live failure signal. Everything before this index was loaded
# from disk and belongs to an earlier window; only records appended by this
# invocation count as a current provider/quota failure.
WINDOW_START = len(runs)

# Authoritative completion state decides execution, membership decides identity.
# A job already holding a valid complete triplet is skipped, never re-run.
AUTHORITATIVE = authoritative_successes(OUT)
PLAN = plan_window(BENCHMARK_MEMBERS, AUTHORITATIVE, START, END)
TO_RUN = PLAN["to_run"]
SKIPPED = PLAN["skipped"]
PARTIAL = PLAN["partial"]
COMPLETE = PLAN["complete"]

print(f"window: benchmark members [{START}:{END}] of {len(BENCHMARK_MEMBERS)} "
      f"| out={OUT.name} | resume={_args.resume} | existing runs={len(runs)} "
      f"| stop_on_quota={STOP_ON_QUOTA}", flush=True)
print(f"window_start (live failure boundary) : {WINDOW_START}", flush=True)
print(f"jobs in window          : {WINDOW}", flush=True)
print(f"complete triplets (skip): {SKIPPED or 'none'}", flush=True)
print(f"partial triplets        : {PARTIAL or 'none'}", flush=True)
print(f"authoritative to execute: {TO_RUN}", flush=True)
print(f"complete triplets overall: {len(COMPLETE)}/{len(BENCHMARK_MEMBERS)}", flush=True)

for job_id in TO_RUN:
    resolved = POPULATION[job_id]
    source = resolved["source_text"]
    # A partial authoritative triplet is completed by running only what is
    # missing; a complete one never reaches this loop.
    RUN_IDS = PLAN["missing_run_ids"][job_id]
    for run_id in RUN_IDS:
        if STOP_ON_QUOTA and live_provider_error(runs, WINDOW_START):
            # Atomic triplet rule (V3.3c section 5): a provider/quota failure
            # during THIS window abandons the whole job. Missing runs are not
            # fabricated, no other provider/model is tried, and the next job
            # does not start. A later window may resume this job.
            print(f"QUOTA EXHAUSTED - abandoning {job_id} to avoid "
                  "splitting a triplet across windows", flush=True)
            OUT.write_text(json.dumps({"run_metadata": RUN_META, "runs": runs},
                                      indent=2, ensure_ascii=False),
                           encoding="utf-8")
            raise SystemExit(2)
        rec = {
            "job_id": job_id, "run_id": run_id,
            "provider": RUN_META["provider"], "model": RUN_META["model"],
            "temperature": RUN_META["temperature"], "seed": None,
            "prompt_version": RUN_META["system_prompt_sha256"],
            "schema_version": RUN_META["schema_version"],
            "source_sha256": sha(source), "source_chars": len(source),
            "source_origin": resolved["source_origin"],
            "source_status": resolved["source_status"],
            "provenance_status": resolved["provenance_status"],
            "population_status": resolved["population_status"],
            "benchmark_member": True,
            "profile_sha256": PROFILE_HASH,
            "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            "success": False, "failure_code": None, "failure_detail": None,
            "extraction_status": None,
            "raw_requirement_count": None, "canonical_requirement_count": None,
            "canonical_requirement_set": None, "score": None,
            "recommendation": None, "blocker_count": None,
            "canonical_notes": None,
            "raw_extraction": None, "coerced_extraction": None,
            "token_usage_available": False,
            "input_tokens": None, "output_tokens": None, "total_tokens": None,
            "token_usage_attempts": None, "token_usage_timestamp": None,
            "token_usage_extra": None,
        }
        try:
            extracted = PROVIDER.extract_job_requirements(source)
            snapshot_usage(rec)
            # Raw provider output is preserved verbatim. It is never replaced by
            # the coerced or canonicalized form, which are stored alongside it.
            payload = extracted.model_dump()
            coerced, _rep = coerce_requirements_payload(payload)
            canon, notes = canonical_requirements(coerced)
            score, rec_name, blockers = engine_for(canon)
            rec.update(
                success=True,
                extraction_status="SUCCESS" if not notes else "SUCCESS",
                raw_extraction=payload,
                coerced_extraction=coerced,
                raw_requirement_count=raw_count(coerced),
                canonical_requirement_count=len(canon),
                canonical_requirement_set=sorted(list(i) for i in
                                                  ({c.identity() for c in canon})),
                canonical_requirements=[c.to_dict() for c in canon],
                canonical_notes=notes[:25],
                score=score, recommendation=rec_name, blocker_count=blockers,
                payload_hash=sha(json.dumps(coerced, sort_keys=True,
                                            default=str))[:32],
            )
        except AIProviderError as exc:
            snapshot_usage(rec)
            msg = str(exc)
            rec["failure_code"] = ("PROVIDER_ERROR"
                                   if "429" in msg or "rate" in msg.lower()
                                   else "EXTRACTION_FAILED")
            rec["failure_detail"] = msg[:300]
        except Exception as exc:  # noqa: BLE001
            snapshot_usage(rec)
            rec["failure_code"] = type(exc).__name__
            rec["failure_detail"] = str(exc)[:300]
        runs.append(rec)
        print(f"{rec['job_id']} run{run_id} "
              f"{'ok raw=' + str(rec['raw_requirement_count']) + ' canon=' + str(rec['canonical_requirement_count']) + ' rec=' + str(rec['recommendation']) if rec['success'] else 'FAIL ' + str(rec['failure_code'])}",
              flush=True)
    OUT.write_text(json.dumps({"run_metadata": RUN_META, "runs": runs},
                              indent=2, ensure_ascii=False), encoding="utf-8")

ok = sum(1 for r in runs if r["success"])
planned = len(BENCHMARK_MEMBERS) * 3
print(f"\npopulation: {len(BENCHMARK_MEMBERS)} benchmark members "
      f"| planned {planned} | completed {len(runs)} | success {ok} "
      f"| failed {len(runs) - ok}")
