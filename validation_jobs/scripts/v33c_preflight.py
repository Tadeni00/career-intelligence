"""V3.3 measurement-revision preflight. READ-ONLY / OFFLINE.

Produces the gate that must pass before any further Groq extraction call.
Contacts no provider. Modifies no experiment artifact.
"""

import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(".")
sys.path.insert(0, str(REPO / "apps/api"))


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha_file(rel: str) -> str:
    return sha_bytes((REPO / rel).read_bytes())


print("=" * 72)
print("V3.3 MEASUREMENT REVISION -- PREFLIGHT")
print("=" * 72)

# ---------------------------------------------------------------- integrity
print("\n[1] INTEGRITY")
FROZEN = {
    "prompt (REQUIREMENT_CONTRACT_PROMPT)": "43d20b8be806e7ba130d4f1120cc9a4fe9456110a95048092323c3c68afbd436",
    "engine.py": "f8913c528710e3f3",
    "config.py": "0af42435d68b9463",
}
from app.ai.openai_provider import REQUIREMENT_CONTRACT_PROMPT  # noqa: E402

prompt_sha = sha_bytes(REQUIREMENT_CONTRACT_PROMPT.encode("utf-8"))
print(f"  prompt sha256      : {prompt_sha}")
print(f"  prompt chars       : {len(REQUIREMENT_CONTRACT_PROMPT)}")
print(f"  prompt UNCHANGED   : {prompt_sha == FROZEN['prompt (REQUIREMENT_CONTRACT_PROMPT)']}")
print(f"  engine.py          : {sha_file('packages/matching/matching/engine.py')[:16]} "
      f"UNCHANGED={sha_file('packages/matching/matching/engine.py').startswith('f8913c528710e3f3')}")
print(f"  config.py          : {sha_file('packages/matching/matching/config.py')[:16]} "
      f"UNCHANGED={sha_file('packages/matching/matching/config.py').startswith('0af42435d68b9463')}")

code = [
    "apps/api/app/services/requirements.py",
    "apps/api/app/services/extraction.py",
    "apps/api/app/ai/openai_provider.py",
    "apps/api/app/schemas/__init__.py",
    "tests/test_v33_extraction_contract.py",
    "tests/test_openai_provider.py",
]
agg = hashlib.sha256()
for rel in code:
    agg.update(rel.encode())
    agg.update(sha_file(rel).encode())
impl = agg.hexdigest()
print("\n  implementation files (per-file sha256):")
for rel in code:
    print(f"    {sha_file(rel)[:16]}  {rel}")
print(f"\n  implementation aggregate : {impl}")
print(f"  previous implementation   : dcc4f506965d57e99bf0bb54bdd1c429...")
print(f"  CHANGED (expected)       : {impl != 'dcc4f506965d57e99bf0bb54bdd1c429'}")

harness = sha_file("validation_jobs/scripts/v33_runs.py")
print(f"\n  harness sha256           : {harness}")
print(f"  previous harness         : 715be9a26725a131...")
print(f"  CHANGED (expected)       : {not harness.startswith('715be9a26725a131')}")

print("\n  experiment configuration (must be unchanged):")
print("    provider  : openai (OpenAI-compatible Groq)")
print("    model     : openai/gpt-oss-120b")
print("    temperature: 0.1")
print("    seed      : none")
print("    schema    : ExtractedJobRequirements@2")

# ---------------------------------------------------------------- benchmark
print("\n[2] BENCHMARK POPULATION")
bench_path = REPO / "docs/benchmark/matching_benchmark_v3.json"
bench_sha = sha_bytes(bench_path.read_bytes())
bench = json.loads(bench_path.read_text(encoding="utf-8"))
coll = json.loads((REPO / "validation_jobs/postings/collected.json").read_text(encoding="utf-8"))
rec = json.loads((REPO / "docs/benchmark/v3_3_benchmark_reconciliation.json").read_text(encoding="utf-8"))
print(f"  frozen benchmark sha256 : {bench_sha}")
print(f"  benchmark UNCHANGED     : {bench_sha.startswith('4199f5d386e1')}")
print(f"  benchmark population    : {len(bench['cases'])}")
print(f"  collected population    : {len(coll)}")
print(f"  reconciliation written  : docs/benchmark/v3_3_benchmark_reconciliation.{{json,md}}")
print(f"  selection rule reproduces benchmark exactly : "
      f"{rec['selection_rule']['reproduces_frozen_benchmark_exactly']}")
print(f"  governance mismatches   : {rec['selection_rule']['mismatches'] or 'none'}")
print(f"\n  collected postings NOT in benchmark ({len(rec['excluded_postings'])}):")
for r in rec["excluded_postings"]:
    print(f"    {r['job_id']}  {r['company']:<12} {r['identity_class']:<12} "
          f"{r['exclusion_reason'].split(':')[0]}")
print(f"\n  duplicate posting-text pairs: "
      f"{ {k[:16] + '..': v for k, v in rec['identity_audit']['duplicate_posting_texts'].items()} or 'none'}")
print(f"  duplicate source URLs        : {rec['identity_audit']['duplicate_url_count']}")

# ------------------------------------------------- execution vs analysis set
print("\n[3] POPULATION ALIGNMENT DEFECT (blocks resume)")
runs = json.loads((REPO / "docs/benchmark/v3_3c_extraction_reproducibility_runs.json").read_text(encoding="utf-8"))["runs"]
bench_ids = {c["job_id"] for c in bench["cases"]}
coll_ids = [j["job_id"] for j in coll]
# The harness iterates collected.json BY INDEX. Its default window is
# --from 0 --to 26, so its default reach is the first 26 collected postings.
default_window = set(coll_ids[:26])
sourced = set(coll_ids)  # jobs whose source text exists in collected.json at all
print(f"  benchmark population                                : {len(bench_ids)} jobs")
print(f"  harness default window (--to 26, by index)          : {len(default_window)} jobs")
print(f"  in default window but NOT in benchmark              : "
      f"{sorted(default_window - bench_ids)}")
print(f"  in benchmark but NOT in default window              : "
      f"{sorted(bench_ids - default_window)}")
print(f"  in benchmark with NO source text anywhere (dev DB only): "
      f"{sorted(bench_ids - sourced)}")
done = {j for j in sourced if sum(1 for r in runs if r["job_id"] == j and r["success"]) == 3}
print(f"\n  complete V3.3 triplets so far                       : {len(done)} -> {sorted(done)}")
print(f"  completed work outside the benchmark                : {sorted(done - bench_ids) or 'none'}")
reachable = sorted((bench_ids & sourced) - done)
unreachable = sorted(bench_ids - sourced)
missed_by_default = sorted((bench_ids & sourced) - done - default_window)
print(f"\n  in-benchmark unrun WITH source text available       : {len(reachable)} -> {reachable}")
print(f"  in-benchmark unrun with NO source text (unrunnable)  : {len(unreachable)} -> {unreachable}")
print(f"  of those, missed by the default --to 26 window       : {len(missed_by_default)} -> {missed_by_default}")
print(f"\n  reachable calls required   : {len(reachable) * 3}")
print(f"  unreachable calls required : {len(unreachable) * 3}")
print(f"  total remaining requirement: {len(reachable + unreachable) * 3} calls "
      f"over {len(reachable + unreachable)} jobs")

# ---------------------------------------------------------------- telemetry
print("\n[4] TELEMETRY (local mock, no provider call)")
from app.ai.openai_provider import OpenAIProvider  # noqa: E402
from app.core.config import get_settings  # noqa: E402

PAYLOAD = {
    "required_skills": ["Python"], "preferred_skills": ["SQL"],
    "experience_requirements": ["5+ years in machine learning"],
    "education_requirements": [], "location_requirements": [],
    "other_requirements": [],
}


class _M:
    def __init__(self, c): self.message = type("Msg", (), {"content": c})()


class _C:
    def __init__(self, c, u): self.choices = [_M(c)]; self.usage = u


class _U:
    def __init__(self): 
        self.prompt_tokens, self.completion_tokens, self.total_tokens = 4276, 280, 4556
        self.prompt_tokens_details = self.completion_tokens_details = None


class _CC:
    def __init__(self): self.payload = PAYLOAD; self.usage = _U()

    def create(self, **k): return _C(json.dumps(self.payload), self.usage)


class _CL:
    def __init__(self): self.chat = type("X", (), {"completions": _CC()})()


def mk():
    p = OpenAIProvider(get_settings().model_copy(
        update={"ai_api_key": "k", "ai_base_url": "https://example.invalid/v1"}))
    p.client = _CL()
    return p


p1 = mk()
a = p1.extract_job_requirements("posting")
p2 = mk()
p2.client.chat.completions.usage = None
b = p2.extract_job_requirements("posting")
print(f"  with usage    : input={p1.last_usage['input_tokens']} "
      f"output={p1.last_usage['output_tokens']} total={p1.last_usage['total_tokens']} "
      f"available={p1.last_usage['available']}")
print(f"  without usage : input={p2.last_usage['input_tokens']} "
      f"output={p2.last_usage['output_tokens']} total={p2.last_usage['total_tokens']} "
      f"available={p2.last_usage['available']}")
print(f"  extraction content identical : {a.model_dump() == b.model_dump()}")
print(f"  absence recorded as None (not zero) : "
      f"{p2.last_usage['total_tokens'] is None}")

# ---------------------------------------------------------------- artifacts
print("\n[5] FROZEN EXPERIMENT ARTIFACTS")
for f, exp in [("matching_benchmark_v3.json", "4199f5d386e1"),
               ("human_labels_v3.json", "292841efc8b1"),
               ("blind_review_pack_v3.json", "d70aace7ae28")]:
    got = sha_file(f"docs/benchmark/{f}")[:12]
    print(f"  {f:<30}{got} {'UNCHANGED' if got == exp else 'CHANGED'}")
lab = json.loads((REPO / "docs/benchmark/human_labels_v3.json").read_text(encoding="utf-8"))
filled = sum(1 for r in lab["labels"] if r["decision"] is not None)
print(f"  human labels filled            {filled}/{len(lab['labels'])} (must stay 0)")
runsfile = json.loads((REPO / "docs/benchmark/v3_3c_extraction_reproducibility_runs.json").read_text(encoding="utf-8"))
ok = sum(1 for r in runsfile["runs"] if r["success"])
have_usage = sum(1 for r in runsfile["runs"] if "total_tokens" in r)
print(f"  V3.3c runs                     {len(runsfile['runs'])} recorded, {ok} successful")
print(f"  runs carrying token telemetry  {have_usage} (historical runs are NOT backfilled)")

print("\n" + "=" * 72)
print("GATE: BLOCKED -- BENCHMARK RECONCILIATION")
print(f"  reason 1: the frozen benchmark is INTACT and internally consistent;")
print(f"            but {len(unreachable)} of its {len(bench_ids)} cases "
      f"({', '.join(unreachable)}) have no source")
print("            text in collected.json, so the V3.3 26-job experiment")
print("            cannot be completed as specified without a governance ruling.")
print(f"  reason 2: the harness selects jobs by INDEX; its default window also")
print(f"            misses {', '.join(missed_by_default)} (a benchmark case at index 27)")
print("            and would spend 12 calls on 4 non-benchmark postings.")
print("          Extraction must not resume until benchmark governance rules.")
print("=" * 72)