import { useEffect, useState } from "react";
import {
  Card,
  Group,
  Title,
  Text,
  Badge,
  SimpleGrid,
  Stack,
  ThemeIcon,
  RingProgress,
  Table,
  Button,
  Alert,
  Loader,
} from "@mantine/core";
import {
  IconBriefcase,
  IconCheck,
  IconAlertTriangle,
  IconX,
  IconArrowRight,
  IconUser,
} from "@tabler/icons-react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Dashboard } from "../types";

const RECOMMENDATION_COLORS: Record<string, string> = {
  APPLY: "green",
  APPLY_WITH_TAILORING: "blue",
  STRETCH: "orange",
  SKIP: "red",
};

const RECOMMENDATION_LABELS: Record<string, string> = {
  APPLY: "Apply",
  APPLY_WITH_TAILORING: "Apply with tailoring",
  STRETCH: "Stretch",
  SKIP: "Skip",
};

export function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    api<Dashboard>("/dashboard")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <Alert color="red" title="Failed to load dashboard">{error}</Alert>;
  if (!data) return <Loader size="lg" />;

  const { stats, opportunities, recent_applications, warnings } = data;

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <Title order={2}>Dashboard</Title>
        <Button variant="subtle" onClick={() => navigate("/jobs")}>
          View all jobs
        </Button>
      </Group>

      {warnings.length > 0 && (
        <Alert color="yellow" title="Profile incomplete" icon={<IconUser size={16} />}>
          {warnings.join(" ")}
        </Alert>
      )}

      <SimpleGrid cols={{ base: 2, sm: 4, lg: 8 }}>
        <StatCard icon={<IconBriefcase size={20} />} label="Jobs" value={stats.jobs} />
        <StatCard icon={<IconCheck size={20} />} label="Apply" value={stats.apply} color="green" />
        <StatCard
          icon={<IconCheck size={20} />}
          label="Tailor"
          value={stats.apply_with_tailoring}
          color="blue"
        />
        <StatCard
          icon={<IconAlertTriangle size={20} />}
          label="Stretch"
          value={stats.stretch}
          color="orange"
        />
        <StatCard icon={<IconX size={20} />} label="Skip" value={stats.skip} color="red" />
        <StatCard
          icon={<IconBriefcase size={20} />}
          label="Applications"
          value={stats.applications}
          color="violet"
        />
        <StatCard
          icon={<IconCheck size={20} />}
          label="Interviews"
          value={stats.interviews}
          color="cyan"
        />
        <StatCard
          icon={<IconCheck size={20} />}
          label="Offers"
          value={stats.offers}
          color="green"
        />
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Card withBorder padding="lg" radius="md">
          <Title order={4} mb="md">Today's Opportunities</Title>
          {opportunities.length === 0 ? (
            <Text c="dimmed">No jobs yet. Add a job to get started.</Text>
          ) : (
            <Stack gap="sm">
              {opportunities.map((opp) => (
                <OpportunityRow key={opp.job_id} opp={opp} onNavigate={navigate} />
              ))}
            </Stack>
          )}
        </Card>

        <Card withBorder padding="lg" radius="md">
          <Title order={4} mb="md">Recent Applications</Title>
          {recent_applications.length === 0 ? (
            <Text c="dimmed">No applications yet.</Text>
          ) : (
            <Table striped highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Job</Table.Th>
                  <Table.Th>Status</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {recent_applications.map((app) => (
                  <Table.Tr key={app.id}>
                    <Table.Td>{app.job?.title ?? `Job ${app.job_id}`}</Table.Td>
                    <Table.Td>
                      <Badge color={statusColor(app.status)} variant="light">
                        {app.status}
                      </Badge>
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
        </Card>
      </SimpleGrid>
    </Stack>
  );
}

function StatCard({
  icon,
  label,
  value,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
  color?: string;
}) {
  return (
    <Card withBorder padding="sm" radius="md">
      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
            {label}
          </Text>
          <Text size="xl" fw={700}>
            {value}
          </Text>
        </Stack>
        <ThemeIcon color={color ?? "gray"} variant="light" size="lg" radius="md">
          {icon}
        </ThemeIcon>
      </Group>
    </Card>
  );
}

function OpportunityRow({
  opp,
  onNavigate,
}: {
  opp: Dashboard["opportunities"][number];
  onNavigate: (path: string) => void;
}) {
  const color = RECOMMENDATION_COLORS[opp.recommendation] ?? "gray";
  return (
    <Card withBorder padding="sm" radius="sm">
      <Group justify="space-between" align="center">
        <Group gap="sm">
          <RingProgress
            size={48}
            thickness={5}
            roundCaps
            sections={[{ value: opp.overall_score, color }]}
            label={
              <Text size="xs" ta="center" fw={700}>
                {opp.overall_score}%
              </Text>
            }
          />
          <Stack gap={2}>
            <Text size="sm" fw={600}>
              {opp.title}
            </Text>
            <Text size="xs" c="dimmed">
              {opp.company} {opp.location ? `· ${opp.location}` : ""}
            </Text>
          </Stack>
        </Group>
        <Group gap="sm">
          <Badge color={color} variant="light">
            {RECOMMENDATION_LABELS[opp.recommendation] ?? opp.recommendation}
          </Badge>
          <Button
            variant="subtle"
            size="xs"
            rightSection={<IconArrowRight size={14} />}
            onClick={() => onNavigate(`/jobs/${opp.job_id}`)}
          >
            View
          </Button>
        </Group>
      </Group>
    </Card>
  );
}

function statusColor(status: string): string {
  const map: Record<string, string> = {
    INTERESTED: "gray",
    READY_TO_APPLY: "blue",
    APPLIED: "indigo",
    INTERVIEW: "violet",
    OFFER: "green",
    REJECTED: "red",
    WITHDRAWN: "orange",
  };
  return map[status] ?? "gray";
}
