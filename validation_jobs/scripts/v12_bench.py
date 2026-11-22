"""V1.2 benchmark on the three benchmark jobs (spec section 24)."""
import json, pathlib, statistics

from app.schemas import ProfileSummary
from app.services.validation import is_soft_signal, validate_cover_letter

profile = ProfileSummary.model_validate(
    json.loads(pathlib.Path("val_profile_fixed.json").read_text(encoding="utf-8")))
res = json.loads(pathlib.Path("validation_jobs/_results.json").read_text(encoding="utf-8"))
base = {"VJ-01": "MAYBE", "VJ-02": "NO", "VJ-03": "YES"}
BEFORE = {"VJ-01": 16, "VJ-02": 10, "VJ-03": 13}

rows = []
for k, v in res.items():
    meta = v["meta"]
    p = pathlib.Path(f"validation_jobs/{k}_coverletter.txt")
    letter = p.read_text(encoding="utf-8") if p.exists() else ""
    r = validate_cover_letter(letter, profile, meta["title"], meta["company"])
    safety = [i for i in r.issues if i.code in
              ("SUSPICIOUS_OUTPUT", "UNSUPPORTED_CONTACT", "UNSUPPORTED_ELIGIBILITY")]
    rows.append({
        "job": k, "human": base[k], "rec": v["match"]["recommendation"],
        "before": BEFORE[k], "after": len(r.issues),
        "hard": sum(1 for i in r.issues if i.severity == "error"),
        "review": sum(1 for i in r.issues if i.severity == "warning"),
        "critical": sum(1 for i in r.issues if i.claim_severity == "CRITICAL"),
        "safety": len(safety), "status": r.status.value,
        "soft": [g for g in v["match"]["gaps"] if is_soft_signal(g)],
    })

out = ["# V1.2 benchmark - 3 real jobs, unchanged candidate evidence", "",
       f"{'job':<7}{'human':<7}{'rec':<21}{'before':>7}{'after':>7}{'hard':>6}"
       f"{'review':>8}{'crit':>6}{'safety':>8}  status"]
for r in rows:
    out.append(f"{r['job']:<7}{r['human']:<7}{r['rec']:<21}{r['before']:>7}"
               f"{r['after']:>7}{r['hard']:>6}{r['review']:>8}{r['critical']:>6}"
               f"{r['safety']:>8}  {r['status']}")
b = [r["before"] for r in rows]; a = [r["after"] for r in rows]
out += ["", f"average findings/document before : {statistics.mean(b):.1f}",
        f"average findings/document after  : {statistics.mean(a):.1f}",
        f"reduction                         : {100*(1-statistics.mean(a)/statistics.mean(b)):.0f}%",
        f"ambiguity (review) findings      : {sum(r['review'] for r in rows)}",
        f"hard failures                     : {sum(r['hard'] for r in rows)}",
        f"critical safety findings          : {sum(r['critical'] for r in rows)}",
        f"soft-signal gaps penalised        : {sum(len(r['soft']) for r in rows)}"]
pathlib.Path("validation_jobs/_v12_benchmark.txt").write_text("\n".join(out), encoding="utf-8")
print("\n".join(out))