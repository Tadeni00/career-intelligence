import { applicationReadinessSignals, PERSONAL_VERIFICATIONS } from "./applicationReadiness.ts";
import type { Job, MatchResult } from "./types.ts";

const base = {
  id: 1, url: "https://example.org/apply", title: "Analyst", company: "Example",
  location: "Remote", remote_status: "REMOTE", salary_min: null, salary_max: null,
} as Job;
let failures = 0;

function check(label: string, passed: boolean): void {
  if (passed) console.log("PASS", label);
  else { console.error("FAIL", label); failures++; }
}
const signals = applicationReadinessSignals(base, null);
check("link syntax is only link availability", signals.find(s => s.key === "destination")?.status === "available" &&
  signals.find(s => s.key === "destination")?.explanation.includes("not been checked") === true);
check("remote does not imply global eligibility", signals.find(s => s.key === "location")?.explanation.includes("permitted countries") === true);
check("authorization always unverified", signals.find(s => s.key === "authorization")?.status === "unknown");
check("missing match remains unknown", signals.find(s => s.key === "qualifications")?.status === "unknown");
check("missing salary remains unknown", signals.find(s => s.key === "compensation")?.status === "unknown");
check("vacancy availability remains unknown without live validation", signals.find(s => s.key === "availability")?.status === "unknown");
check("personal check IDs are distinct", new Set(PERSONAL_VERIFICATIONS.map(s => s.key)).size === PERSONAL_VERIFICATIONS.length);
const broken = applicationReadinessSignals({ ...base, url: "javascript:alert(1)" }, null);
check("unsafe application links are flagged", broken.find(s => s.key === "destination")?.status === "review");
const stale = applicationReadinessSignals(base, null, { status: "stale", reason: "old posting" });
check("stale postings require renewed check", stale.find(s => s.key === "availability")?.status === "review");
const matched = applicationReadinessSignals(base, { recommendation: "APPLY", overall_score: 90 } as MatchResult);
check("high match never certifies eligibility", matched.find(s => s.key === "authorization")?.status === "unknown" &&
  matched.find(s => s.key === "qualifications")?.status === "review");
process.exitCode = failures ? 1 : 0;
