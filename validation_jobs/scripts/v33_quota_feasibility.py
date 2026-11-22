"""V3.3 quota feasibility analysis. READ-ONLY. No experiment, model, prompt or
engine change. Computes token economics from whatever telemetry actually exists.
"""
import collections
import hashlib
import json
import pathlib
import re
import statistics

RUNS = json.loads(pathlib.Path(
    "docs/benchmark/v3_3c_extraction_reproducibility_runs.json").read_text(encoding="utf-8"))
runs = RUNS["runs"]
POSTINGS = {j["job_id"]: j for j in json.loads(
    pathlib.Path("validation_jobs/postings/collected.json").read_text(encoding="utf-8"))}

# --- A. per-call token telemetry -------------------------------------------
# Ask the artifacts what they actually contain. Do not assume.
has_usage = any("usage" in r or "total_tokens" in r for r in runs)
recorded_keys = sorted({k for r in runs for k in r.keys()})
print("=== A. TOKEN TELEMETRY AUDIT ===")
print(f"run record fields containing 'token': "
      f"{[k for k in recorded_keys if 'token' in k] or 'NONE'}")
print("provider captures response.usage     : False "
      "(_json_completion returns json.loads(content) only)")
print(f"per-call usage present in artifact  : {has_usage}")

# The only per-call token figures that exist are Groq's own estimates inside
# 429 denial messages recorded in failure_detail.
denials = []
for r in runs:
    m = re.search(r"Requested (\d+)", r.get("failure_detail") or "")
    if m:
        denials.append(int(m.group(1)))
# Also mine the V3.3b raw artifact for its denial figure.
for name in ("v3_extraction_reproducibility_runs.json",
             "v3_3b_extraction_reproducibility.json"):
    p = pathlib.Path("docs/benchmark") / name
    if p.exists():
        for m in re.finditer(r"Requested (\d+)",
                             p.read_text(encoding="utf-8", errors="replace")):
            denials.append(int(m.group(1)))
print(f"\nper-call token estimates from 429 denials: {denials}")
mean_req = statistics.mean(denials) if denials else None
median_req = statistics.median(denials) if denials else None
print(f"  mean   tokens/call estimate: {mean_req}")
print(f"  median tokens/call estimate: {median_req}")
print("  NOTE: these are estimates for DENIED calls, not confirmed consumption.")
print("  Input-only telemetry      : NOT RECORDED (mean/median/p90 unavailable)")

# Static input-size estimate (deterministic, from frozen artifacts)
PROMPT_CHARS = 5123
BM = json.loads(pathlib.Path(
    "docs/benchmark/matching_benchmark_v3.json").read_text(encoding="utf-8"))
BENCH_IDS = [c["job_id"] for c in BM["cases"]]  # authoritative 26, not collected.json's 28
by_job = collections.defaultdict(list)
for r in runs:
    by_job[r["job_id"]].append(r)
done = {j for j in BENCH_IDS
        if len([x for x in by_job.get(j, []) if x["success"]]) == 3}
remaining = [j for j in BENCH_IDS if j not in done]
print(f"\nbenchmark job count (authoritative): {len(BENCH_IDS)}")
print(f"postings in collected.json         : {len(POSTINGS)} "
      "(contains 2 non-benchmark postings; excluded)")
rem_src = sum(len(POSTINGS[j]["description"]) for j in remaining if j in POSTINGS)
in_postings = [j for j in remaining if j in POSTINGS]
not_in_postings = [j for j in remaining if j not in POSTINGS]
rem_calls = len(remaining) * 3
mean_src = rem_src / len(in_postings) if in_postings else 0
print(f"\nremaining jobs: {len(remaining)}")
print(f"  with source in collected.json : {len(in_postings)} -> {in_postings}")
print(f"  not in collected.json        : {len(not_in_postings)} -> {not_in_postings}")
print("  (frozen VJ-01..03 source text lives in the dev DB, not collected.json)")
print(f"  mean source chars : {mean_src:,.0f}")
print(f"  calls required    : {rem_calls}")
print(f"  mean input chars/call  ~= {(PROMPT_CHARS + mean_src):,.0f}"
      f"  (~{(PROMPT_CHARS + mean_src) / 4:,.0f} tokens at 4 chars/token)")

# --- B. remaining consumption ----------------------------------------------
print("\n=== B. ESTIMATED REMAINING CONSUMPTION ===")
expected = rem_calls * (mean_req or 4416)
conservative = rem_calls * max(denials) if denials else None
worst = rem_calls * (max(denials) if denials else 4556)
print(f"  expected      : {rem_calls} x {mean_req:.0f} = {expected:,.0f} tokens")
print(f"  conservative  : {rem_calls} x {max(denials)} = {conservative:,.0f} tokens")
print(f"  worst observed: {rem_calls} x 4556 = {worst:,.0f} tokens")
DAILY = 200000
print(f"  daily quota   : {DAILY:,}")
print(f"  budgets if entire 200k were available: {expected / DAILY:.2f}")

# --- C. free-tier feasibility ----------------------------------------------
print("\n=== C. FREE-TIER FEASIBILITY ===")
print("Observed successful calls per daily window (this project):")
print("  V3.3b window      : 4 successful calls")
print("  V3.3c window 1    : 12 successful calls")
obs = [4, 12]
print(f"  mean observed/window   : {statistics.mean(obs):.1f}")
print(f"  best observed/window   : {max(obs)}")
print(f"  -> implied experimental budget/window: "
      f"{max(obs) * mean_req:,.0f} tokens ({max(obs)*mean_req/DAILY:.0%} of daily quota)")
for label, per in (("worst observed (4 calls)", 4),
                   ("mean observed (8 calls)", 8),
                   ("best observed (12 calls)", 12)):
    w = expected / (per * mean_req)
    print(f"  windows needed at {label:<26}: {w:.1f} -> {int(-(-w // 1))}")
print("  Counter-observation: 'Used' readings across sessions "
      "(198852, 198923, 197363, 197803) are NOT monotonic,")
print("  so the daily window appears to roll or be shared; a fresh 200k is")
print("  not observed to be available to the experiment alone.")

# --- D. paid tier ----------------------------------------------------------
print("\n=== D. PAID-TIER FEASIBILITY ===")
print("  Cost estimate NOT computed. No verified Groq rate for")
print("  'openai/gpt-oss-120b' on this account is available in-repo or")
print("  from the artifacts, and inventing a price would be fabrication.")
print("  Required to decide: published input/output rate per 1M tokens for")
print("  this model on the account's tier, x ~291,456 tokens.")

# --- integrity -------------------------------------------------------------
code = ["apps/api/app/services/requirements.py", "apps/api/app/services/extraction.py",
        "apps/api/app/ai/openai_provider.py", "apps/api/app/schemas/__init__.py",
        "tests/test_v33_extraction_contract.py", "tests/test_openai_provider.py"]
agg = hashlib.sha256()
for rel in code:
    agg.update(rel.encode())
    agg.update(hashlib.sha256(pathlib.Path(rel).read_bytes()).hexdigest().encode())
print("\n=== INTEGRITY (read-only task) ===")
print(f"  implementation : {agg.hexdigest()[:32]} "
      f"match={agg.hexdigest()[:32] == 'dcc4f506965d57e99bf0bb54bdd1c429'}")
for f, exp in [("matching_benchmark_v3.json", "4199f5d386e1"),
               ("human_labels_v3.json", "292841efc8b1"),
               ("blind_review_pack_v3.json", "d70aace7ae28")]:
    got = hashlib.sha256((pathlib.Path("docs/benchmark") / f).read_bytes()).hexdigest()[:12]
    print(f"  {f:<32}{got} {'UNCHANGED' if got == exp else 'CHANGED'}")
lab = json.loads(pathlib.Path("docs/benchmark/human_labels_v3.json").read_text(encoding="utf-8"))
print(f"  human labels                "
      f"{sum(1 for r in lab['labels'] if r['decision'] is not None)}/23")
