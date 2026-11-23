import { extractVacancyDraft } from "./vacancyDraftExtraction.ts";
function check(value: unknown, message: string): asserts value {
  if (!value) throw new Error(message);
}
const source = {
  "@context": "https://schema.org",
  "@type": "JobPosting",
  title: "Analyste de données",
  hiringOrganization: { "@type": "Organization", name: "Société Bénin" },
  jobLocation: { address: { addressLocality: "Cotonou", addressCountry: "BJ" } },
  description: "<p>SQL, Python and data quality; at least three years of experience.</p>",
};
const raw = JSON.stringify(source);
const result = extractVacancyDraft(raw);
check(result, "Expected JobPosting draft");
check(result.title === "Analyste de données", "Title must be parsed");
check(result.company === "Société Bénin", "Employer must be parsed");
check(result.location === "Cotonou, BJ", "City/country must be parsed");
check(result.arrangement === "UNKNOWN", "Address alone does not prove on-site");
check(result.description.startsWith("SQL, Python"), "Description must be plain text");

const html = '<html><script type="application/ld+json">' + raw +
  '</script><script>alert("run")</script></html>';
const fromHtml = extractVacancyDraft(html);
check(fromHtml?.title === result.title, "Structured HTML script must parse without executing");
check(!fromHtml?.description.includes("<p>"), "HTML markup must be removed");

const remote = extractVacancyDraft(JSON.stringify({ ...source, jobLocationType: "TELECOMMUTE" }));
check(remote?.arrangement === "REMOTE", "Explicit telecommute should be retained");
const missingLocation = extractVacancyDraft(JSON.stringify({ ...source, jobLocation: undefined }));
check(missingLocation?.location === "", "Missing workplace must not be invented");

check(extractVacancyDraft(JSON.stringify({ "@type": "Organization", name: "Not a job" })) === null,
  "Non-job structured data cannot create a vacancy");
check(extractVacancyDraft(JSON.stringify([source, source])) === null,
  "Ambiguous multiple postings must not arbitrarily choose one");
check(extractVacancyDraft(JSON.stringify({ ...source, hiringOrganization: undefined })) === null,
  "Missing employer cannot be inferred");
check(extractVacancyDraft(JSON.stringify({ ...source, description: "Short" })) === null,
  "Incomplete job content must not be treated as complete");
check(extractVacancyDraft("x".repeat(150001)) === null, "Large inputs are rejected");
console.log("PASS reviewed structured-data vacancy extraction");
