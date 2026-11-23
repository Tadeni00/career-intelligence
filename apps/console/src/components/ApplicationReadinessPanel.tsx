import { useState } from "react";
import { Badge, Button, Card, Checkbox, Group, Stack, Text, Title } from "@mantine/core";
import { applicationReadinessSignals, PERSONAL_VERIFICATIONS } from "../applicationReadiness";
import type { Freshness, Job, MatchResult } from "../types";

export function ApplicationReadinessPanel({
  job,
  match,
  freshness = null,
}: {
  job: Job;
  match: MatchResult | null;
  freshness?: Freshness | null;
}) {
  // Deliberately local and temporary: do not imply a durable or independently
  // verified eligibility decision. Key the panel by job ID in each parent.
  const [checked, setChecked] = useState<string[]>([]);
  const signals = applicationReadinessSignals(job, match, freshness);

  return (
    <Card withBorder padding="md" radius="md" mt="md" mb="md">
      <Group justify="space-between" align="center" mb="xs">
        <Title order={3}>Before you apply</Title>
        <Badge color="gray" variant="light">Personal review</Badge>
      </Group>
      <Text size="sm" c="dimmed" mb="md">
        Confirm the requirements at the original employer posting. The information
        below is not a work-permit decision, a live vacancy check, or proof
        you qualify. A remote listing can still be restricted to specific countries.
      </Text>
      <Stack gap="sm">
        {signals.map((signal) => (
          <Group key={signal.key} align="flex-start" gap="sm" wrap="nowrap">
            <Badge
              color={signal.status === "available" ? "teal" : signal.status === "review" ? "yellow" : "gray"}
              variant="light"
              size="sm"
              style={{ flexShrink: 0 }}
            >
              {signal.status === "available" ? "Link" : signal.status === "review" ? "Review" : "Unknown"}
            </Badge>
            <div>
              <Text size="sm" fw={600}>{signal.label}</Text>
              <Text size="xs" c="dimmed">{signal.explanation}</Text>
            </div>
          </Group>
        ))}
      </Stack>

      <Title order={4} mt="lg" mb="xs">What have you personally checked?</Title>
      <Text size="xs" c="dimmed" mb="sm">
        These checkboxes are only a temporary personal guide. They reset when
        you leave or switch jobs, and they are not saved as verified eligibility.
      </Text>
      <Stack gap="xs">
        {PERSONAL_VERIFICATIONS.map(({ key, label }) => (
          <Checkbox
            key={key}
            label={label}
            checked={checked.includes(key)}
            onChange={(event) => setChecked((previous) =>
              event.currentTarget.checked
                ? [...previous, key]
                : previous.filter((item) => item !== key)
            )}
          />
        ))}
      </Stack>
      <Group mt="md" justify="space-between">
        <Text size="sm" c="dimmed">
          {checked.length} of {PERSONAL_VERIFICATIONS.length} checks noted by you
        </Text>
        <Button size="xs" variant="subtle" onClick={() => setChecked([])} disabled={checked.length === 0}>
          Clear my checks
        </Button>
      </Group>
    </Card>
  );
}
