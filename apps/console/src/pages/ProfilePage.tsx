import { useEffect, useState } from "react";
import {
  Card, Group, Title, Text, TextInput, Select, Button, Alert, SimpleGrid,
  Loader, Textarea,
} from "@mantine/core";
import { useNavigate } from "react-router-dom";
import { IconX } from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { api, errorMessage } from "../api";
import type { ProfileSummary } from "../types";
import {
  profileToDraft, profileUpdatePayload, validateProfileDraft,
  type ProfileDraft,
} from "../profileEditing";

export function ProfilePage() {
  const [profile, setProfile] = useState<ProfileSummary | null>(null);
  const [draft, setDraft] = useState<ProfileDraft | null>(null);
  const [savedDraft, setSavedDraft] = useState<ProfileDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    let active = true;
    api<ProfileSummary>("/candidate")
      .then((data) => {
        if (!active) return;
        setProfile(data);
        const initial = profileToDraft(data);
        setDraft(initial);
        setSavedDraft(initial);
      })
      .catch((e) => {
        if (active) setError(errorMessage(e, "Could not load your career profile."));
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  const update = (field: keyof ProfileDraft, value: string) => {
    setDraft((current) => current ? { ...current, [field]: value } : current);
    setError(null);
  };

  const dirty = draft !== null && savedDraft !== null &&
    JSON.stringify(draft) !== JSON.stringify(savedDraft);

  const saveProfile = async () => {
    if (!draft || saving || !dirty) return;
    const validation = validateProfileDraft(draft);
    if (validation) { setError(validation); return; }
    setSaving(true);
    setError(null);
    try {
      const updated = await api<ProfileSummary>("/candidate", {
        method: "PUT",
        body: JSON.stringify(profileUpdatePayload(draft)),
      });
      setProfile(updated);
      const committed = profileToDraft(updated);
      setSavedDraft(committed);
      setDraft(committed);
      notifications.show({
        title: "Career preferences saved",
        message: "Your updated roles and locations can now be used to fill job searches.",
        color: "green",
      });
    } catch (e) {
      setError(errorMessage(e, "Could not save your career profile. Changes remain in the editor."));
    } finally {
      setSaving(false);
    }
  };

  const removeSkill = async (skillId: number) => {
    try {
      await api(`/candidate/skills/${skillId}`, { method: "DELETE" });
      setProfile((current) => current ? {
        ...current,
        skills: current.skills.filter((skill) => skill.id !== skillId),
      } : current);
    } catch (e) {
      notifications.show({
        title: "Could not remove skill",
        message: errorMessage(e, "Please try again."),
        color: "red",
      });
    }
  };

  if (loading) return <Loader size="lg" />;
  if (!profile || !draft || !savedDraft) {
    return <Alert color="red">{error ?? "Career profile unavailable. Reload to try again."}</Alert>;
  }

  return (
    <Card padding="lg" radius="md">
      <Title order={2} mb="xs">Career profile and search preferences</Title>
      <Text size="sm" c="dimmed" mb="md">
        Edit your profile and preferred roles, then select Save changes. Nothing
        is sent to the server while you type. Job discovery only uses these preferences
        when you explicitly choose Use profile preferences.
      </Text>

      {error && <Alert color="red" title="Profile update" mb="md">{error}</Alert>}

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md" mb="md">
        <TextInput label="Name" value={draft.name}
          onChange={(e) => update("name", e.currentTarget.value)} disabled={saving} />
        <TextInput label="Professional title" value={draft.professional_title}
          onChange={(e) => update("professional_title", e.currentTarget.value)} disabled={saving} />
        <TextInput label="Current location" value={draft.location}
          onChange={(e) => update("location", e.currentTarget.value)} disabled={saving} />
        <TextInput label="Years of experience" type="number" min={0} max={100}
          value={draft.years_of_experience}
          onChange={(e) => update("years_of_experience", e.currentTarget.value)} disabled={saving} />
        <Textarea label="Professional summary" value={draft.summary} minRows={3}
          onChange={(e) => update("summary", e.currentTarget.value)} disabled={saving} />
        <TextInput label="Minimum salary (numeric, currency not specified)"
          description="An unlabelled number is not used to exclude vacancies or compare currencies."
          type="number" min={0} value={draft.minimum_salary}
          onChange={(e) => update("minimum_salary", e.currentTarget.value)} disabled={saving} />
      </SimpleGrid>

      <Card withBorder padding="md" radius="md" mb="md">
        <Title order={4} mb="xs">Job search preferences</Title>
        <Text size="xs" c="dimmed" mb="md">
          List multiple target roles or locations separated by commas. When filling
          a new search, Career Intelligence uses the first preferred role and location;
          you can adjust them before searching. Remote-only is the only work-arrangement
          restriction supported by the current provider search.
        </Text>
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
          <TextInput label="Preferred roles (comma-separated)"
            placeholder="Data Scientist, Machine Learning Engineer"
            value={draft.preferred_roles} disabled={saving}
            onChange={(e) => update("preferred_roles", e.currentTarget.value)} />
          <TextInput label="Preferred locations (comma-separated)"
            placeholder="Lagos, Cotonou"
            value={draft.preferred_locations} disabled={saving}
            onChange={(e) => update("preferred_locations", e.currentTarget.value)} />
          <Select label="Preferred work arrangement"
            value={draft.remote_preference || "ANY"} disabled={saving}
            allowDeselect={false}
            data={[
              { value: "REMOTE", label: "Remote only" },
              { value: "HYBRID", label: "Prefer hybrid" },
              { value: "ONSITE", label: "Prefer on-site" },
              { value: "ANY", label: "Any arrangement" },
            ]}
            onChange={(value) => update("remote_preference", value ?? "ANY")} />
        </SimpleGrid>
      </Card>

      <Group gap="sm" mb="xl">
        <Button onClick={saveProfile} disabled={!dirty || saving} loading={saving}>
          Save changes
        </Button>
        <Button variant="default" disabled={!dirty || saving}
          onClick={() => { setDraft(savedDraft); setError(null); }}>
          Discard changes
        </Button>
        <Button variant="light" disabled={dirty || saving} onClick={() => navigate("/discover")}>
          Find jobs
        </Button>
        <Text size="xs" c={dirty ? "orange" : "dimmed"}>
          {dirty ? "Unsaved edits — save before leaving this page" : "All profile edits saved"}
        </Text>
      </Group>

      <Card withBorder padding="lg" radius="md" mb="md">
        <Title order={3} mb="sm">Skills</Title>
        <SimpleGrid cols={3} spacing="sm">
          {profile.skills.map((s) => (
            <Card key={s.id} withBorder padding="xs" radius="xs">
              <Text size="sm">{s.name}</Text>
              <Button
                variant="subtle"
                size="xs"
                rightSection={<IconX size={12} />}
                onClick={() => removeSkill(s.id)}
              >
                Remove
              </Button>
            </Card>
          ))}
        </SimpleGrid>
        <Button
          variant="filled"
          mb="sm"
          onClick={() => navigate("/cv")}
        >
          Add skills via CV upload
        </Button>
      </Card>

      <Card withBorder padding="lg" radius="md">
        <Title order={3} mb="sm">Experience</Title>
        <SimpleGrid cols={3} spacing="sm">
          {profile.experience.map((e) => (
            <Card key={e.id} withBorder padding="xs" radius="xs">
              <Text size="sm">
                {e.title} @ {e.company}
              </Text>
              <Text size="xs" c="dimmed">
                {e.start_date ?? "?"} -{" "}
                {e.end_date ?? "present"}
              </Text>
            </Card>
          ))}
        </SimpleGrid>
        <Button
          variant="contained"
          mb="sm"
          onClick={() => navigate("/cv")}
        >
          Add experience via CV upload
        </Button>
      </Card>

      <Card withBorder padding="lg" radius="md">
        <Title order={3} mb="sm">Education</Title>
        <SimpleGrid cols={3} spacing="sm">
          {profile.education.map((e) => (
            <Card key={e.id} withBorder padding="xs" radius="xs">
              <Text size="sm">
                {e.degree || ""} {e.field || ""} @ {e.institution}
              </Text>
            </Card>
          ))}
        </SimpleGrid>
        <Button
          variant="contained"
          mb="sm"
          onClick={() => navigate("/cv")}
        >
          Add education via CV upload
        </Button>
      </Card>

      <Card withBorder padding="lg" radius="md">
        <Title order={3} mb="sm">Projects</Title>
        <SimpleGrid cols={3} spacing="sm">
          {profile.projects.map((p) => (
            <Card key={p.id} withBorder padding="xs" radius="xs">
              <Text size="sm">{p.name}</Text>
              <Text size="xs" c="dimmed">{p.technologies.join(", ")}</Text>
            </Card>
          ))}
        </SimpleGrid>
      </Card>
    </Card>
  );
}