import type { TailoredCV } from "./types";

/**
 * Route semantics for the tailored-CV workflow.
 *
 *   /tailored-cvs/:id         -> exactly one TailoredCV document, by document id
 *   /jobs/:jobId/tailored-cv  -> the CV workflow for exactly one job
 *
 * The two id spaces overlap numerically (job 13 and tailored CV 13 both exist and
 * are different things), so a route param is interpreted only as the entity its
 * own route declares. A value is never re-read as the other entity type.
 */
export type TailoredCVTarget =
  | { kind: "document"; docId: number }
  | { kind: "job"; jobId: number }
  | { kind: "invalid"; reason: string };

/** Accept only a plain positive integer; reject anything else rather than coerce. */
function positiveInt(raw: string | undefined): number | null {
  if (raw === undefined) return null;
  if (!/^[0-9]+$/.test(raw)) return null;
  const n = Number(raw);
  return Number.isSafeInteger(n) && n > 0 ? n : null;
}

/**
 * Resolve a route param using the route it arrived on. `jobId` comes from the
 * job-scoped route and `id` from the document route, so no fallback between
 * entity types is possible.
 */
export function resolveTailoredCVTarget(params: {
  id?: string;
  jobId?: string;
}): TailoredCVTarget {
  const jobId = positiveInt(params.jobId);
  const docId = positiveInt(params.id);

  if (params.jobId !== undefined && jobId === null) {
    return { kind: "invalid", reason: `"${params.jobId}" is not a valid job id.` };
  }
  if (params.id !== undefined && docId === null) {
    return { kind: "invalid", reason: `"${params.id}" is not a valid tailored CV id.` };
  }
  if (jobId !== null) return { kind: "job", jobId };
  if (docId !== null) return { kind: "document", docId };
  return { kind: "invalid", reason: "No tailored CV was requested." };
}

/**
 * A document belongs to a job only when the backend's own `job_id` field says
 * so. This is the single source of truth for identity in this data model; ids
 * are never inferred from ranges, ordering or which entity happens to exist.
 */
export function belongsToJob(
  doc: Pick<TailoredCV, "job_id">,
  jobId: number
): boolean {
  return doc.job_id === jobId;
}

/**
 * Keep only the documents the backend associates with this job. The list endpoint
 * already returns newest first, so backend order is preserved.
 */
export function selectJobCVs(docs: TailoredCV[], jobId: number): TailoredCV[] {
  return docs.filter((d) => belongsToJob(d, jobId));
}

/**
 * Where an application's materials live. Uses the real tailored CV id when the
 * application has one, and otherwise falls back to that application's job --
 * never to the application id, which is a different entity in a different table.
 */
export function applicationMaterialsTarget(app: {
  job_id: number;
  tailored_cv_id: number | null;
}): { kind: "document"; docId: number } | { kind: "job"; jobId: number } {
  return app.tailored_cv_id !== null
    ? { kind: "document", docId: app.tailored_cv_id }
    : { kind: "job", jobId: app.job_id };
}

/** Build the href for a resolved target. */
export function targetPath(
  target: TailoredCVTarget
): string | null {
  if (target.kind === "document") return `/tailored-cvs/${target.docId}`;
  if (target.kind === "job") return `/jobs/${target.jobId}/tailored-cv`;
  return null;
}
