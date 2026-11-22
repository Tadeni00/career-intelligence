"""V3 Phase 2 — collect REAL job postings for benchmark expansion.

Sources are public job-board APIs returning genuine postings. Nothing here
synthesises a posting: every record keeps its original URL, company, location
and description text so it can be re-verified.
"""
import json
import pathlib
import re

import httpx

OUT = pathlib.Path("validation_jobs/postings")
OUT.mkdir(parents=True, exist_ok=True)

HEADERS = {"User-Agent": "career-intelligence-benchmark/1.0 (research)"}
TERMS = (
    "data scientist", "data analyst", "machine learning", "ml engineer",
    "analytics engineer", "data engineer", "ai engineer", "statistician",
    "business intelligence", "computer vision", "nlp", "deep learning",
    "data science", "quantitative", "research scientist",
)
BAD = ("sales", "marketing", "recruiter", "customer support", "account executive")


def strip_html(text: str) -> str:
    text = re.sub(r"<script.*?</script>", " ", text or "", flags=re.S | re.I)
    text = re.sub(r"<style.*?</style>", " ", text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = (
        text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<")
        .replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"')
    )
    return re.sub(r"\s{2,}", " ", text).strip()


def relevant(title: str) -> bool:
    low = (title or "").lower()
    if any(b in low for b in BAD):
        return False
    return any(t in low for t in TERMS)


def fetch_remotive() -> list[dict]:
    out: list[dict] = []
    r = httpx.get("https://remotive.com/api/remote-jobs?limit=200",
                  headers=HEADERS, timeout=45, follow_redirects=True)
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        if not relevant(j.get("title")):
            continue
        out.append({
            "source": "remotive",
            "title": (j.get("title") or "").strip(),
            "company": (j.get("company_name") or "").strip(),
            "location": (j.get("candidate_required_location") or "Remote").strip(),
            "url": j.get("url") or "",
            "remote": True,
            "description": strip_html(j.get("description") or ""),
            "salary_min": _num(j.get("salary_min")),
            "salary_max": _num(j.get("salary_max")),
        })
    return out


def fetch_arbeitnow() -> list[dict]:
    out: list[dict] = []
    r = httpx.get("https://www.arbeitnow.com/api/job-board-api",
                  headers=HEADERS, timeout=45, follow_redirects=True)
    r.raise_for_status()
    for j in r.json().get("data", []):
        if not relevant(j.get("title")):
            continue
        out.append({
            "source": "arbeitnow",
            "title": (j.get("title") or "").strip(),
            "company": (j.get("company_name") or "").strip(),
            "location": (j.get("location") or "Remote").strip(),
            "url": j.get("url") or "",
            "remote": "remote" in (j.get("location") or "").lower(),
            "description": strip_html(j.get("description") or ""),
            "salary_min": None,
            "salary_max": None,
        })
    return out


def fetch_jobicy() -> list[dict]:
    out: list[dict] = []
    r = httpx.get("https://jobicy.com/api/v2/remote-jobs?count=100",
                  headers=HEADERS, timeout=45, follow_redirects=True)
    r.raise_for_status()
    for j in r.json().get("jobs", []):
        if not relevant(j.get("jobTitle")):
            continue
        cats = j.get("jobCategories") or {}
        desc = strip_html((j.get("jobDescription") or "").replace(
            "<article>", "").replace("</article>", ""))
        out.append({
            "source": "jobicy",
            "title": (j.get("jobTitle") or "").strip(),
            "company": (j.get("companyName") or "").strip(),
            "location": ", ".join(cats.get("location") or []) or "Remote",
            "url": j.get("url") or "",
            "remote": True,
            "description": desc,
            "salary_min": _annual(cats.get("salary")),
            "salary_max": None,
        })
    return out


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _annual(salary):
    if isinstance(salary, list) and salary:
        return _num(salary[0])
    return _num(salary)


sources = {
    "remotive": fetch_remotive,
    "arbeitnow": fetch_arbeitnow,
    "jobicy": fetch_jobicy,
}

collected: list[dict] = []
errors: dict[str, str] = {}
for name, fn in sources.items():
    try:
        got = fn()
        collected.extend(got)
        print(f"{name}: {len(got)} relevant postings")
    except Exception as exc:  # noqa: BLE001 - report and continue
        errors[name] = f"{type(exc).__name__}: {exc}"
        print(f"{name}: FAILED {type(exc).__name__}")

# De-duplicate on (title, company).
seen: set[tuple[str, str]] = set()
unique: list[dict] = []
for job in collected:
    key = (job["title"].lower().strip(), job["company"].lower().strip())
    if key in seen or len(job["description"]) < 200:
        continue
    seen.add(key)
    job["job_id"] = f"VJ-B{len(unique) + 1:02d}"
    unique.append(job)

print(f"\ncollected: {len(collected)}  usable: {len(unique)}")
for job in unique:
    print(f"  {job['job_id']:<8}{job['title'][:52]:<54}"
          f"{job['company'][:20]:<22}{job['location'][:30]}")

(OUT / "collected.json").write_text(
    json.dumps(unique, indent=2, ensure_ascii=False), encoding="utf-8")
if errors:
    print("\nsource errors:", json.dumps(errors, indent=2))