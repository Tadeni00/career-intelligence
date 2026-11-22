import { useCallback, useEffect, useState } from "react";
import {
  Alert,
  Badge,
  Button,
  Card,
  Code,
  Divider,
  Group,
  Loader,
  Paper,
  ScrollArea,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, downloadFile } from "../api";
import { useActiveProfile } from "../ProfileSelector";
import type { CoverLetter, Job } from "../types";
import { ProvenanceBadge, useProfileNames } from "../ProvenanceBadge";

/** Route param is the Job id — generation is `POST /jobs/{job_id}/cover-letter`. */
export function CoverLetterPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();

  const [job, setJob] = useState<Job | null>(null);
  const [letter, setLetter] = useState<CoverLetter | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { profiles } = useProfileNames();
  const [profileId] = useActiveProfile();

  const load = useCallback(async () => {
    if (!jobId) return;
    setLoading(true);
    setError(null);
    try {
      const j = await api<Job>(`/jobs/${jobId}`);
      setJob(j);
      const list = await api<CoverLetter[]>(`/cover-letters?job_id=${jobId}`);
      setLetter(list.length > 0 ? list[0] : null);
    } catch (e: any) {
      setError(e.message ?? "Could not load this job.");
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const generate = async () => {
    if (!job) return;
    setBusy(true);
    try {
      const created = await api<CoverLetter>(`/jobs/${job.id}/cover-letter`, {
        method: "POST",
        // Empty object when no profile is selected: the backend treats that as
        // the legacy shared-profile generation, never as a default profile.
        body: JSON.stringify(profileId === null ? {} : { cv_profile_id: profileId }),
      });
      setLetter(created);
      notifications.show({
        title: "Cover letter generated",
        message: "Review it below before sending.",
        color: "green",
      });
    } catch (e: any) {
      notifications.show({
        title: "Generation failed",
        message: e.message ?? "The cover letter could not be generated.",
        color: "red",
      });
    } finally {
      setBusy(false);
    }
  };

  const download = () => {
    if (!letter || !job) return;
    const company =
      (job.company ?? "company")
        .replace(/[^a-zA-Z0-9 -_]/g, "")
        .trim()
        .replace(/\s+/g, "-") || "company";
    void downloadFile(
      `/cover-letters/${letter.id}/download`,
      `${company}-cover-letter.txt`
    ).catch((e: Error) =>
      notifications.show({
        title: "Download failed",
        message: e.message,
        color: "red",
      })
    );
  };

  if (loading) return <Loader size="lg" />;
  if (error) return <Alert color="red" title="Not available">{error}</Alert>;

  const ready = letter?.validation_status === "VALID";

  return (
    <Card padding="lg" radius="md">
      <Group justify="space-between" mb="md" align="flex-start">
        <div>
          <Title order={2}>Cover letter</Title>
          <Text size="sm" c="dimmed">
            {job ? `${job.title}${job.company ? ` · ${job.company}` : ""}` : "Job"}
          </Text>
        </div>
        {letter && (
          <Group gap="sm">
            <ProvenanceBadge profileId={letter.cv_profile_id} profiles={profiles} size="sm" />
            <Badge
              variant="light"
              color={ready ? "green" : letter.validation_status === "REVIEW_REQUIRED" ? "yellow" : "red"}
            >
              {letter.validation_status}
            </Badge>
          </Group>
        )}
      </Group>

      {letter && (
        <Text size="xs" c="dimmed" mb="md">
          {letter.cv_profile_id === null
            ? "Written from your shared profile. Select a CV profile to generate this letter from one specific CV."
            : `Written from “${profiles.find((p) => p.id === letter.cv_profile_id)?.label ?? `CV profile #${letter.cv_profile_id}`}”, not from your shared profile.`}
        </Text>
      )}

      {!letter ? (
        <Stack>
          <Text c="dimmed">
            No cover letter has been generated for this job yet. It is written from your
            confirmed profile, so anything you have not evidenced is left out.
          </Text>
          <Group gap="xs" mb={4}>
            <Text size="xs" c="dimmed">New letters are written from</Text>
            <ProvenanceBadge profileId={profileId} profiles={profiles} size="xs" />
          </Group>
          <Group>
            <Button onClick={generate} loading={busy} disabled={busy || !job}>
              Generate cover letter
            </Button>
            <Button variant="subtle" onClick={() => navigate(`/jobs/${job?.id ?? ""}`)}>
              Back to job
            </Button>
          </Group>
        </Stack>
      ) : (
        <Stack>
          {!ready && (
            <Alert color="yellow" title="Review required before sending">
              Validation reported <Code>{letter.validation_status}</Code>. Check the warnings
              below — do not send it unverified.
            </Alert>
          )}

          {letter.validation_issues.length > 0 && (
            <Stack gap="xs">
              {letter.validation_issues.map((issue, i) => (
                <Alert
                  key={`${issue.code}-${i}`}
                  color={issue.severity === "error" ? "red" : "yellow"}
                  title={issue.code}
                  variant="light"
                >
                  {issue.message}
                  {issue.detail ? ` — ${issue.detail}` : ""}
                </Alert>
              ))}
            </Stack>
          )}

          <Divider label="Content" labelPosition="left" />
          <ScrollArea h={420}>
            <Paper withBorder p="md" radius="sm">
              <Text style={{ whiteSpace: "pre-wrap" }} size="sm">
                {letter.content}
              </Text>
            </Paper>
          </ScrollArea>

          <Divider />
          <Group gap="sm">
            <Button onClick={download} disabled={busy}>
              Download cover letter
            </Button>
            <Button variant="light" onClick={generate} loading={busy} disabled={busy}>
              Regenerate
            </Button>
            <Button variant="subtle" onClick={() => navigate(`/jobs/${letter.job_id}`)}>
              Back to job
            </Button>
            <Button
              variant="subtle"
              component={Link}
              to={`/tailored-cvs/${letter.job_id}`}
            >
              Tailored CV
            </Button>
          </Group>
        </Stack>
      )}
    </Card>
  );
}
