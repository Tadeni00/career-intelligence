/** Explicit, browser-local discovery presets. Never auto-run a provider search. */

export const SAVED_SEARCHES_KEY = "career.discovery.savedSearches.v1";
export const MAX_SAVED_SEARCHES = 8;
export type SearchCriteria = {
  query: string;
  country: string;
  location: string;
  remoteOnly: boolean;
  maxResults: number;
};
export type SavedSearch = SearchCriteria & { id: string; label: string };

export function validCriteria(input: unknown): SearchCriteria | null {
  if (!input || typeof input !== "object") return null;
  const value = input as Record<string, unknown>;
  if (typeof value.query !== "string" || !value.query.trim() || value.query.length > 200) return null;
  if (typeof value.country !== "string" || !/^[a-z]{2}$/i.test(value.country)) return null;
  if (typeof value.location !== "string" || value.location.length > 100) return null;
  if (typeof value.remoteOnly !== "boolean") return null;
  if (typeof value.maxResults !== "number" ||
      !Number.isInteger(value.maxResults) || value.maxResults < 1 || value.maxResults > 50) return null;
  return {
    query: value.query.trim(),
    country: value.country.toLowerCase(),
    location: value.location.trim(),
    remoteOnly: value.remoteOnly,
    maxResults: value.maxResults,
  };
}

export function parseSavedSearches(raw: string | null): SavedSearch[] {
  if (!raw) return [];
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    const result: SavedSearch[] = [];
    const seen = new Set<string>();
    for (const value of parsed) {
      if (!value || typeof value !== "object") continue;
      const item = value as Record<string, unknown>;
      const criteria = validCriteria(item);
      if (!criteria || typeof item.id !== "string" ||
          !/^[a-zA-Z0-9-]{1,80}$/.test(item.id) ||
          typeof item.label !== "string" || !item.label.trim() ||
          item.label.length > 120 || seen.has(item.id)) continue;
      seen.add(item.id);
      result.push({ ...criteria, id: item.id, label: item.label.trim() });
      if (result.length === MAX_SAVED_SEARCHES) break;
    }
    return result;
  } catch {
    return [];
  }
}

export function readSavedSearches(): SavedSearch[] {
  try {
    return parseSavedSearches(window.localStorage.getItem(SAVED_SEARCHES_KEY));
  } catch {
    return [];
  }
}

export function writeSavedSearches(items: readonly SavedSearch[]): boolean {
  try {
    window.localStorage.setItem(SAVED_SEARCHES_KEY, JSON.stringify(items.slice(0, MAX_SAVED_SEARCHES)));
    return true;
  } catch {
    return false;
  }
}

export function suggestedSearchLabel(value: SearchCriteria): string {
  const place = value.location || value.country.toUpperCase();
  const remote = value.remoteOnly ? " · remote" : "";
  return `${value.query} · ${place}${remote}`.slice(0, 120);
}

export function addSavedSearch(
  items: readonly SavedSearch[], criteria: SearchCriteria, id: string,
): SavedSearch[] {
  const validated = validCriteria(criteria);
  if (!validated || !/^[a-zA-Z0-9-]{1,80}$/.test(id)) return [...items];
  const signature = JSON.stringify(validated);
  if (items.some(({ id: _id, label: _label, ...rest }) => JSON.stringify(rest) === signature)) {
    return [...items];
  }
  const next = [{ ...validated, id, label: suggestedSearchLabel(validated) }, ...items];
  return next.slice(0, MAX_SAVED_SEARCHES);
}
