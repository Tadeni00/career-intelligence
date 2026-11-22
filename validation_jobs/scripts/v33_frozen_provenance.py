"""VJ-01..VJ-03 provenance verification. FULLY OFFLINE. No provider calls.

Establishes, for each frozen regression case, whether the exact source text used
to build the frozen benchmark can be proven byte-identical from an immutable
artifact in the repository -- or whether provenance must be recorded as
unresolved.

Evidence classes accepted (governance section 5):
  A. exact source text artifact        -> validation_jobs/VJ-0N_jobN.json
  B. prior extraction-run input        -> checked; V3.3 runs cover no frozen case
  C. benchmark embeds source text      -> checked; benchmark carries no description
  D. verified database snapshot        -> dev DB row accepted ONLY when an
                                          independent artifact pins its bytes

A current database row on its own is never sufficient evidence.
"""

import hashlib
import json
import pathlib
import sys

REPO = pathlib.Path(".")
sys.path.insert(0, str(REPO / "apps/api"))

BENCH = json.loads((REPO / "docs/benchmark/matching_benchmark_v3.json").read_text(encoding="utf-8"))
CASES = {c["job_id"]: c for c in BENCH["cases"]}
FROZEN = ["VJ-01", "VJ-02", "VJ-03"]
ARCHIVE = {"VJ-01": "validation_jobs/VJ-01_job1.json",
           "VJ-02": "validation_jobs/VJ-02_job2.json",
           "VJ-03": "validation_jobs/VJ-03_job3.json"}


def sha(t: str) -> str:
    return hashlib.sha256((t or "").encode("utf-8")).hexdigest()


# Evidence class B: do any recorded extraction runs cover a frozen case?
runs_files = sorted((REPO / "docs/benchmark").glob("*runs*.json")) + \
    sorted((REPO / "docs/benchmark").glob("*extraction_reproducibility*.json"))
run_ids: set[str] = set()
for p in runs_files:
    try:
        o = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    recs = o.get("runs") if isinstance(o, dict) else o
    if isinstance(recs, list):
        run_ids |= {r.get("job_id") for r in recs if isinstance(r, dict)}
evidence_b = sorted(set(FROZEN) & run_ids)

# Evidence class C: does the benchmark embed source text?
evidence_c = {j: ("description" in c) for j, c in CASES.items() if j in FROZEN}

print("=" * 74)
print("VJ-01..VJ-03 PROVENANCE VERIFICATION (offline)")
print("=" * 74)
print(f"\nEvidence class B -- frozen cases present in any recorded extraction run: "
      f"{evidence_b or 'none'}")
print(f"Evidence class C -- benchmark case embeds description text: {evidence_c}")

# dev DB rows (evidence class D requires an independent pin)
from app.db.session import SessionLocal  # noqa: E402
from app.models import Job  # noqa: E402
from sqlalchemy import select  # noqa: E402

db = SessionLocal()
rows = db.execute(select(Job)).scalars().all()

results = {}
for jid in FROZEN:
    case = CASES[jid]
    arch_path = REPO / ARCHIVE[jid]
    print("\n" + "-" * 74)
    print(f"{jid}  ({case['title']} @ {case['company']})")
    print("-" * 74)

    if not arch_path.exists():
        print(f"  archive            : MISSING ({ARCHIVE[jid]})")
        results[jid] = {"provenance_status": "PROVENANCE_UNRESOLVED", "evidence": []}
        continue

    arch = json.loads(arch_path.read_text(encoding="utf-8"))
    a_desc = arch.get("description") or ""
    a_sha, a_len = sha(a_desc), len(a_desc)
    print(f"  archive            : {ARCHIVE[jid]}")
    print(f"    retrieved        : {arch.get('retrieved')}")
    print(f"    posting_updated  : {arch.get('posting_updated')}")
    print(f"    source_url       : {arch.get('source_url')}")
    print(f"    description      : {a_len} chars, sha256 {a_sha}")

    # identity tie between archive and the frozen benchmark case
    id_checks = {
        "title": (arch.get("title"), case.get("title")),
        "company": (arch.get("company"), case.get("company")),
        "location": (arch.get("location"), case.get("location")),
        "source_url": (arch.get("source_url"), case.get("source_url")),
    }
    for field, (a, b) in id_checks.items():
        flag = "MATCH" if a == b else "DIFFER"
        print(f"    identity {field:<12}: {flag}")
    identity_ok = all(a == b for a, b in id_checks.values())

    # dev DB rows matching this case's title+company
    matching = [r for r in rows
                if r.title == case.get("title") and r.company == case.get("company")]
    shas = sorted({sha(r.description or "") for r in matching})
    print(f"  dev DB rows        : {len(matching)} matching title+company")
    print(f"    distinct desc sha: {len(shas)}")
    for s in shas:
        print(f"      {s}  ({(s == a_sha) and '== ARCHIVE' or '!= ARCHIVE'}")
    db_match = bool(matching) and shas == [a_sha]

    status = "VERIFIED" if (identity_ok and db_match) else "PROVENANCE_UNRESOLVED"
    print(f"  --> provenance      : {status}")
    results[jid] = {
        "archive_path": ARCHIVE[jid],
        "archive_retrieved": arch.get("retrieved"),
        "posting_updated": arch.get("posting_updated"),
        "source_url": arch.get("source_url"),
        "source_length": a_len,
        "source_sha256": a_sha,
        "identity_match_benchmark": identity_ok,
        "db_rows_matching": len(matching),
        "db_desc_sha_distinct": shas,
        "db_matches_archive": db_match,
        "provenance_status": status,
        "evidence": (["A: exact source text artifact"] if a_desc else [])
                    + (["C: benchmark embeds source"] if evidence_c.get(jid) else [])
                    + (["D: database snapshot pinned by archive"] if db_match else []),
    }

print("\n" + "=" * 74)
print("SUMMARY")
print("=" * 74)
verified = [j for j in FROZEN if results[j]["provenance_status"] == "VERIFIED"]
unresolved = [j for j in FROZEN if results[j]["provenance_status"] != "VERIFIED"]
for j in FROZEN:
    r = results[j]
    print(f"  {j}: {r['provenance_status']:<22} sha={r.get('source_sha256','-')[:16]}"
          f" evidence={r['evidence'] or 'none'}")
print(f"\n  verified   : {len(verified)}/3 {verified}")
print(f"  unresolved : {len(unresolved)}/3 {unresolved}")

out = REPO / "docs/benchmark/v3_3_frozen_provenance.json"
out.write_text(json.dumps({
    "artifact": "VJ-01..VJ-03 frozen regression provenance",
    "method": "offline; no provider calls",
    "evidence_classes_searched": {
        "A_exact_source_text_artifact": [ARCHIVE[j] for j in FROZEN
                                         if (REPO / ARCHIVE[j]).exists()],
        "B_prior_extraction_run_input": evidence_b,
        "C_benchmark_embeds_source": evidence_c,
        "D_database_snapshot": "accepted only where pinned byte-identically by an archive",
    },
    "governing_rule": ("a current database row alone is never sufficient; it is "
                       "accepted only when an independent immutable artifact "
                       "pins the identical bytes"),
    "results": results,
    "verified_count": len(verified),
    "unresolved_count": len(unresolved),
}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"\nwrote {out}")
