import { useEffect, useState } from "react";
import {
  Card,
  Group,
  Title,
  Text,
  Select,
  Button,
  Alert,
  Badge,
  Loader,
  SimpleGrid,
  Progress,
} from "@mantine/core";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useActiveProfile } from "../ProfileSelector";
import { useProfileNames, ProvenanceBadge } from "../ProvenanceBadge";
import { useRunMatch } from "../runMatch";
import type { Job, MatchResult } from "../types";

const STATUS_COLORS: Record<string, string> = {
  APPLY: "green",
  APPLY_WITH_TAILORING: "blue",
  STRETCH: "orange",
  SKIP: "red",
};

export function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [matches, setMatches] = useState<Record<number, MatchResult>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const [profileId] = useActiveProfile();
  const { profiles } = useProfileNames();
  const { run, busyId } = useRunMatch(profileId, profiles);

  useEffect(() => {
    setLoading(true);
    api<Job[]>("/jobs")
      .then(setJobs)
      .catch((e) => setError(errorMessage(e, "Could not load jobs.")))
      .finally(() => setLoading(false));
  }, []);

  // A score already loaded for this scope is shown as-is. Pressing the button
  // again calculates a *new* match record rather than re-reading the old one,
  // which is why it is labelled differently once a result exists.
  const matchJob = async (jobId: number) => {
    const result = await run(jobId);
    if (result) {
      setMatches((prev) => ({ ...prev, [jobId]: result }));
    }
  };

  return (
    <Card padding="lg" radius="md">
      <Group justify="space-between" align="center" mb="md">
        <Title order={2}>Jobs</Title>
        <Button onClick={() => navigate("/jobs/import")}>Import a vacancy</Button>
      </Group>

      <Group gap="xs" mb="md">
        <Text size="xs" c="dimmed">Matches are calculated against</Text>
        <ProvenanceBadge profileId={profileId} profiles={profiles} size="xs" />
        <Text size="xs" c="dimmed">
          — change it on the CV page.
        </Text>
      </Group>

      <Group gap="md" mb="md">
        <Select
          label="Filter by recommendation"
          value={useParams<{ status?: string }>().status ?? ""}
          data={[
            { value: "", label: "All" },
            { value: "APPLY", label: "Apply" },
            { value: "APPLY_WITH_TAILORING", label: "Apply with tailoring" },
            { value: "STRETCH", label: "Stretch" },
            { value: "SKIP", label: "Skip" },
          ]}
          onChange={(value) =>
            navigate({ pathname: "/jobs", search: `status=${value ?? ""}` })
          }
        />

        <Select
          label="Sort by"
          value={useParams<{ sort?: string }>().sort ?? "newest"}
          data={[
            { value: "newest", label: "Newest first" },
            { value: "match", label: "Match score" },
            { value: "oldest", label: "Oldest first" },
          ]}
          onChange={(value) =>
            navigate({ pathname: "/jobs", search: `sort=${value ?? ""}` })
          }
        />
      </Group>

      {error && <Alert color="red">{error}</Alert>}

      {loading ? (
        <Loader size="lg" />
      ) : jobs.length === 0
        ? <Text c="dimmed">No jobs yet. Import a vacancy using its description and original link.</Text>
        : <SimpleGrid cols={{ base: 2, md: 3, lg: 4 }}>
            {jobs.map((job) => {
              const match = matches[job.id];
              return (
                <Card key={job.id} withBorder padding="sm" radius="sm">
                  <Group justify="space-between" align="center">
                    <Group gap="sm">
                      <Text size="sm" fw={600}>
                        {job.title} at {job.company ?? "Unknown"}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {job.location ?? ""} {job.remote_status ?? ""}
                      </Text>
                    </Group>
                    <Group gap="2">
                      {match && (
                        <Badge color={STATUS_COLORS[match.recommendation] ?? "gray"} variant="light">
                          {RECOMMENDATION_LABELS[match.recommendation] ?? match.recommendation}
                        </Badge>
                      )}
                      <Progress size="sm" value={match?.overall_score ?? 0}>
                        <Progress.Label>
                          {`${(match?.overall_score ?? 0).toFixed(0)}/100`}
                        </Progress.Label>
                      </Progress>
                    </Group>
                  </Group>
                  <Group gap="xs" mt={4}>
                    <Button
                      variant="subtle"
                      size="xs"
                      loading={busyId === job.id}
                      disabled={busyId !== null && busyId !== job.id}
                      onClick={() => matchJob(job.id)}
                    >
                      {match ? "Re-run match" : "Run match"}
                    </Button>
                    <Button
                      variant="subtle"
                      size="xs"
                      onClick={() => navigate(`/jobs/${job.id}`)}
                    >
                      View
                    </Button>
                  </Group>
                </Card>
              );
            })}
          </SimpleGrid>
      }

      <Button
        variant="contained"
        mb="md"
        onClick={() => navigate("/cv")}
      >
        Add a CV first
      </Button>
    </Card>
  );
}

const RECOMMENDATION_LABELS: Record<string, string> = {
  APPLY: "Apply",
  APPLY_WITH_TAILORING: "Apply with tailoring",
  STRETCH: "Stretch",
  SKIP: "Skip",
};