import { useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Divider,
  FileInput,
  Group,
  Modal,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { api, errorMessage, uploadFile } from "./api";
import {
  describeProvenance,
  getActiveProfileId,
  isUsableProfile,
  setActiveProfileId,
} from "./activeProfile";
import type { CVProfileOut } from "./types";
import { useProfiles } from "./ProfileSelector";

function canDelete(profile: CVProfileOut, activeId: number | null): boolean {
  return !profile.archived_at && profile.id !== activeId;
}

function statusColor(status: string, archived: boolean): string {
  if (archived) return "gray";
  if (status === "CONFIRMED") return "green";
  if (status === "EXTRACTION_FAILED") return "red";
  return "orange";
}

function statusLabel(profile: CVProfileOut): string {
  if (profile.archived_at) return "Archived";
  return profile.status.replace(/_/g, " ").toLowerCase();
}

/**
 * Manage independent CV profiles.
 *
 * Uploading a new CV always creates an additional profile: existing profiles,
 * and the shared profile, are left exactly as they are. Nothing here replaces
 * or merges into anything else.
 */
export function ProfileManager() {
  const { profiles, loading, error, reload } = useProfiles();
  const [activeId, setActiveId] = useState<number | null>(getActiveProfileId);
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<CVProfileOut | null>(null);

  const createProfile = async (file: File) => {
    setUploading(true);
    setUploadError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const created = await uploadFile("/cv-profiles", file);
      const profile = created as CVProfileOut;
      notifications.show({
        title: "Profile created",
        message: `“${profile.label}” was added. Your existing profiles are unchanged.`,
        color: "green",
      });
      reload();
    } catch (e) {
      setUploadError(errorMessage(e, "Upload failed."));
    } finally {
      setUploading(false);
    }
  };

  const runAction = async (profile: CVProfileOut, action: string) => {
    setBusyId(profile.id);
    try {
      if (action === "delete") {
        await api(`/cv-profiles/${profile.id}`, { method: "DELETE" });
        notifications.show({
          title: "Deleted",
          message: `“${profile.label}” was removed.`,
          color: "gray",
        });
        reload();
        return;
      }

      const updated = await api<CVProfileOut>(
        `/cv-profiles/${profile.id}/${action}`,
        action === "confirm" ? { method: "POST", body: JSON.stringify({}) } : { method: "POST" }
      );
      if (action === "extract") {
        notifications.show({
          title: "Extracted",
          message: `Review “${profile.label}” and confirm it when you are happy with the result.`,
          color: "blue",
        });
        setReviewing(updated);
      } else if (action === "archive") {
        notifications.show({
          title: "Archived",
          message: `“${profile.label}” is retired. Its matches and documents still point to it.`,
          color: "gray",
        });
      }
      reload();
    } catch (e) {
      notifications.show({
        title: "Action failed",
        message: errorMessage(e, `Could not ${action} this profile.`),
        color: "red",
      });
    } finally {
      setBusyId(null);
    }
  };

  const confirmProfile = async (
    profile: CVProfileOut,
    fields: {
      name?: string;
      professional_title?: string;
      email?: string;
      phone?: string;
      location?: string;
      summary?: string;
    }
  ) => {
    setBusyId(profile.id);
    try {
      await api(`/cv-profiles/${profile.id}/confirm`, {
        method: "POST",
        body: JSON.stringify(fields),
      });
      notifications.show({
        title: "Profile confirmed",
        message: `“${profile.label}” is now available for searching.`,
        color: "green",
      });
      setReviewing(null);
      reload();
    } catch (e) {
      notifications.show({
        title: "Confirmation failed",
        message: errorMessage(e, "Could not confirm this profile."),
        color: "red",
      });
    } finally {
      setBusyId(null);
    }
  };

  const selectProfile = (profile: CVProfileOut) => {
    setActiveProfileId(profile.id);
    setActiveId(profile.id);
    notifications.show({
      title: "CV profile selected",
      message: `New searches will be matched against “${profile.label}”.`,
      color: "teal",
    });
  };

  const usableCount = profiles.filter(isUsableProfile).length;

  return (
    <Card padding="lg" radius="md" mb="lg">
      <Title order={2} mb="xs">
        CV profiles
      </Title>
      <Text size="sm" c="dimmed" mb="md">
        Each CV here is a separate profile with its own confirmed details. Adding
        another CV never replaces or changes the ones you already have.
      </Text>

      <Stack gap="md">
        {(error || uploadError) && <Alert color="red">{error || uploadError}</Alert>}

        <FileInput
          label="Add another CV as a new profile (.pdf or .docx)"
          accept=".pdf,.docx"
          disabled={uploading}
          placeholder={uploading ? "Uploading…" : "Choose a file"}
          onChange={(file) => {
            if (file) createProfile(file);
          }}
        />

        {activeId !== null && (
          <Alert color="teal" variant="light">
            New searches use “{describeProvenance(activeId, profiles)}”.{" "}
            <Button
              variant="subtle"
              size="compact-xs"
              onClick={() => {
                setActiveProfileId(null);
                setActiveId(null);
              }}
            >
              Use my shared profile instead
            </Button>
          </Alert>
        )}

        <Divider />

        {loading ? (
          <Text c="dimmed" size="sm">
            Loading profiles…
          </Text>
        ) : profiles.length === 0 ? (
          <Text c="dimmed" size="sm">
            No CV profiles yet. Upload one above to create your first profile.
          </Text>
        ) : (
          <Stack gap="sm">
            {profiles.map((profile) => {
              const busy = busyId === profile.id;
              const usable = isUsableProfile(profile);
              return (
                <Card key={profile.id} withBorder padding="sm" radius="sm">
                  <Group justify="space-between" align="flex-start" wrap="nowrap">
                    <div style={{ minWidth: 0 }}>
                      <Group gap="xs">
                        <Text size="sm" fw={600} truncate>
                          {profile.label}
                        </Text>
                        <Badge
                          size="xs"
                          color={statusColor(profile.status, Boolean(profile.archived_at))}
                          variant="light"
                        >
                          {statusLabel(profile)}
                        </Badge>
                        {profile.id === activeId && (
                          <Badge size="xs" color="teal" variant="filled">
                            In use
                          </Badge>
                        )}
                      </Group>
                      <Text size="xs" c="dimmed">
                        {profile.confirmed
                          ? [
                              profile.confirmed.professional_title,
                              profile.confirmed.location,
                            ]
                              .filter(Boolean)
                              .join(" · ") || "No title or location confirmed"
                          : profile.extracted
                            ? "Extracted, not yet confirmed"
                            : "Not extracted yet"}
                      </Text>
                      {profile.extracted_issues.length > 0 && (
                        <Text size="xs" c="orange">
                          {profile.extracted_issues.length} extraction note
                          {profile.extracted_issues.length === 1 ? "" : "s"}
                        </Text>
                      )}
                    </div>

                    <Group gap="xs" wrap="nowrap">
                      {profile.status === "AWAITING_EXTRACTION" && !profile.archived_at && (
                        <Button
                          size="compact-sm"
                          variant="light"
                          loading={busy}
                          onClick={() => runAction(profile, "extract")}
                        >
                          Extract
                        </Button>
                      )}
                      {profile.status === "AWAITING_REVIEW" && !profile.archived_at && (
                        <>
                          <Button
                            size="compact-sm"
                            variant="light"
                            loading={busy}
                            onClick={() => runAction(profile, "extract")}
                          >
                            Re-extract
                          </Button>
                          <Button
                            size="compact-sm"
                            variant="light"
                            color="blue"
                            onClick={() => setReviewing(profile)}
                          >
                            Review
                          </Button>
                        </>
                      )}
                      {usable && profile.id !== activeId && (
                        <Button
                          size="compact-sm"
                          variant="default"
                          onClick={() => selectProfile(profile)}
                        >
                          Use this profile
                        </Button>
                      )}
                      {usable && (
                        <Button
                          size="compact-sm"
                          variant="light"
                          color="gray"
                          loading={busy}
                          onClick={() => runAction(profile, "archive")}
                        >
                          Archive
                        </Button>
                      )}
                      {canDelete(profile, activeId) && (
                        <Button
                          size="compact-sm"
                          variant="light"
                          color="red"
                          loading={busy}
                          onClick={() => runAction(profile, "delete")}
                        >
                          Delete
                        </Button>
                      )}
                    </Group>
                  </Group>
                </Card>
              );
            })}
          </Stack>
        )}

        {usableCount === 0 && profiles.length > 0 && (
          <Alert color="orange" variant="light">
            None of your profiles is confirmed yet. Confirm one to search against
            it; until then searches use your shared profile.
          </Alert>
        )}
      </Stack>

      <ReviewModal
        key={reviewing?.id ?? "none"}
        profile={reviewing}
        busy={busyId === reviewing?.id}
        onClose={() => setReviewing(null)}
        onConfirm={confirmProfile}
      />
    </Card>
  );
}

function ReviewModal({
  profile,
  busy,
  onClose,
  onConfirm,
}: {
  profile: CVProfileOut | null;
  busy: boolean;
  onClose: () => void;
  onConfirm: (
    profile: CVProfileOut,
    fields: {
      name?: string;
      professional_title?: string;
      email?: string;
      phone?: string;
      location?: string;
      summary?: string;
    }
  ) => void;
}) {
  // Seeded from the profile directly rather than copied in an effect: the
  // caller keys this component on the profile id, so switching profiles
  // remounts it and the fields always start from that profile's extraction.
  const [name, setName] = useState(profile?.extracted?.name ?? "");
  const [title, setTitle] = useState(profile?.extracted?.professional_title ?? "");
  const [email, setEmail] = useState(profile?.extracted?.email ?? "");
  const [phone, setPhone] = useState(profile?.extracted?.phone ?? "");
  const [location, setLocation] = useState(profile?.extracted?.location ?? "");
  const [summary, setSummary] = useState(profile?.extracted?.summary ?? "");

  if (!profile) return null;

  return (
    <Modal
      opened
      onClose={onClose}
      title={`Review “${profile.label}”`}
      size="lg"
    >
      <Stack gap="sm">
        <Text size="sm" c="dimmed">
          Check the details the profile will be matched on. Anything you leave
          unchanged keeps the extracted value. These contact details will be
          used in documents generated from this profile.
        </Text>
        <TextInput
          label="Full name"
          value={name}
          onChange={(e) => setName(e.currentTarget.value)}
        />
        <TextInput
          label="Email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.currentTarget.value)}
        />
        <TextInput
          label="Phone"
          value={phone}
          onChange={(e) => setPhone(e.currentTarget.value)}
        />
        <TextInput
          label="Professional title"
          value={title}
          onChange={(e) => setTitle(e.currentTarget.value)}
        />
        <TextInput
          label="Location"
          value={location}
          onChange={(e) => setLocation(e.currentTarget.value)}
        />
        <Textarea
          label="Summary"
          autosize
          minRows={3}
          value={summary}
          onChange={(e) => setSummary(e.currentTarget.value)}
        />
        {profile.extracted && (
          <Text size="xs" c="dimmed">
            {profile.extracted.skills.length} skills ·{" "}
            {profile.extracted.experience.length} roles ·{" "}
            {profile.extracted.education.length} qualifications
          </Text>
        )}
        <Group justify="flex-end" gap="sm">
          <Button variant="default" onClick={onClose}>
            Not yet
          </Button>
          <Button
            loading={busy}
            onClick={() =>
              onConfirm(profile, {
                name,
                professional_title: title,
                email,
                phone,
                location,
                summary,
              })
            }
          >
            Confirm profile
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}