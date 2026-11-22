/**
 * Application-destination rules for the job-discovery workflow.
 *
 * `Job.url` is the only source of truth for the original application
 * destination. It arrives from the external job provider and is persisted
 * verbatim; nothing here constructs, repairs, or guesses a URL from the job
 * title or employer. The helper only decides whether a stored value is safe to
 * render as a link, and what to tell the user when it is not.
 *
 * The backend already refuses to persist a malformed or non-HTTP(S) URL from
 * the discovery provider (`apps/api/app/services/jsearch.py::_is_valid_url`,
 * which requires an http/https scheme and a non-empty host, and drops the
 * whole vacancy otherwise). Legacy and manually created jobs bypass that path,
 * so the console re-checks before rendering rather than trusting the field.
 */

/** Longest employer name kept inside a button label before falling back to "Apply". */
const MAX_COMPANY_IN_LABEL = 20;

export type ApplicationUrlState =
  | { kind: "ok"; href: string }
  | { kind: "missing"; reason: string }
  | { kind: "unsafe"; reason: string };

/**
 * Classify a stored application URL.
 *
 * - `ok`       - absolute http/https URL with a host; safe to render as an anchor.
 * - `missing`  - absent or blank; the source supplied no destination at all.
 * - `unsafe`   - present but not a usable absolute http/https URL.
 *
 * The reason strings are user-facing copy: they are shown next to the action so
 * an unavailable Apply control always explains itself.
 */
export function classifyApplicationUrl(raw: string | null | undefined): ApplicationUrlState {
  if (raw === null || raw === undefined) {
    return {
      kind: "missing",
      reason: "No application link was provided by the job source.",
    };
  }

  const value = String(raw).trim();
  if (value === "") {
    return {
      kind: "missing",
      reason: "No application link was provided by the job source.",
    };
  }

  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    return {
      kind: "unsafe",
      reason: "The stored application link is not a valid URL and cannot be opened.",
    };
  }

  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
    return {
      kind: "unsafe",
      reason: `The stored application link uses an unsupported address (${parsed.protocol}//) and cannot be opened.`,
    };
  }

  if (parsed.hostname === "") {
    return {
      kind: "unsafe",
      reason: "The stored application link has no host and cannot be opened.",
    };
  }

  return { kind: "ok", href: value };
}

/**
 * Button label for the external application action.
 *
 * The employer is included when it is short enough to stay readable; a long
 * employer name collapses to "Apply" and is named in the supporting text
 * instead, so the control never becomes an awkwardly long button on a narrow
 * card. The wording never claims the application has been made.
 */
export function applyActionLabel(company: string | null | undefined): string {
  const name = (company ?? "").trim();
  if (name === "") return "Apply";
  if (name.length > MAX_COMPANY_IN_LABEL) return "Apply";
  return `Apply on ${name}'s site`;
}

/**
 * Supporting line under the application action. Always names the destination and
 * always states that the external site owns the application process.
 */
export function applyActionNote(
  company: string | null | undefined,
  source: string | null | undefined,
): string {
  const name = (company ?? "").trim();
  const owner = name === "" ? "the employer's site" : `${name}'s site`;
  const via = (source ?? "").trim() === "" ? "" : ` (via ${(source ?? "").trim()})`;
  return (
    `Opens the original vacancy on ${owner}${via} in a new tab. ` +
    "You read the posting and submit the application there; " +
    "Career Intelligence never submits applications on your behalf."
  );
}