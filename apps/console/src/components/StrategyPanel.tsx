import { useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Card,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { api } from "../api";
import { ProvenanceBadge, useProfileNames } from "../ProvenanceBadge";
import type {
  ApplicationStrategy,
  StrategyBlocker,
  StrategyGap,
} from "../types";

const DECISION_COLOR: Record<string, string> = {
  APPLY: "green",
  APPLY_WITH_TAILORING: "blue",
  STRETCH: "orange",
  SKIP: "red",
};

const GAP_COLOR: Record<string, string> = {
  REQUIRED_GAP: "red",
  PREFERRED_GAP: "orange",
  SOFT_SIGNAL_GAP: "gray",
};

function GapList({ gaps }: { gaps: StrategyGap[] }) {
  if (gaps.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        No gaps recorded by the deterministic match.
      </Text>
    );
  }
  return (
    <Stack gap={6}>
      {gaps.map((gap) => (
        <Card key={`${gap.requirement_id}-${gap.requirement_name}`} withBorder padding="xs" radius="xs">
          <Group justify="space-between" gap="xs" wrap="nowrap" align="flex-start">
            <div style={{ minWidth: 0 }}>
              <Text size="sm" fw={600}>{gap.requirement_name}</Text>
              <Text size="xs" c="dimmed">{gap.statement}</Text>
            </div>
            <Badge size="xs" variant="light" color={GAP_COLOR[gap.severity] ?? "gray"}>
              {gap.severity.replace("_GAP", "")}
            </Badge>
          </Group>
        </Card>
      ))}
    </Stack>
  );
}

function BlockerList({ blockers }: { blockers: StrategyBlocker[] }) {
  if (blockers.length === 0) {
    return (
      <Text size="sm" c="dimmed">
        None identified.
      </Text>
    );
  }
  return (
    <Stack gap={6}>
      {blockers.map((blocker) => (
        <Card key={`${blocker.requirement_id}-${blocker.requirement_name}`} withBorder padding="xs" radius="xs">
          <Text size="sm" fw={600} c="red">{blocker.requirement_name}</Text>
          <Text size="xs" c="dimmed">{blocker.statement}</Text>
        </Card>
      ))}
    </Stack>
  );
}

/**
 * Application Strategy (V2). Interpretation of the existing deterministic
 * decision: strengths, gaps, blockers, transferable evidence, emphasis,
 * do-not-claim restrictions and next steps.
 *
 * Scoped to one evidence source. `cvProfileId` null reads the shared Candidate
 * record; an id reads and, when stale, rebuilds that profile's own strategy.
 * The two chains are never mixed: a strategy is only ever produced from a
 * match in the same scope.
 */
export function StrategyPanel({
  jobId,
  cvProfileId = null,
}: {
  jobId: string;
  cvProfileId?: number | null;
}) {
  const [strategy, setStrategy] = useState<ApplicationStrategy | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { profiles } = useProfileNames();

  // The scope is part of the identity of what is fetched: switching profile
  // must re-read, never reuse the previous profile's chain.
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    const query = cvProfileId === null ? "" : `?cv_profile_id=${cvProfileId}`;
    api<ApplicationStrategy>(`/jobs/${jobId}/strategy${query}`)
      .then((data) => {
        if (active) setStrategy(data);
      })
      .catch((err: Error) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [jobId, cvProfileId]);

  if (loading) return <Loader size="sm" />;

  if (error) {
    return (
      <Alert color="yellow" title="Application strategy unavailable">
        <Stack gap="xs">
          <Text size="sm">{error}</Text>
          <Text size="sm">
            {cvProfileId === null
              ? "Run the match for this job to generate a strategy."
              : "Run the match for this job against the selected CV profile to generate its strategy."}
          </Text>
        </Stack>
      </Alert>
    );
  }

  if (!strategy) return null;

  return (
    <Card withBorder padding="lg" radius="md">
      <Group justify="space-between" mb="sm" align="flex-start">
        <Title order={3}>Application strategy</Title>
        <Group gap="xs">
          <Badge variant="light" color={DECISION_COLOR[strategy.decision] ?? "gray"}>
            {strategy.decision}
          </Badge>
          <Badge variant="outline" color={strategy.status === "CURRENT" ? "green" : "orange"}>
            {strategy.status}
          </Badge>
        </Group>
      </Group>

      <Group gap="xs" mb="xs">
        <Text size="xs" c="dimmed" tt="uppercase" fw={700}>
          Built from
        </Text>
        <ProvenanceBadge profileId={cvProfileId} profiles={profiles} size="xs" />
      </Group>

      <Text size="sm" mb="lg">
        {strategy.decision_summary || "No explanation available."}
      </Text>

      <SimpleGrid cols={{ base: 1, md: 2 }} spacing="lg">
        <Stack gap="sm">
          <div>
            <Title order={5} mb={4}>Why this recommendation</Title>
            {strategy.strengths.length === 0 ? (
              <Text size="sm" c="dimmed">No requirement was matched as strong.</Text>
            ) : (
              <Stack gap={4}>
                {strategy.strengths.map((s) => (
                  <div key={`${s.requirement_id}-${s.requirement_name}`}>
                    <Text size="sm">
                      <Text span fw={600}>{s.requirement_name}</Text>
                      <Text span c="dimmed"> — {s.evidence_ids.join(", ")}</Text>
                    </Text>
                  </div>
                ))}
              </Stack>
            )}
          </div>

          <div>
            <Title order={5} mb={4}>Gaps</Title>
            <GapList gaps={strategy.gaps} />
          </div>

          <div>
            <Title order={5} mb={4}>Blockers</Title>
            <BlockerList blockers={strategy.blockers} />
          </div>
        </Stack>

        <Stack gap="sm">
          {strategy.transferable_evidence.length > 0 && (
            <div>
              <Title order={5} mb={4}>Transferable evidence</Title>
              <Stack gap={4}>
                {strategy.transferable_evidence.map((t) => (
                  <Text key={`${t.requirement_id}-${t.requirement_name}`} size="sm">
                    <Text span fw={600}>{t.requirement_name}</Text>
                    <Text span c="dimmed">
                      {" "}— {t.relationship.toLowerCase()} via {t.evidence_ids.join(", ")}
                    </Text>
                  </Text>
                ))}
              </Stack>
            </div>
          )}

          {strategy.evidence_emphasis.length > 0 && (
            <div>
              <Title order={5} mb={4}>Application emphasis</Title>
              <Stack gap={2}>
                {strategy.evidence_emphasis
                  .slice()
                  .sort((a, b) => a.priority - b.priority)
                  .map((e) => (
                    <Text key={e.priority} size="sm">
                      {e.priority}. {e.evidence_ids.join(", ")}
                    </Text>
                  ))}
              </Stack>
            </div>
          )}

          {strategy.claim_restrictions.length > 0 && (
            <div>
              <Title order={5} mb={4}>Do not claim</Title>
              <Stack gap={2}>
                {strategy.claim_restrictions.map((r) => (
                  <Text key={`${r.requirement_id}-${r.subject}`} size="sm" c="red">
                    {r.subject}
                  </Text>
                ))}
              </Stack>
            </div>
          )}

          {strategy.review_notes.length > 0 && (
            <div>
              <Title order={5} mb={4}>Review</Title>
              <Stack gap={4}>
                {strategy.review_notes.map((note, i) => (
                  <Text key={i} size="xs" c="dimmed">
                    [{note.severity}] {note.statement}
                  </Text>
                ))}
              </Stack>
            </div>
          )}

          <div>
            <Title order={5} mb={4}>Recommended next steps</Title>
            <Stack gap={4}>
              {strategy.actions
                .slice()
                .sort((a, b) => a.priority - b.priority)
                .map((action) => (
                  <div key={action.priority}>
                    <Text size="sm">
                      {action.priority}. {action.action}
                    </Text>
                    <Text size="xs" c="dimmed">{action.rationale}</Text>
                  </div>
                ))}
            </Stack>
          </div>
        </Stack>
      </SimpleGrid>
    </Card>
  );
}