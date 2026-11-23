import type { DiscoveredJobOut } from "./types";

export type DiscoverySort = "review" | "newest" | "score";

function postedTime(item: DiscoveredJobOut): number {
  const date = item.job.posted_at;
  if (!date) return -Infinity;
  const parsed = Date.parse(date);
  return Number.isFinite(parsed) ? parsed : -Infinity;
}

function score(item: DiscoveredJobOut): number {
  const value = item.match?.overall_score;
  return value !== undefined && value !== null && Number.isFinite(value)
    ? value
    : -1;
}

// Advisory ordering, NOT a revised matching score or hiring-eligibility decision.
// The provider relevance, freshness, duplicate and match assessments are retained
// exactly as returned. Missing signals never imply a strong match.
function reviewPriority(item: DiscoveredJobOut): number {
  const relevance = item.search_relevance?.label;
  const relevancePoints =
    relevance === "Aligned" ? 4 : relevance === "Adjacent" ? 2 : 0;
  const recommendation = item.match?.recommendation;
  const matchPoints =
    recommendation === "APPLY" ? 4 :
    recommendation === "APPLY_WITH_TAILORING" ? 3 :
    recommendation === "STRETCH" ? 1 : 0;
  const stalePenalty = item.freshness?.status === "stale" ? 3 : 0;
  const duplicatePenalty =
    item.duplicate_review?.status === "Likely duplicate" ? 2 : 0;
  return relevancePoints + matchPoints - stalePenalty - duplicatePenalty;
}

export function promisingOpportunity(item: DiscoveredJobOut): boolean {
  return (
    (item.search_relevance?.label === "Aligned" ||
      item.search_relevance?.label === "Adjacent") &&
    (item.match?.recommendation === "APPLY" ||
      item.match?.recommendation === "APPLY_WITH_TAILORING") &&
    item.freshness?.status !== "stale" &&
    item.duplicate_review?.status !== "Likely duplicate"
  );
}

export function visibleOpportunities(
  items: readonly DiscoveredJobOut[],
  sort: DiscoverySort,
  promisingOnly: boolean,
): DiscoveredJobOut[] {
  const visible = promisingOnly ? items.filter(promisingOpportunity) : [...items];
  return visible.sort((a, b) => {
    const primary = sort === "newest"
      ? postedTime(b) - postedTime(a)
      : sort === "score"
        ? score(b) - score(a)
        : reviewPriority(b) - reviewPriority(a);
    // Avoid NaN when two posting timestamps are missing.
    if (Number.isFinite(primary) && primary !== 0) return primary;
    const scoreDiff = score(b) - score(a);
    if (scoreDiff !== 0) return scoreDiff;
    const dateDiff = postedTime(b) - postedTime(a);
    if (Number.isFinite(dateDiff) && dateDiff !== 0) return dateDiff;
    return a.job.id - b.job.id;
  });
}
