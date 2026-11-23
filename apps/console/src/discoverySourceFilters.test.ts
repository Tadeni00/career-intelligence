import { filterDiscoveredResults, sourceCounts, sourcesFromResults, arrangementBucket } from "./discoverySourceFilters.ts";
import type { DiscoveredJobOut } from "./types";

const make = (id: number, source: string, remote_status: string | null): DiscoveredJobOut => ({
  job: { id, title: "Role", source, remote_status },
} as DiscoveredJobOut);
const items = [
  make(1, "devglobaljobs", null),
  make(2, "remotive", "REMOTE"),
  make(3, "careerjet", null),
  make(4, "jsearch", null),
];
function check(value: unknown, reason: string): void {
  if (!value) throw new Error(reason);
}
check(sourceCounts(items).map(({ count }) => count).every((n) => n === 1), "Each provider counted");
check(sourcesFromResults(items).length === 4, "Distinct providers discovered");
check(filterDiscoveredResults(items, "remotive", "all").map((r) => r.job.id).join() === "2", "Source filter");
check(filterDiscoveredResults(items, "all", "remote").map((r) => r.job.id).join() === "2", "Remote filter");
check(filterDiscoveredResults(items, "all", "local").map((r) => r.job.id).join() === "1,3", "Benin workplace filter");
check(arrangementBucket(items[3].job) === "unknown", "Unknown workplace not falsely local");
check(filterDiscoveredResults(items, "all", "all").length === 4, "All shows full response");
check(items.length === 4, "Filtering must not mutate original results");
console.log("PASS unified discovery source/workplace filters");
