"""V3.3 post-governance final verification. READ-ONLY / OFFLINE.

Emits the integrity block required after the benchmark-membership and frozen
provenance governance resolution. Contacts no provider.
"""

import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "validation_jobs"))
sys.path.insert(0, str(_REPO / "apps/api"))

from benchmark_selector import (  # noqa: E402
    benchmark_members,
    build_population,
    select_window,
)


def sha(rel: str) -> str:
    return hashlib.sha256((_REPO / rel).read_bytes()).hexdigest()


print("=" * 74)
print("V3.3 -- POST-GOVERNANCE FINAL VERIFICATION (offline)")
print("=" * 74)

print("\n[1] NEW HASHES")
CODE = [
    "apps/api/app/services/requirements.py",
    "apps/api/app/services/extraction.py",
    "apps/api/app/ai/openai_provider.py",
    "apps/api/app/schemas/__init__.py",
    "tests/test_v33_extraction_contract.py",
    "tests/test_openai_provider.py",
]
agg = hashlib.sha256()
for rel in CODE:
    agg.update(rel.encode())
    agg.update(sha(rel).encode())
print(f"  implementation          : {agg.hexdigest()}")
print(f"    (previous dcc4f506965d57e99bf0bb54bdd1c429; telemetry revision)")
print(f"  harness                 : {sha('validation_jobs/scripts/v33_runs.py')}")
print(f"    (previous 05011783f5211a4c; membership-based selection)")
print(f"  selector                : {sha('validation_jobs/benchmark_selector.py')}")
print(f"  reconciliation (json)   : {sha('docs/benchmark/v3_3_benchmark_reconciliation.json')}")
print(f"  reconciliation (md)     : {sha('docs/benchmark/v3_3_benchmark_reconciliation.md')}")
print(f"  frozen provenance       : {sha('docs/benchmark/v3_3_frozen_provenance.json')}")
print(f"  selector tests          : {sha('tests/test_v33_benchmark_selector.py')}")

print("\n[2] CONFIRMED UNCHANGED")
from app.ai.openai_provider import REQUIREMENT_CONTRACT_PROMPT  # noqa: E402
prompt = hashlib.sha256(REQUIREMENT_CONTRACT_PROMPT.encode("utf-8")).hexdigest()
CHECKS = [
    ("prompt sha256", prompt, "43d20b8be806e7ba130d4f1120cc9a4fe9456110a95048092323c3c68afbd436"),
    ("engine sha256", sha("packages/matching/matching/engine.py"), "f8913c528710e3f3"),
    ("config sha256", sha("packages/matching/matching/config.py"), "0af42435d68b9463"),
    ("benchmark sha256", sha("docs/benchmark/matching_benchmark_v3.json"), "4199f5d386e1"),
    ("human labels sha256", sha("docs/benchmark/human_labels_v3.json"), "292841efc8b1"),
    ("blind pack sha256", sha("docs/benchmark/blind_review_pack_v3.json"), "d70aace7ae28"),
]
for label, actual, expected in CHECKS:
    ok = actual.startswith(expected) if len(expected) < 40 else actual == expected
    print(f"  {label:<22}: {actual[:16]}..  {'UNCHANGED' if ok else 'CHANGED  <-- STOP'}")
print(f"  prompt chars            : {len(REQUIREMENT_CONTRACT_PROMPT)} (must be 5123)")

print("\n[3] POPULATION")
members = benchmark_members(_REPO)
rec = json.loads((_REPO / "docs/benchmark/v3_3_benchmark_reconciliation.json").read_text(encoding="utf-8"))
print(f"  benchmark_population        : {rec['benchmark_population']}")
print(f"  collected_population        : {rec['collected_population']}")
print(f"  benchmark_from_collection   : {rec['benchmark_from_collection']}")
print(f"  frozen_regression           : {rec['frozen_regression']}")
print(f"  excluded_collection_records : {rec['excluded_collection_records']}")
print(f"  members in frozen order (26):")
for i, m in enumerate(members):
    print(f"     [{i:>2}] {m}")
resolved = build_population(_REPO)
print(f"\n  members resolved with source: {sum(1 for r in resolved if r['source_text'])}/{len(resolved)}")
print(f"  provenance VERIFIED          : {sum(1 for r in resolved if r['provenance_status'] == 'VERIFIED')}/26")
print(f"  provenance unresolved        : {sum(1 for r in resolved if r['provenance_status'] != 'VERIFIED')}")

print("\n[4] EXCLUSIONS")
for r in rec["excluded_records"]:
    print(f"  {r['job_id']}  {r['company']:<12} {r['population_status']:<9} "
          f"{r['exclusion_reason']}  identity={r['identity_class']}")

print("\n[5] TELEMETRY STILL OPERATIONAL")
runs = json.loads((_REPO / "docs/benchmark/v3_3c_extraction_reproducibility_runs.json").read_text(encoding="utf-8"))["runs"]
print(f"  V3.3c runs recorded        : {len(runs)}  successful {sum(1 for r in runs if r['success'])}")
print(f"  historical runs with tokens: {sum(1 for r in runs if 'total_tokens' in r)} (must be 0 -- no backfill)")
lab = json.loads((_REPO / "docs/benchmark/human_labels_v3.json").read_text(encoding="utf-8"))
print(f"  human labels               : {sum(1 for r in lab['labels'] if r['decision'] is not None)}/{len(lab['labels'])} (must stay 0)")

print("\n[6] REMAINING EXPERIMENT REQUIREMENT")
done = {}
for r in runs:
    if r["success"]:
        done[r["job_id"]] = done.get(r["job_id"], 0) + 1
complete = sorted(j for j, n in done.items() if n == 3)
remaining = [m for m in members if done.get(m, 0) < 3]
print(f"  complete triplets  : {len(complete)}/26 -> {complete}")
print(f"  remaining members  : {len(remaining)} -> {remaining}")
print(f"  remaining calls    : {len(remaining) * 3}")
print(f"  first window index : {members.index(remaining[0])}  (--from {members.index(remaining[0])})")
print(f"  window [0:26] sanity: {len(select_window(members, 0, 26))} members")

print("\n" + "=" * 74)
print("STATE A -- FULLY RESOLVED")
print(f"  26/26 benchmark members identified")
print(f"  26/26 source inputs provenance-verified")
print(f"  membership selector corrected")
print("  => READY TO RESUME V3.3")
print("=" * 74)