import { salaryLabel, workArrangementLabel } from "./jobMetadataLabels.ts";
import type { Job } from "./types.ts";

function assert(name: string, good: boolean) {
  if (!good) throw new Error("FAIL " + name);
  console.log("PASS " + name);
}
const job = (min: number | null, max: number | null) =>
  ({ salary_min: min, salary_max: max } as Job);
assert("unknown work arrangement not guessed as on-site",
  workArrangementLabel(null) === "Work arrangement not stated");
assert("remote never means worldwide eligibility",
  workArrangementLabel("REMOTE").includes("country restrictions unverified"));
assert("on-site only for explicitly provided on-site evidence",
  workArrangementLabel("ONSITE") === "On-site");
assert("no salary shows unknown", salaryLabel(job(null, null)) === "Salary not stated");
assert("zero salary is not interpreted as missing", salaryLabel(job(0, null)).includes("from 0"));
assert("displayed amount is not silently multiplied by 1000",
  salaryLabel(job(10000, 20000)).includes("10,000–20,000") &&
  !salaryLabel(job(10000, 20000)).includes("k"));
assert("salary currency and time period never invented",
  salaryLabel(job(null, 30000)).includes("currency/period unverified"));
