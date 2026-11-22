/**
 * Focused checks for the tailored-CV routing rules.
 *
 * Run with:  node src/tailoredCvRouting.test.ts      (no test framework needed)
 * Also type-checked by `tsc -b`, because tsconfig.app.json includes src/.
 */
import {
  applicationMaterialsTarget,
  belongsToJob,
  resolveTailoredCVTarget,
  selectJobCVs,
  targetPath,
} from "./tailoredCvRouting.ts";
import type { TailoredCV } from "./types.ts";

// tsconfig.app.json only loads "vite/client" types, so Node's global is declared
// narrowly here rather than widening the project's compiler options.
declare const process: { exit(code: number): void };

let failures = 0;

function check(name: string, actual: unknown, expected: unknown): void {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) {
    console.log(`  PASS  ${name}`);
  } else {
    failures += 1;
    console.log(`  FAIL  ${name}\n          expected ${e}\n          actual   ${a}`);
  }
}

function doc(id: number, job_id: number, extra: Partial<TailoredCV> = {}): TailoredCV {
  return {
    id,
    candidate_id: 1,
    job_id,
    source_cv_id: null,
    cv_profile_id: null,
    version: 1,
    filename: `cv-${id}.docx`,
    storage_path: `/tmp/cv-${id}.docx`,
    summary: null,
    analysis: null,
    changes_summary: [],
    validation_status: "VALID",
    validation_issues: [],
    created_at: "2026-01-01T00:00:00Z",
    ...extra,
  };
}

console.log("\n1. Job id 13 opens the workflow for job 13, even though CV 13 exists");
check(
  "resolve({ jobId: '13' }) is a job target",
  resolveTailoredCVTarget({ jobId: "13" }),
  { kind: "job", jobId: 13 }
);
check(
  "its href is the job-scoped route",
  targetPath(resolveTailoredCVTarget({ jobId: "13" })),
  "/jobs/13/tailored-cv"
);

console.log("\n2. /tailored-cvs/13 retrieves CV 13, not job 13's CV");
check(
  "resolve({ id: '13' }) is a document target",
  resolveTailoredCVTarget({ id: "13" }),
  { kind: "document", docId: 13 }
);
check(
  "its href is the document route",
  targetPath(resolveTailoredCVTarget({ id: "13" })),
  "/tailored-cvs/13"
);
const cv13 = doc(13, 6); // CV 13 belongs to job 6, not job 13
const job13Cvs = selectJobCVs([cv13], 13);
check("CV 13 is not offered as job 13's CV", job13Cvs, []);
check("CV 13 is correctly recognised as job 6's", belongsToJob(cv13, 6), true);
check(
  "the same numeric id resolves to different routes",
  [targetPath(resolveTailoredCVTarget({ id: "13" })), targetPath(resolveTailoredCVTarget({ jobId: "13" }))],
  ["/tailored-cvs/13", "/jobs/13/tailored-cv"]
);

console.log("\n3. The job-scoped workflow lists only CVs for its own job");
const mixed = [doc(1, 5), doc(2, 6), doc(3, 6), doc(4, 7)];
check("job 6 sees only its two CVs", selectJobCVs(mixed, 6).map((d) => d.id), [2, 3]);
check("job 5 sees only its one CV", selectJobCVs(mixed, 5).map((d) => d.id), [1]);
check("an unrelated job sees none", selectJobCVs(mixed, 99), []);

console.log("\n4. Generating from job 13 associates the document with job 13");
const generated = doc(18, 13, { version: 1, validation_status: "VALID" });
check("the generated doc belongs to job 13", belongsToJob(generated, 13), true);
check("and appears in job 13's list", selectJobCVs([generated, cv13], 13).map((d) => d.id), [18]);
check("job 6's list is unaffected", selectJobCVs([generated, cv13], 6).map((d) => d.id), [13]);

console.log("\n5. Application links use a real tailored-CV id, never an application id");
function applicationHref(app: { job_id: number; tailored_cv_id: number | null }): string {
  const t = applicationMaterialsTarget(app);
  return t.kind === "document" ? `/tailored-cvs/${t.docId}` : `/jobs/${t.jobId}/tailored-cv`;
}
check(
  "with a tailored CV, use the document route",
  applicationHref({ job_id: 13, tailored_cv_id: 4 }),
  "/tailored-cvs/4"
);
const noCv = applicationMaterialsTarget({ job_id: 13, tailored_cv_id: null });
check(
  "without one, fall back to the application's job, not its id",
  applicationHref({ job_id: 13, tailored_cv_id: null }),
  "/jobs/13/tailored-cv"
);
check(
  "an application id is never used as a document id",
  applicationHref({ job_id: 13, tailored_cv_id: null }).includes("/tailored-cvs/"),
  false
);
check(
  "the fallback target is the job, carrying no document id",
  noCv.kind === "job" && noCv.jobId === 13,
  true
);

console.log("\n6. Missing/invalid entities are reported, never silently substituted");
check("non-numeric job id is invalid", resolveTailoredCVTarget({ jobId: "abc" }).kind, "invalid");
check("non-numeric document id is invalid", resolveTailoredCVTarget({ id: "abc" }).kind, "invalid");
check("zero is rejected", resolveTailoredCVTarget({ jobId: "0" }).kind, "invalid");
check("negative is rejected", resolveTailoredCVTarget({ id: "-5" }).kind, "invalid");
check("float is rejected", resolveTailoredCVTarget({ id: "1.5" }).kind, "invalid");
check("empty is rejected", resolveTailoredCVTarget({ id: "" }).kind, "invalid");
check("no params is invalid", resolveTailoredCVTarget({}).kind, "invalid");
check("invalid targets have no href", targetPath(resolveTailoredCVTarget({ id: "abc" })), null);
check(
  "a missing document is never resolvable as a job",
  resolveTailoredCVTarget({ id: "9999" }),
  { kind: "document", docId: 9999 }
);
check(
  "a missing job is never resolvable as a document",
  resolveTailoredCVTarget({ jobId: "9999" }),
  { kind: "job", jobId: 9999 }
);

console.log(
  failures === 0
    ? "\nAll routing checks passed.\n"
    : `\n${failures} routing check(s) FAILED.\n`
);
process.exit(failures === 0 ? 0 : 1);
