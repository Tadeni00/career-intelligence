import type { Job } from "./types";

// Provider data cannot establish where a remote worker may legally reside,
// whether the listing is still open, or whether salary is annual/monthly.
export function workArrangementLabel(remoteStatus: string | null | undefined): string {
  if (!remoteStatus || !remoteStatus.trim()) return "Work arrangement not stated";
  const value = remoteStatus.trim().toUpperCase();
  if (value === "REMOTE") return "Remote (country restrictions unverified)";
  if (value === "HYBRID") return "Hybrid";
  if (value === "ONSITE" || value === "ON_SITE" || value === "ON-SITE") return "On-site";
  return "Work arrangement: " + remoteStatus.trim();
}

export function salaryLabel(job: Pick<Job, "salary_min" | "salary_max">): string {
  const { salary_min: minimum, salary_max: maximum } = job;
  const hasMinimum = minimum !== null && minimum !== undefined && Number.isFinite(minimum);
  const hasMaximum = maximum !== null && maximum !== undefined && Number.isFinite(maximum);
  if (!hasMinimum && !hasMaximum) return "Salary not stated";
  if (hasMinimum && hasMaximum) return `Salary: ${minimum!.toLocaleString("en-US")}–${maximum!.toLocaleString("en-US")} (currency/period unverified)`;
  if (hasMinimum) return `Salary: from ${minimum!.toLocaleString("en-US")} (currency/period unverified)`;
  return `Salary: up to ${maximum!.toLocaleString("en-US")} (currency/period unverified)`;
}
