import { useCallback, useState } from "react";
import { notifications } from "@mantine/notifications";
import { api, errorMessage } from "./api";
import { describeProvenance } from "./activeProfile";
import type { CVProfileOut, MatchResult } from "./types";

/**
 * Run a match for a job against the currently selected evidence.
 *
 * Every call inserts a new match record: the backend never updates or replaces
 * an existing result, so re-running is a deliberate act that grows the history
 * rather than an edit. The hook says so in the confirmation so the cost of a
 * click is never invisible.
 *
 * A result is only ever produced for the requested scope. There is no fallback
 * to the shared record when a profile is selected and cannot be scored — that
 * surfaces as an error, it does not silently score something else.
 */
export function useRunMatch(profileId: number | null, profiles: CVProfileOut[]) {
  const [busyId, setBusyId] = useState<number | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  const run = useCallback(
    async (jobId: number): Promise<MatchResult | null> => {
      setBusyId(jobId);
      setRunError(null);
      const scope = describeProvenance(profileId, profiles);
      try {
        const result = await api<MatchResult>(`/jobs/${jobId}/match`, {
          method: "POST",
          // Empty object when no profile is selected: the backend treats that
          // as the unchanged legacy path, never as a default profile.
          body: JSON.stringify(profileId === null ? {} : { cv_profile_id: profileId }),
        });
        notifications.show({
          title: "Match calculated",
          message: `Scored against ${scope}. Stored as match #${result.id}; earlier results are kept.`,
          color: "green",
        });
        return result;
      } catch (e) {
        const message = errorMessage(e, "The match could not be calculated.");
        setRunError(message);
        notifications.show({
          title: "Match failed",
          message,
          color: "red",
        });
        return null;
      } finally {
        setBusyId(null);
      }
    },
    [profileId, profiles]
  );

  return { run, busyId, runError, clearRunError: () => setRunError(null) };
}
