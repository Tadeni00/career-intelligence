/** Browser-side, no-fetch extraction of user-supplied JobPosting JSON-LD or HTML.
 * Never execute supplied scripts or trust an extracted value as confirmed.
 * Schema reference: https://schema.org/JobPosting
 */
export type VacancyDraft = {
  title: string;
  company: string;
  location: string;
  description: string;
  arrangement: "REMOTE" | "HYBRID" | "ONSITE" | "UNKNOWN";
  warning: string;
};

type RecordValue = Record<string, unknown>;

function record(value: unknown): RecordValue | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as RecordValue : null;
}
function simple(value: unknown): string {
  return typeof value === "string" ? value.trim() : "";
}
function cleanText(value: string): string {
  const noUnsafe = value.replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, " ")
    .replace(/<style\b[^>]*>[\s\S]*?<\/style\s*>/gi, " ")
    .replace(/<[^>]*>/g, " ");
  return noUnsafe.replace(/&nbsp;|&#160;/gi, " ")
    .replace(/&amp;/gi, "&").replace(/&lt;/gi, "<")
    .replace(/&gt;/gi, ">").replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'").replace(/\s+/g, " ").trim();
}
function jobTypes(value: unknown): boolean {
  const values = Array.isArray(value) ? value : [value];
  return values.some((item) => typeof item === "string" &&
    (item === "JobPosting" || item === "https://schema.org/JobPosting" ||
      item === "http://schema.org/JobPosting"));
}
function findJobs(value: unknown, depth = 0): RecordValue[] {
  if (depth > 5) return [];
  if (Array.isArray(value)) return value.flatMap((item) => findJobs(item, depth + 1));
  const object = record(value);
  if (!object) return [];
  const self = jobTypes(object["@type"]) ? [object] : [];
  return [...self, ...findJobs(object["@graph"], depth + 1)];
}
function organization(value: unknown): string {
  if (typeof value === "string") return value.trim();
  const obj = record(value);
  return obj ? simple(obj.name) : "";
}
function place(value: unknown): string {
  if (Array.isArray(value)) return value.map(place).filter(Boolean).join("; ");
  const obj = record(value);
  if (!obj) return simple(value);
  const address = record(obj.address);
  if (!address) return simple(obj.name) || simple(obj.address);
  const parts = [address.addressLocality, address.addressRegion, address.addressCountry]
    .map((item) => typeof item === "string" ? item : record(item)?.name)
    .map(simple).filter(Boolean);
  return [...new Set(parts)].join(", ");
}
function arrangement(value: RecordValue): VacancyDraft["arrangement"] {
  const raw = value.jobLocationType;
  const values = Array.isArray(raw) ? raw : [raw];
  if (values.some((item) => simple(item).toUpperCase() === "TELECOMMUTE")) return "REMOTE";
  // Never infer on-site/hybrid from a geographic address alone.
  return "UNKNOWN";
}

export function extractVacancyDraft(input: string): VacancyDraft | null {
  if (input.length > 150000 || !input.trim()) return null;
  const candidates: unknown[] = [];
  const trimmed = input.trim();
  if (trimmed.startsWith("{") || trimmed.startsWith("[")) {
    try { candidates.push(JSON.parse(trimmed)); } catch { return null; }
  } else {
    const script = /<script\b[^>]*type\s*=\s*["']application\/ld\+json["'][^>]*>([\s\S]*?)<\/script\s*>/gi;
    for (const match of input.matchAll(script)) {
      try { candidates.push(JSON.parse(match[1])); } catch { /* ignore malformed blocks */ }
    }
  }
  const jobs = candidates.flatMap((candidate) => findJobs(candidate));
  if (jobs.length !== 1) return null; // Avoid choosing the wrong job from listing pages.
  const job = jobs[0];
  const title = simple(job.title);
  const company = organization(job.hiringOrganization);
  const location = place(job.jobLocation);
  const description = cleanText(simple(job.description));
  if (!title || !company || description.length < 30) return null;
  return {
    title: title.slice(0, 255),
    company: company.slice(0, 255),
    location: location.slice(0, 255),
    description: description.slice(0, 50000),
    arrangement: arrangement(job),
    warning: location
      ? "Review every field, especially the work arrangement and posting deadline."
      : "Workplace is missing. Confirm the actual city and country before saving.",
  };
}
