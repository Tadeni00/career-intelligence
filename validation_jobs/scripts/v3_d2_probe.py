"""Confirm live-provider availability, then demonstrate the D2-D
(schema/parsing) contribution deterministically. No provider calls are made by
the second half, so this runs even when quota is exhausted.
"""
import json
import os
import pathlib

print("=" * 68)
print("A. LIVE PROVIDER AVAILABILITY PROBE")
print("=" * 68)
from app.ai import get_ai_provider
from app.ai.base import AIProviderError
from app.core.config import get_settings

settings = get_settings()
print(f"provider     : {get_ai_provider().name}")
print(f"model        : {settings.ai_model}")
print(f"temperature  : 0.1")
print(f"seed         : None (not sent by the provider call)")

try:
    get_ai_provider().extract_job_requirements(
        "Required: Python. 5+ years experience. PhD or equivalent."
    )
    print("live extraction: AVAILABLE")
    print("PROBE_RESULT=AVAILABLE")
except AIProviderError as exc:
    msg = str(exc)
    print(f"live extraction: BLOCKED")
    print(f"  {msg[:220]}")
    print("PROBE_RESULT=BLOCKED")

print()
print("=" * 68)
print("B. D2-D SCHEMA/COERCION GAP (deterministic, no provider)")
print("=" * 68)
from app.ai.openai_provider import _coerce_job_requirements
from app.schemas import ExtractedJobRequirements
from pydantic import ValidationError

CASES = {
    "1. required_skills as OBJECTS (prompt says strings)": {
        "required_skills": [{"name": "Python", "importance": "REQUIRED"}],
        "preferred_skills": [], "experience_requirements": [],
        "education_requirements": [], "location_requirements": [],
        "other_requirements": [],
    },
    "2. required_skills as plain strings (prompt-correct)": {
        "required_skills": ["Python"],
        "preferred_skills": [], "experience_requirements": [],
        "education_requirements": [], "location_requirements": [],
        "other_requirements": [],
    },
    "3. importance as ENUM-ish upper string": {
        "required_skills": [], "preferred_skills": [],
        "experience_requirements": [
            {"name": "5+ years ML", "description": None,
             "importance": "REQUIRED", "years_required": "5"}],
        "education_requirements": [], "location_requirements": [],
        "other_requirements": [],
    },
    "4. experience_requirement as a BARE STRING": {
        "required_skills": [], "preferred_skills": [],
        "experience_requirements": ["5+ years of machine learning"],
        "education_requirements": [], "location_requirements": [],
        "other_requirements": [],
    },
    "5. unknown extra key present": {
        "required_skills": ["Python"],
        "preferred_skills": [], "experience_requirements": [],
        "education_requirements": [], "location_requirements": [],
        "other_requirements": [], "nice_to_haves": ["Kubernetes"],
    },
}

for label, payload in CASES.items():
    coerced = _coerce_job_requirements(payload)
    coerced_changed = json.dumps(coerced, sort_keys=True) != json.dumps(
        payload, sort_keys=True)
    try:
        model = ExtractedJobRequirements.model_validate(coerced)
        ok = "VALID"
        detail = (f"required_skills={model.required_skills} "
                  f"exp={len(model.experience_requirements)}")
    except ValidationError as exc:
        ok = "INVALID"
        first = exc.errors()[0]
        detail = f"{first['loc']}: {first['msg'][:60]}"
    print(f"\n{label}")
    print(f"  _coerce_job_requirements changed payload : {coerced_changed}")
    print(f"  schema validation                        : {ok}")
    print(f"  detail                                   : {detail}")

print()
print("=" * 68)
print("C. WHY THIS MATTERS")
print("=" * 68)
print("_coerce_job_requirements repairs only the four *string* arrays.")
print("The four *_requirements object arrays are passed through untouched, so")
print("the same requirement expressed as an object vs a bare string is")
print("silently discarded on validation failure rather than recovered. Two runs")
print("that differ only in that surface choice therefore produce different")
print("requirement sets from the same job text - a parsing contribution to D2")
print("that is entirely independent of model temperature.")