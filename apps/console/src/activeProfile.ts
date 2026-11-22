/**
 * Which CV profile the console sends with matching, document and application
 * requests.
 *
 * The choice is held in the browser and is only ever changed by an explicit
 * user action. There is no backend "active profile" and no implicit default: a
 * profile is selected because the person using the app selected it, and
 * clearing it deliberately returns to the shared Candidate record.
 *
 * Keeping it client-side means nothing is stored on the server that could make
 * one request's evidence silently apply to another.
 */

import type { CVProfileOut } from "./types";

const STORAGE_KEY = "career.activeCvProfileId";

type Listener = (profileId: number | null) => void;

const listeners = new Set<Listener>();

function read(): number | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw === null || raw === "") return null;
    const parsed = Number(raw);
    return Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
  } catch {
    // Private browsing or a blocked storage partition. Fall back to no profile
    // rather than failing the page.
    return null;
  }
}

let current: number | null | undefined;

export function getActiveProfileId(): number | null {
  if (current === undefined) current = read();
  return current;
}

/** Set the profile the console will use. Pass `null` to return to the shared record. */
export function setActiveProfileId(profileId: number | null): void {
  current = profileId;
  try {
    if (profileId === null) window.localStorage.removeItem(STORAGE_KEY);
    else window.localStorage.setItem(STORAGE_KEY, String(profileId));
  } catch {
    // Storage unavailable: the selection still applies for this page view.
  }
  for (const listener of listeners) listener(profileId);
}

export function subscribeToActiveProfile(listener: Listener): () => void {
  listeners.add(listener);
  // Keep in step with changes made in another tab.
  const onStorage = (event: StorageEvent) => {
    if (event.key !== null && event.key !== STORAGE_KEY) return;
    current = read();
    listener(current);
  };
  window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener("storage", onStorage);
  };
}

/** Profiles that may be used for new matching and document work. */
export function isUsableProfile(profile: CVProfileOut): boolean {
  return profile.status === "CONFIRMED" && profile.archived_at === null;
}

export const SHARED_PROFILE_LABEL = "Shared profile (all CVs)";

/** Human label for the profile a response was produced from. */
export function describeProvenance(
  profileId: number | null,
  profiles: CVProfileOut[]
): string {
  if (profileId === null) return SHARED_PROFILE_LABEL;
  const match = profiles.find((p) => p.id === profileId);
  return match ? match.label : `CV profile #${profileId}`;
}

// ---------------------------------------------------------------- the store
//
// One fetch, shared by every view that needs to name a profile. Without this,
// each page would re-request the list just to render a badge.

let cache: CVProfileOut[] | null = null;
let inflight: Promise<CVProfileOut[]> | null = null;
const subscribers = new Set<() => void>();

function notify(): void {
  for (const listener of subscribers) listener();
}

export function subscribeToProfiles(listener: () => void): () => void {
  subscribers.add(listener);
  return () => subscribers.delete(listener);
}

/** Profiles fetched so far. Empty until something has loaded them. */
export function cachedProfiles(): CVProfileOut[] {
  return cache ?? [];
}

export function loadProfiles(force = false): Promise<CVProfileOut[]> {
  if (cache && !force) return Promise.resolve(cache);
  if (inflight && !force) return inflight;

  inflight = api<CVProfileOut[]>("/cv-profiles")
    .then((data) => {
      cache = data;
      inflight = null;
      notify();
      return data;
    })
    .catch((error) => {
      inflight = null;
      notify();
      throw error;
    });
  return inflight;
}

/** Drop the cache after a profile is created, confirmed or archived. */
export function invalidateProfiles(): void {
  cache = null;
  notify();
  void loadProfiles(true).catch(() => {
    /* the next mount retries */
  });
}

// Imported at the end to keep the store helpers above easy to read; api.ts
// depends only on types, so this is not a cycle.
import { api } from "./api";