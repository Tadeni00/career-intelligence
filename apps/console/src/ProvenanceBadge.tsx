import { useEffect, useState } from "react";
import { Badge, Group, Text } from "@mantine/core";
import {
  cachedProfiles,
  describeProvenance,
  loadProfiles,
  subscribeToProfiles,
} from "./activeProfile";
import type { CVProfileOut } from "./types";

/**
 * Shared access to the CV profile list, backed by one cache.
 *
 * Views that only need to *name* a profile use `useProfileNames` and never
 * trigger their own request.
 */
export function useProfileNames(): {
  profiles: CVProfileOut[];
  ready: boolean;
} {
  const [profiles, setProfiles] = useState<CVProfileOut[]>(cachedProfiles);
  const [ready, setReady] = useState(cachedProfiles().length > 0);

  useEffect(() => {
    let cancelled = false;
    loadProfiles()
      .then((data) => {
        if (!cancelled) setProfiles(data);
      })
      .catch(() => {
        /* naming degrades to the numeric id; nothing else breaks */
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    const unsubscribe = subscribeToProfiles(() => {
      if (!cancelled) setProfiles(cachedProfiles());
    });
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  return { profiles, ready };
}

/**
 * State which CV profile a score, document or application came from.
 *
 * `null` is shown as the shared profile, never omitted: a result with no
 * profile is a different thing from a result whose profile has not loaded yet.
 */
export function ProvenanceBadge({
  profileId,
  profiles,
  size = "xs",
  prefix,
}: {
  profileId: number | null;
  profiles: CVProfileOut[];
  size?: "xs" | "sm" | "md" | "lg" | "xl";
  prefix?: string;
}) {
  const known = profileId !== null ? profiles.find((p) => p.id === profileId) : undefined;
  const archived = known?.archived_at != null;
  const pending =
    profileId !== null && known === undefined && profiles.length > 0;

  return (
    <Badge
      size={size}
      variant="light"
      color={profileId === null ? "gray" : archived ? "gray" : "teal"}
      title={
        profileId === null
          ? "Calculated from your shared profile, not a specific CV."
          : `Calculated from the CV profile “${describeProvenance(profileId, profiles)}”.`
      }
    >
      {prefix ? `${prefix} ` : ""}
      {profileId === null
        ? "Shared profile"
        : pending
          ? `CV profile #${profileId}`
          : known?.label ?? `CV profile #${profileId}`}
      {archived ? " (archived)" : ""}
    </Badge>
  );
}

/** A one-line explanation of what the badge above means. */
export function ProvenanceNote({
  profileId,
  profiles,
}: {
  profileId: number | null;
  profiles: CVProfileOut[];
}) {
  const known = profileId !== null ? profiles.find((p) => p.id === profileId) : undefined;
  if (profileId === null) {
    return (
      <Text size="xs" c="dimmed">
        This uses your shared profile. Choose a CV profile to see results specific
        to one CV.
      </Text>
    );
  }
  if (known?.archived_at) {
    return (
      <Text size="xs" c="dimmed">
        Generated from “{known.label}”, which is archived. It stays attributed to
        that CV, but cannot be used for new work.
      </Text>
    );
  }
  return (
    <Text size="xs" c="dimmed">
      Generated from “{known?.label ?? `CV profile #${profileId}`}”, not from your
      shared profile.
    </Text>
  );
}

/** Badge plus note, the form used on detail pages. */
export function ProvenanceSummary({
  profileId,
  profiles,
  label = "Provenance",
}: {
  profileId: number | null;
  profiles: CVProfileOut[];
  label?: string;
}) {
  return (
    <Group gap="xs" align="center">
      <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
        {label}
      </Text>
      <ProvenanceBadge profileId={profileId} profiles={profiles} size="sm" />
    </Group>
  );
}