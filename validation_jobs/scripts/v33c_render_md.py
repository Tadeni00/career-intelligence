"""Render Markdown companions for the V3.3c diagnostics."""
import json
import pathlib

B = pathlib.Path("docs/benchmark")

audit = json.loads((B / "vj_b04_forensic_audit.json").read_text(encoding="utf-8"))
table = json.loads((B / "v3_3c_26_job_stability.json").read_text(encoding="utf-8"))

# ---------------------------------------------------------------- VJ-B04 MD
L = ["# VJ-B04 Forensic Audit", "",
     f"Generated {audit['generated_utc']}", "",
     f"Implementation identifier: `{audit['provenance']['implementation_identifier']}`",
     f"Prompt SHA-256: `{audit['provenance']['prompt_sha256']}`",
     f"Experiment artifact SHA-256: `{audit['provenance']['experiment_artifact_sha256'][:32]}`",
     "", "Runs used:", ""]
L += [f"- `{r}`" for r in audit["provenance"]["run_identifiers"]]
L += ["", "Payload hashes (raw provider output, per run):", ""]
L += [f"- run {k}: `{v}`" for k, v in audit["provenance"]["payload_hashes"].items()]

L += ["", "## Counts", "",
      "| | Run 1 | Run 2 | Run 3 |", "|---|---|---|---|",
      f"| raw requirements | {audit['raw_counts']['1']} | {audit['raw_counts']['2']} | {audit['raw_counts']['3']} |",
      f"| canonical requirements | {audit['run_counts']['1']} | {audit['run_counts']['2']} | {audit['run_counts']['3']} |",
      f"| score | {audit['scores']['1']} | {audit['scores']['2']} | {audit['scores']['3']} |",
      f"| recommendation | {audit['recommendations']['1']} | {audit['recommendations']['2']} | {audit['recommendations']['3']} |",
      "", f"Distinct requirements appearing in any run: **{audit['distinct_requirements_across_runs']}**",
      f"Present in all three runs: **{len(audit['stable_all_runs'])}**", ""]

L += ["## Run-3-only requirements", "",
      "| Requirement | Importance | Source context | Evidence in posting |", "|---|---|---|---|"]
for r in audit["matrix"]:
    if r["selection_status"] == "RUN_3_ONLY":
        L.append(f"| {r['requirement'][:58]} | {r['run_3_importance']} | "
                 f"{r['source_context']} | {r['run_3_evidence_in_posting']} |")

L += ["", "## Absent from Run 3", "",
      "| Requirement | Run 1 | Run 2 | Run 3 |", "|---|---|---|---|"]
for r in audit["matrix"]:
    if r["run_3_present"] is False:
        L.append(f"| {r['requirement'][:58]} | {r['run_1_importance']} | "
                 f"{r['run_2_importance']} | - |")

L += ["", "## Run-3-only source context distribution", ""]
for k, v in sorted(audit["run_3_only_source_context_counts"].items(),
                   key=lambda kv: -kv[1]):
    L.append(f"- {k}: {v}")

L += ["", "## Shared-source-quote clusters", "",
      "The same verbatim source quote was emitted under different requirement "
      "names in different runs. These are paraphrase/granularity variants of one "
      "underlying requirement, not new requirements.", "",
      "| Source quote (identical) | Names observed |", "|---|---|"]

clusters: dict[str, set] = {}
for r in audit["matrix"]:
    src = (r["run_3_source"] or r["run_1_source"] or "").strip().lower()
    if not src:
        continue
    if any(r[f"run_{i}_present"] for i in (1, 2, 3)):
        clusters.setdefault(src, set()).add(r["requirement"])
for src, names in clusters.items():
    if len(names) > 1:
        L.append(f"| `{src[:80]}` | " + "<br>".join(sorted(n[:60] for n in names)) + " |")

L += ["", "## Three-way matrix", "",
      "| Requirement | Category | r1 | r1 imp | r2 | r2 imp | r3 | r3 imp | Selection | Classification |",
      "|---|---|---|---|---|---|---|---|---|---|"]
for r in audit["matrix"]:
    L.append(
        f"| {r['requirement'][:44]} | {r['category'] if isinstance(r['category'], str) else ','.join(r['category'])} "
        f"| {'Y' if r['run_1_present'] else '-'} | {r['run_1_importance'] or '-'} "
        f"| {'Y' if r['run_2_present'] else '-'} | {r['run_2_importance'] or '-'} "
        f"| {'Y' if r['run_3_present'] else '-'} | {r['run_3_importance'] or '-'} "
        f"| {r['selection_status']} | {r['classification_status']} |")

(B / "vj_b04_forensic_audit.md").write_text("\n".join(L), encoding="utf-8")

# ------------------------------------------------------------- table MD
agg = table["aggregate"]
T = ["# V3.3c 26-Job Stability Table", "",
     f"Generated {table['generated_utc']}", "",
     f"Status: **{table['status']}**", "",
     "Structural stability requires all three runs to produce an identical "
     "canonical requirement set. Decision stability requires an identical "
     "recommendation; score may vary. Jobs without three successful runs are "
     "`NOT_MEASURABLE` - never zero.", ""]
T += ["## Aggregate dashboard", "", "| Metric | Value |", "|---|---|"]
for k, v in agg.items():
    if k == "rate_note":
        continue
    T.append(f"| {k} | {v} |")
T += [f"| {agg['rate_note']} | |", ""]

cols = ["job_id", "run_1_status", "run_2_status", "run_3_status",
        "run_1_requirement_count", "run_2_requirement_count",
        "run_3_requirement_count", "structural_stability",
        "run_1_score", "run_2_score", "run_3_score", "score_range",
        "run_1_recommendation", "run_2_recommendation", "run_3_recommendation",
        "decision_stability", "added_count", "removed_count", "modified_count",
        "reclassified_count", "diagnostic_class"]
T += ["## Per-job stability", "", "| " + " | ".join(cols) + " |",
      "|" + "---|" * len(cols)]
for r in table["jobs"]:
    T.append("| " + " | ".join(str(r[c]) for c in cols) + " |")

(B / "v3_3c_26_job_stability.md").write_text("\n".join(T), encoding="utf-8")
print("written: vj_b04_forensic_audit.md, v3_3c_26_job_stability.md")