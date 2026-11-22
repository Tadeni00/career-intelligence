import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, Badge, Group, Select, Text } from "@mantine/core";
import { errorMessage } from "./api";
import {
  SHARED_PROFILE_LABEL,
  getActiveProfileId,
  invalidateProfiles,
  isUsableProfile,
  loadProfiles,
  setActiveProfileId,
  subscribeToActiveProfile,
  subscribeToProfiles,
} from "./activeProfile";
import { useProfileNames } from "./ProvenanceBadge";
import type { CVProfileOut } from "./types";

/**
 * Load every CV profile owned by the current candidate.
 *
 * Backed by the shared cache, so the selector, the profile manager and any
 * provenance badge all read one request rather than one each.
 */
export function useProfiles(): {
  profiles: CVProfileOut[];
  loading: boolean;
  error: string | null;
  reload: () => void;
} {
  const { profiles, ready } = useProfileNames();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadProfiles()
      .then(() => {
        if (!cancelled) setError(null);
      })
      .catch((e) => {
        if (!cancelled) setError(errorMessage(e, "Could not load CV profiles."));
      });
    const unsubscribe = subscribeToProfiles(() => {
      if (!cancelled) setError(null);
    });
    return () => {
      cancelled = true;
      unsubscribe();
    };
  }, []);

  return {
    profiles,
    loading: !ready,
    error,
    reload: () => invalidateProfiles(),
  };
}

/**
 * Choose which CV profile the matching, document and application requests in
 * this view are evaluated against.
 *
 * The selection is explicit and reversible. When no profile is chosen the
 * shared Candidate record is used, which is the historical behaviour; the
 * control says so rather than implying a profile is active.
 */
export function ProfileSelector({
  profiles,
  value,
  onChange,
  label = "CV profile",
  description,
}: {
  profiles: CVProfileOut[];
  value: number | null;
  onChange: (profileId: number | null) => void;
  label?: string;
  description?: string;
}) {
  const usable = profiles.filter(isUsableProfile);
  const options = [
    { value: "shared", label: SHARED_PROFILE_LABEL },
    ...usable.map((profile) => ({
      value: String(profile.id),
      label: profile.label,
    })),
  ];

  return (
    <Select
      label={label}
      description={description}
      data={options}
      value={value === null ? "shared" : String(value)}
      onChange={(next) =>
        onChange(next === null || next === "shared" ? null : Number(next))
      }
      allowDeselect={false}
      disabled={usable.length === 0}
      rightSection={
        usable.length === 0 ? (
          <Badge size="xs" color="gray" variant="light">
            None confirmed
          </Badge>
        ) : null
      }
    />
  );
}

/**
 * A compact, always-visible statement of which profile the current view is
 * using, so a score or document is never ambiguous about its evidence.
 */
export function ActiveProfileBanner({
  profiles,
  profileId,
  onChange,
}: {
  profiles: CVProfileOut[];
  profileId: number | null;
  onChange: (profileId: number | null) => void;
}) {
  const selected = profiles.find((p) => p.id === profileId) ?? null;

  if (profileId !== null && selected && !isUsableProfile(selected)) {
    return (
      <Alert color="orange" mb="md">
        CV profile “{selected.label}” is {selected.archived_at ? "archived" : selected.status}
        , so it cannot be used for new matches or documents. Existing results and
        documents remain attributed to it. Choose another profile to continue.
      </Alert>
    );
  }

  return (
    <Group justify="space-between" align="flex-end" mb="md" gap="md">
      <div>
        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
          Searching as
        </Text>
        <Text size="sm" fw={600}>
          {profileId === null
            ? SHARED_PROFILE_LABEL
            : (profiles.find((p) => p.id === profileId)?.label ?? `CV profile #${profileId}`)}
        </Text>
      </div>
      <ProfileSelector
        profiles={profiles}
        value={profileId}
        onChange={onChange}
        label="Change"
      />
    </Group>
  );
}

/** Subscribe a component to the console-wide active profile. */
export function useActiveProfile(): [number | null, (id: number | null) => void] {
  const [profileId, setProfileId] = useState<number | null>(getActiveProfileId);
  useEffect(() => subscribeToActiveProfile(setProfileId), []);
  return [profileId, setActiveProfileId];
}

/** Link to profile management, shown when no usable profile exists yet. */
export function NoProfilesNotice() {
  return (
    <Alert color="blue" mb="md">
      You have no confirmed CV profile yet, so searches use your shared profile.
      You can <Link to="/cv">upload another CV as its own profile</Link> at any
      time — existing profiles are never replaced.
    </Alert>
  );
}