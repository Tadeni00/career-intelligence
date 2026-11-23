/** Focused job-seeker triage checks, no API/provider calls. */
import { promisingOpportunity, visibleOpportunities } from "./discoveryTriage.ts";
import type { DiscoveredJobOut } from "./types.ts";

declare const process: { exit(code: number): void };

function opportunity(
  id: number,
  relevance: string | null,
  recommendation: string | null,
  score: number,
  options: { stale?: boolean; duplicate?: boolean; posted?: string | null } = {},
): DiscoveredJobOut {
  return {
    job: { id, posted_at: options.posted ?? null } as DiscoveredJobOut["job"],
    match: recommendation
      ? { overall_score: score, recommendation } as DiscoveredJobOut["match"]
      : null,
    search_relevance: relevance ? { label: relevance, reason: "advisory" } : null,
    freshness: options.stale ? { status: "stale", reason: "older" } : null,
    duplicate_review: options.duplicate
      ? { status: "Likely duplicate", reason: "similar", related_job_ids: [] }
      : null,
    shortlisted: false,
  };
}

let failures = 0;
function check(name: string, actual: unknown, expected: unknown) {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    failures += 1;
    console.error("FAIL", name, { actual, expected });
  } else {
    console.log("PASS", name);
  }
}
const aligned = opportunity(1, "Aligned", "APPLY", 84, { posted: "2026-11-20T00:00:00Z" });
const adjacent = opportunity(2, "Adjacent", "APPLY_WITH_TAILORING", 72);
const mismatch = opportunity(3, "Mismatch", "APPLY", 99, { posted: "2026-11-22T00:00:00Z" });
const stale = opportunity(4, "Aligned", "APPLY", 95, { stale: true });
const duplicate = opportunity(5, "Aligned", "APPLY", 95, { duplicate: true });
const unscored = opportunity(6, null, null, 0);
const all = [mismatch, stale, unscored, adjacent, duplicate, aligned];

check("promising includes aligned/adjacent with APPLY recommendations",
  all.filter(promisingOpportunity).map(x => x.job.id), [2, 1]);
check("stale, likely duplicates, unscored and mismatches are not hidden by default",
  visibleOpportunities(all, "review", false).length, 6);
check("review-first prioritizes aligned and recommendations, not raw score alone",
  visibleOpportunities([mismatch, adjacent, aligned], "review", false).map(x => x.job.id),
  [1, 2, 3]);
check("newest sorts dated records first, undated records last",
  visibleOpportunities([unscored, aligned, mismatch], "newest", false).map(x => x.job.id),
  [3, 1, 6]);
check("score sorting puts unscored last",
  visibleOpportunities([unscored, adjacent, aligned], "score", false).map(x => x.job.id),
  [1, 2, 6]);
check("promising filter preserves original array",
  [all.length, visibleOpportunities(all, "review", true).length], [6, 2]);
check("stable IDs break ties deterministically",
  visibleOpportunities([opportunity(9, null, null, 0), opportunity(7, null, null, 0)],
    "review", false).map(x => x.job.id), [7, 9]);

process.exit(failures === 0 ? 0 : 1);
