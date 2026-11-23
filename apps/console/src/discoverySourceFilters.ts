import type { DiscoveredJobOut } from "./types";

export type DiscoveryArrangement = "all" | "local" | "remote";
export function arrangementBucket(job: DiscoveredJobOut["job"]): "local" | "remote" | "unknown" {
  if (job.remote_status === "REMOTE") return "remote";
  // Non-remote labels are not proof of workplace; retain unknown separately.
  if (job.remote_status === "ONSITE" || job.remote_status === "HYBRID" ||
      job.source === "careerjet" || job.source === "devglobaljobs") return "local";
  return "unknown";
}

export function sourcesFromResults(items: readonly DiscoveredJobOut[]): string[] {
  return Array.from(new Set(items.map(({ job }) => job.source ?? "unknown"))).sort();
}

export function filterDiscoveredResults(
  items: readonly DiscoveredJobOut[],
  source: string,
  arrangement: DiscoveryArrangement,
): DiscoveredJobOut[] {
  return items.filter(({ job }) =>
    (source === "all" || (job.source ?? "unknown") === source) &&
    (arrangement === "all" || arrangementBucket(job) === arrangement)
  );
}

export function sourceCounts(items: readonly DiscoveredJobOut[]): { source: string; count: number }[] {
  return sourcesFromResults(items).map((source) => ({
    source, count: items.filter(({ job }) => (job.source ?? "unknown") === source).length,
  }));
}
