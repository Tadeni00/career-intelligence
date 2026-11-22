"""V3.3 benchmark population reconciliation. FULLY OFFLINE / READ-ONLY.

Authoritative population record for the V3.3 experiment, produced under the
governance ruling that the experimental population is explicit membership in the
frozen benchmark.

Headline counts:
    benchmark_population          = 26
    collected_population          = 28
    benchmark_from_collection     = 23
    frozen_regression             = 3
    excluded_collection_records   = 5

Every benchmark member carries an explicit population_status, source_status,
source_origin, source_sha256 and provenance_status. Unresolved provenance is
written as the literal token PROVENANCE_UNRESOLVED -- never as an empty string.

Reads the frozen benchmark; never modifies it. Contacts no provider.
"""

import collections
import hashlib
import json
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO / "validation_jobs"))

from benchmark_selector import (  # noqa: E402
    COLLECTED_RELPATH,
    benchmark_members,
    build_population,
    is_member,
    load_provenance,
)

BENCH_PATH = _REPO / "docs/benchmark/matching_benchmark_v3.json"
OUT_JSON = _REPO / "docs/benchmark/v3_3_benchmark_reconciliation.json"
OUT_MD = _REPO / "docs/benchmark/v3_3_benchmark_reconciliation.md"

FROZEN_BENCH_SHA_PREFIX = "4199f5d386e1"
CAP_PER_COMPANY = 2
EXCLUSION_REASON = "EXCLUDED_BY_PER_COMPANY_CAP"

bench = json.loads(BENCH_PATH.read_text(encoding="utf-8"))
bench_sha = hashlib.sha256(BENCH_PATH.read_bytes()).hexdigest()
collected = json.loads((_REPO / COLLECTED_RELPATH).read_text(encoding="utf-8"))
members = benchmark_members(_REPO)
provenance = load_provenance(_REPO)

resolved = {r["job_id"]: r for r in build_population(_REPO)}


def text_hash(j):
    return hashlib.sha256((j.get("description") or "").encode("utf-8")).hexdigest()


# --- replay the documented selection rule ------------------------------------
rule_selected, per_company = [], collections.Counter()
for job in collected:
    key = (job.get("company") or "").strip().lower()
    if per_company[key] >= CAP_PER_COMPANY:
        continue
    per_company[key] += 1
    rule_selected.append(job["job_id"])
rule_selected_set = set(rule_selected)

collected_ids = {j["job_id"] for j in collected}
collected_backed = [m for m in members if m in collected_ids]
frozen_regression = [m for m in members if m not in collected_ids]

# --- identity audit ----------------------------------------------------------
by_url, by_hash, by_title = (collections.defaultdict(list),
                             collections.defaultdict(list),
                             collections.defaultdict(list))
for j in collected:
    by_url[(j.get("url") or "").strip()].append(j["job_id"])
    by_hash[text_hash(j)].append(j["job_id"])
    by_title[((j.get("title") or "").strip().lower(),
              (j.get("company") or "").strip().lower())].append(j["job_id"])

dup_urls = {k: v for k, v in by_url.items() if len(v) > 1}
dup_hashes = {k: v for k, v in by_hash.items() if len(v) > 1}
dup_titles = {k: v for k, v in by_title.items() if len(v) > 1}

# --- the 26 benchmark members ------------------------------------------------
member_records = []
for job_id in members:
    case = next(c for c in bench["cases"] if c["job_id"] == job_id)
    r = resolved[job_id]
    is_frozen = job_id in frozen_regression
    member_records.append({
        "job_id": job_id,
        "title": case.get("title"),
        "company": case.get("company"),
        "population_status": "BENCHMARK_MEMBER",
        "member_class": "FROZEN_REGRESSION" if is_frozen else "COLLECTED_BACKED",
        "source_status": r["source_status"],
        "source_sha256": r["source_sha256"],
        "source_length": r["source_length"],
        "source_origin": r["source_origin"],
        "provenance_status": r["provenance_status"],
        "source_url": case.get("source_url"),
        "provenance_evidence": (provenance.get(job_id, {}) or {}).get("evidence", []),
    })

# --- the 5 excluded collected records ----------------------------------------
excluded_records = []
for j in collected:
    jid = j["job_id"]
    if is_member(jid, members):
        continue
    company = (j.get("company") or "").strip()
    kept = [c["job_id"] for c in bench["cases"]
            if (c.get("company") or "").strip().lower() == company.lower()]
    th = text_hash(j)
    identity = "DISTINCT"
    if len(by_url[(j.get("url") or "").strip()]) > 1:
        identity = "DUPLICATE_URL"
    elif len(by_hash[th]) > 1:
        identity = "DUPLICATE_POSTING_TEXT"
    elif len(by_title[((j.get("title") or "").strip().lower(),
                       company.lower())]) > 1:
        identity = "DUPLICATE_TITLE_COMPANY"
    excluded_records.append({
        "job_id": jid,
        "title": j.get("title"),
        "company": company,
        "population_status": "EXCLUDED",
        "exclusion_reason": EXCLUSION_REASON,
        "exclusion_detail": (
            f"selection keeps the first {CAP_PER_COMPANY} postings per employer "
            f"in collected.json file order; {company} contributed "
            f"{len(kept)} benchmark case(s) ({', '.join(kept)}) and this posting "
            f"appears later in file order"),
        "member_class": "NOT_IN_BENCHMARK",
        "source_status": "NOT_APPLICABLE",
        "source_sha256": th,
        "source_length": len(j.get("description") or ""),
        "source_origin": COLLECTED_RELPATH,
        "provenance_status": "NOT_APPLICABLE",
        "identity_class": identity,
        "source_url": j.get("url"),
    })

verified = [m for m in member_records if m["provenance_status"] == "VERIFIED"]
unresolved = [m for m in member_records if m["provenance_status"] != "VERIFIED"]

summary = {
    "artifact": "V3.3 benchmark population reconciliation",
    "governance": ("the V3.3 experimental population is explicit membership in "
                   "the frozen benchmark; collection index ranges are not a "
                   "population definition"),
    "generated_offline": True,
    "provider_calls": 0,
    "extraction_results_modified": 0,
    "frozen_benchmark_modified": False,

    "benchmark_population": len(members),
    "collected_population": len(collected),
    "benchmark_from_collection": len(collected_backed),
    "frozen_regression": len(frozen_regression),
    "excluded_collection_records": len(excluded_records),

    "population_verified": len(verified),
    "population_provenance_unresolved": len(unresolved),
    "runnable_population": len(member_records) - len(unresolved),

    "benchmark": {
        "path": "docs/benchmark/matching_benchmark_v3.json",
        "benchmark_version": bench.get("version"),
        "benchmark_sha256": bench_sha,
        "benchmark_sha256_frozen_expected_prefix": FROZEN_BENCH_SHA_PREFIX,
        "benchmark_sha256_unchanged": bench_sha.startswith(FROZEN_BENCH_SHA_PREFIX),
        "benchmark_total_cases": len(bench["cases"]),
        "population_order": "the frozen benchmark's own case order",
        "population_order_ids": members,
    },
    "collected": {
        "path": COLLECTED_RELPATH,
        "posting_count": len(collected),
        "posting_id_range": [collected[0]["job_id"], collected[-1]["job_id"]],
    },
    "selection_rule": {
        "source": "validation_jobs/scripts/v3_benchmark_build.py:58-66",
        "description": (f"Iterate collected.json in file order; keep the first "
                        f"{CAP_PER_COMPANY} postings per employer (employer key "
                        f"lowercased); cap stops one employer's ladder dominating."),
        "cap_per_company": CAP_PER_COMPANY,
        "reproduced_selection": rule_selected,
        "reproduces_frozen_benchmark_exactly": set(rule_selected) == set(collected_backed),
        "mismatches": sorted(set(rule_selected) ^ set(collected_backed)),
    },
    "identity_audit": {
        "duplicate_urls": dup_urls,
        "duplicate_posting_texts": {k: v for k, v in dup_hashes.items()},
        "duplicate_title_company": {str(k): v for k, v in dup_titles.items()},
        "duplicate_url_count": len(dup_urls),
        "duplicate_posting_text_count": len(dup_hashes),
        "note": ("No duplicate source URLs across the 28 collected postings. One "
                 "identical posting-text hash pair exists (same employer, two "
                 "different URLs); both are distinct benchmark members, so this "
                 "is a source-side duplicate listing, not a benchmark defect."),
    },
    "frozen_regression_provenance": {
        "cases": frozen_regression,
        "evidence_classes_searched": ["A exact source text artifact",
                                      "B prior extraction-run input",
                                      "C benchmark embeds source text",
                                      "D database snapshot pinned by archive"],
        "governing_rule": ("a current database row alone is never sufficient; it "
                           "is accepted only where an independent immutable "
                           "archive pins byte-identical text"),
        "results": {
            job_id: {
                "provenance_status": provenance.get(job_id, {}).get(
                    "provenance_status", "PROVENANCE_UNRESOLVED"),
                "source_sha256": provenance.get(job_id, {}).get("source_sha256"),
                "source_length": provenance.get(job_id, {}).get("source_length"),
                "archive_path": provenance.get(job_id, {}).get("archive_path"),
                "archive_retrieved": provenance.get(job_id, {}).get("archive_retrieved"),
                "evidence": provenance.get(job_id, {}).get("evidence", []),
            } for job_id in frozen_regression
        },
    },
    "harness_selector": {
        "module": "validation_jobs/benchmark_selector.py",
        "definition": "explicit benchmark membership -> job ids -> provenance-checked source",
        "window_indices_address": "ordered benchmark member ids",
        "collection_index_used_as_population": False,
        "rejects_non_members": True,
        "tests": "tests/test_v33_benchmark_selector.py",
    },
    "benchmark_members": member_records,
    "excluded_records": excluded_records,
}

OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")

# ------------------------------------------------------------------ markdown
lines = [
    "# V3.3 Benchmark Population Reconciliation",
    "",
    "Offline. **No provider calls. No extraction result modified. Frozen benchmark",
    "unmodified.** The V3.3 experimental population is explicit membership in the",
    "frozen benchmark, not a collection index range.",
    "",
    "## Headline counts",
    "",
    "| quantity | value |",
    "| --- | ---: |",
    f"| `benchmark_population` | {len(members)} |",
    f"| `collected_population` | {len(collected)} |",
    f"| `benchmark_from_collection` | {len(collected_backed)} |",
    f"| `frozen_regression` | {len(frozen_regression)} |",
    f"| `excluded_collection_records` | {len(excluded_records)} |",
    "",
    f"Arithmetic: {len(collected_backed)} + {len(frozen_regression)} = "
    f"{len(collected_backed) + len(frozen_regression)} "
    f"{'== benchmark_population OK' if len(collected_backed) + len(frozen_regression) == len(members) else 'MISMATCH'}"
    f"; and {len(collected_backed)} + {len(excluded_records)} = "
    f"{len(collected_backed) + len(excluded_records)} "
    f"{'== collected_population OK' if len(collected_backed) + len(excluded_records) == len(collected) else 'MISMATCH'}",
    "",
    "## Frozen benchmark",
    "",
    f"- sha256 `{bench_sha}` — "
    f"{'UNCHANGED' if bench_sha.startswith(FROZEN_BENCH_SHA_PREFIX) else 'CHANGED'}",
    f"- cases {len(bench['cases'])}; population order is the benchmark's own case order",
    "",
    "## Benchmark members (26)",
    "",
    "| # | job_id | class | source_status | provenance_status | source_len | source_origin |",
    "| ---: | --- | --- | --- | --- | ---: | --- |",
]
for i, m in enumerate(member_records):
    lines.append(f"| {i} | {m['job_id']} | {m['member_class']} | {m['source_status']} | "
                 f"{m['provenance_status']} | {m['source_length']} | `{m['source_origin']}` |")

lines += [
    "",
    f"Population provenance-verified: **{len(verified)}/{len(member_records)}**; "
    f"unresolved: {len(unresolved)}.",
    "",
    "## Excluded collected records (5)",
    "",
    "| job_id | employer | population_status | exclusion_reason | identity |",
    "| --- | --- | --- | --- | --- |",
]
for r in excluded_records:
    lines.append(f"| {r['job_id']} | {r['company']} | {r['population_status']} | "
                 f"`{r['exclusion_reason']}` | {r['identity_class']} |")

lines += [
    "",
    "### Per-exclusion detail",
    "",
]
for r in excluded_records:
    lines += [f"**{r['job_id']}** — {r['title']} ({r['company']})  ",
              f"- url : {r['source_url']}",
              f"- posting text sha256 : `{r['source_sha256']}`",
              f"- identity : {r['identity_class']}",
              f"- reason : {r['exclusion_detail']}", ""]

lines += [
    "## Frozen regression provenance",
    "",
    "Governing rule: " + summary["frozen_regression_provenance"]["governing_rule"] + ".",
    "",
    "| job_id | provenance_status | source_sha256 | len | archive | retrieved | evidence |",
    "| --- | --- | --- | ---: | --- | --- | --- |",
]
for job_id, r in summary["frozen_regression_provenance"]["results"].items():
    lines.append(
        f"| {job_id} | {r['provenance_status']} | `{(r['source_sha256'] or '')[:16]}..` | "
        f"{r['source_length']} | `{r['archive_path']}` | {r['archive_retrieved']} | "
        f"{'; '.join(r['evidence'])} |")

lines += [
    "",
    "Evidence classes searched: A exact source text artifact; B prior",
    "extraction-run input (no frozen case appears in any recorded run);",
    "C benchmark embeds source text (it does not); D database snapshot accepted",
    "only where an independent archive pins byte-identical text.",
    "",
    "## Identity audit across all 28 collected postings",
    "",
    f"- duplicate source URLs : {len(dup_urls)}",
    f"- duplicate posting texts : {len(dup_hashes)} "
    f"{ {k[:16] + '..': v for k, v in dup_hashes.items()} or ''}",
    f"- duplicate title+employer : {len(dup_titles)}",
    "",
    summary["identity_audit"]["note"],
    "",
    "## Harness selector",
    "",
    f"- module : `{summary['harness_selector']['module']}`",
    f"- definition : {summary['harness_selector']['definition']}",
    f"- `--from/--to` address : {summary['harness_selector']['window_indices_address']}",
    f"- collection index used as population : "
    f"{summary['harness_selector']['collection_index_used_as_population']}",
    f"- tests : `{summary['harness_selector']['tests']}`",
    "",
]
OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"benchmark sha256 {bench_sha} "
      f"{'UNCHANGED' if bench_sha.startswith(FROZEN_BENCH_SHA_PREFIX) else 'CHANGED'}")
print(f"benchmark_population        = {len(members)}")
print(f"collected_population        = {len(collected)}")
print(f"benchmark_from_collection   = {len(collected_backed)}")
print(f"frozen_regression           = {len(frozen_regression)}")
print(f"excluded_collection_records = {len(excluded_records)}")
print(f"provenance verified         = {len(verified)}/{len(member_records)}")
print(f"provenance unresolved       = {len(unresolved)} {[m['job_id'] for m in unresolved] or 'none'}")
print(f"selection rule exact        = {summary['selection_rule']['reproduces_frozen_benchmark_exactly']}")
print(f"excluded ids                = {[r['job_id'] for r in excluded_records]}")
print(f"wrote {OUT_JSON}")
print(f"wrote {OUT_MD}")
