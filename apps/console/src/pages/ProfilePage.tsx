import { useEffect, useState } from "react";
import {
  Card,
  Group,
  Title,
  Text,
  TextInput,
  Select,
  NumberInput,
  Button,
  Alert,
  SimpleGrid,
} from "@mantine/core";
import { useNavigate } from "react-router-dom";
import { IconX } from "@tabler/icons-react";
import { notifications } from "@mantine/notifications";
import { api } from "../api";
import type { ProfileSummary } from "../types";

export function ProfilePage() {
  const [profile, setProfile] = useState<ProfileSummary>({
    id: 0,
    name: "",
    professional_title: "",
    email: "",
    phone: "",
    location: "",
    summary: "",
    years_of_experience: null,
    preferred_roles: [],
    preferred_locations: [],
    remote_preference: "",
    minimum_salary: null,
    skills: [],
    experience: [],
    education: [],
    projects: [],
  });

  const [errors, setErrors] = useState<Record<string, string>>({});
  const navigate = useNavigate();

  useEffect(() => {
    api<ProfileSummary>("/candidate").then(setProfile).catch((e) =>
      notifications.show({ title: "Failed", message: e.message, color: "red" })
    );
  }, []);

  const saveProfile = async (values: any) => {
    setErrors({});
    try {
      await api("/candidate", {
        method: "PUT",
        body: JSON.stringify(values),
      });
      setProfile({ ...profile, ...values });
    } catch (e: any) {
      setErrors(e.response?.data?.detail ?? e.message);
    }
  };

  return (
    <Card padding="lg" radius="md">
      <Title order={2} mb="md">Career Profile</Title>

      {Object.keys(errors).length > 0 && (
        <Alert color="red" title="Save failed">
          {Object.values(errors).join("; ")}
        </Alert>
      )}

      <Group gap="md">
        <TextInput
          label="Name"
          value={profile.name}
          onChange={(e) =>
            saveProfile({ ...profile, name: e.target.value })
          }
        />
        <TextInput
          label="Professional title"
          value={profile.professional_title ?? ""}
          onChange={(e) =>
            saveProfile({ ...profile, professional_title: e.target.value })
          }
        />
        <TextInput
          label="Location"
          value={profile.location ?? ""}
          onChange={(e) =>
            saveProfile({ ...profile, location: e.target.value })
          }
        />
        <TextInput
          label="Summary"
          value={profile.summary ?? ""}
          onChange={(e) =>
            saveProfile({ ...profile, summary: e.target.value })
          }
        />
        <NumberInput
          label="Years of experience"
          value={profile.years_of_experience ?? 0}
          onChange={(value) =>
            saveProfile({
              ...profile,
              years_of_experience: value === "" ? null : Number(value),
            })
          }
        />
        <TextInput
          label="Minimum salary"
          value={profile.minimum_salary ?? ""}
          onChange={(e) =>
            saveProfile({
              ...profile,
              minimum_salary: e.target.value
                ? Number(e.target.value.replace(/[^0-9.-]/g, ""))
                : null,
            })
          }
        />
      </Group>

      <Group gap="md">
        <TextInput
          label="Preferred roles (comma-separated)"
          value={profile.preferred_roles.join(", ")}
          onChange={(e) =>
            saveProfile({
              ...profile,
              preferred_roles: e.target.value
                .split(",")
                .map((s: string) => s.trim())
                .filter((s: string) => s.length > 0),
            })
          }
        />
        <TextInput
          label="Preferred locations (comma-separated)"
          value={profile.preferred_locations.join(", ")}
          onChange={(e) =>
            saveProfile({
              ...profile,
              preferred_locations: e.target.value
                .split(",")
                .map((s: string) => s.trim())
                .filter((s: string) => s.length > 0),
            })
        }
        />
        <Select
          label="Remote preference"
          value={profile.remote_preference ?? ""}
          data={[
            { value: "REMOTE", label: "Remote only" },
            { value: "HYBRID", label: "Hybrid" },
            { value: "ONSITE", label: "On-site only" },
            { value: "ANY", label: "Any" },
          ]}
          onChange={(value) =>
            saveProfile({ ...profile, remote_preference: value })
          }
        />
      </Group>

      <Card withBorder padding="lg" radius="md" mb="md">
        <Title order={3} mb="sm">Skills</Title>
        <SimpleGrid cols={3} spacing="sm">
          {profile.skills.map((s) => (
            <Card key={s.id} withBorder padding="xs" radius="xs">
              <Text size="sm">{s.name}</Text>
              <Button
                variant="bare"
                size="xs"
                rightSection={<IconX size={12} />}
                onClick={() =>
                  api(`/candidate/skills/${s.id}`, { method: "DELETE" }).then(
                    () => setProfile({
                      ...profile,
                      skills: profile.skills.filter((sk) => sk.id !== s.id),
                    })
                  )
                }
              >
                Remove
              </Button>
            </Card>
          ))}
        </SimpleGrid>
        <Button
          variant="contained"
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