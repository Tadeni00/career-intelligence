import { classifyApplicationUrl } from "./applicationUrl.ts";
import type { Freshness, Job, MatchResult } from "./types";

export type ReadinessSignal = {
  key: string;
  label: string;
  status: "available" | "review" | "unknown";
  explanation: string;
};

// Read-only presentation signals; not a new matching, work-authorization,
// salary-comparison, or hiring-eligibility algorithm.
export function applicationReadinessSignals(
  job: Job,
  match: MatchResult | null,
  freshness: Freshness | null = null,
): ReadinessSignal[] {
  const destination = classifyApplicationUrl(job.url);
  const location = job.location?.trim();
  const remote = job.remote_status?.trim();
  const salaryPresent = job.salary_min != null || job.salary_max != null;

  return [
    {
      key: "destination",
      label: "Employer application destination",
      status: destination.kind === "ok" ? "available" : "review",
      explanation: destination.kind === "ok"
        ? "A correctly formatted application link is available. The link has not been checked for reachability or whether applications remain open."
        : destination.reason,
    },
    {
      key: "location",
      label: "Work location and remote restrictions",
      status: location ? "review" : "unknown",
      explanation: location
        ? `Listed location: ${location}. ${remote === "REMOTE" ? "Marked remote, but permitted countries and cross-border restrictions are not verified." : "Confirm required office attendance and whether you can work in this location."}`
        : "The posting does not provide a clear location. Check the employer's site for permitted work locations and any remote-country restrictions.",
    },
    {
      key: "authorization",
      label: "Work authorization and sponsorship",
      status: "unknown",
      explanation: "Citizenship, residency, visa eligibility and employer sponsorship are not verified by this application. Confirm directly with the employer before investing in the application.",
    },
    {
      key: "qualifications",
      label: "Required qualifications and experience",
      status: match ? "review" : "unknown",
      explanation: match
        ? `Existing advisory recommendation: ${match.recommendation}. Inspect required qualifications, blockers and unknowns in the posting; a match score does not establish eligibility.`
        : "There is no match assessment for this view. Review the original requirements against your confirmed experience and education.",
    },
    {
      key: "compensation",
      label: "Salary and compensation",
      status: salaryPresent ? "review" : "unknown",
      explanation: salaryPresent
        ? "A salary figure is recorded, but currency, pay period, benefits and equivalence to your expectations may be unknown. Verify the original posting."
        : "Salary is not stated in the stored vacancy. Verify compensation and pay currency with the employer.",
    },
    {
      key: "availability",
      label: "Vacancy still accepting applications",
      status: freshness?.status === "stale" ? "review" : "unknown",
      explanation: freshness?.status === "stale"
        ? "This posting has been flagged as potentially stale. Confirm it is open on the original employer page."
        : "The application has not verified that this vacancy is currently open. Confirm it directly on the employer page.",
    },
  ];
}

export const PERSONAL_VERIFICATIONS = [
  { key: "location", label: "I checked the permitted work location and remote-country rules" },
  { key: "authorization", label: "I checked work authorization and sponsorship requirements" },
  { key: "qualifications", label: "I reviewed the employer's mandatory qualifications and experience" },
  { key: "availability", label: "I confirmed the vacancy still accepts applications" },
] as const;
