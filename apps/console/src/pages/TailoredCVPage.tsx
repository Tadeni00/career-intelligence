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
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, downloadFile } from "../api";
import {
  belongsToJob,
  resolveTailoredCVTarget,
  selectJobCVs,
} from "../tailoredCvRouting";
import { useActiveProfile } from "../ProfileSelector";
import type { Job, TailoredCV } from "../types";
import { ProvenanceBadge, useProfileNames } from "../ProvenanceBadge";

/**
 * Two routes, two meanings, no guessing:
 *
 *   /jobs/:jobId/tailored-cv  -> the CV workflow for exactly that job
 *   /tailored-cvs/:id         -> exactly that TailoredCV document
 *
 * Job ids and tailored-CV ids are separate id spaces that happen to overlap
 * (job 13 and tailored CV 13 both exist and are different rows), so the route
 * a request arrived on is the only thing that decides which entity `:id` names.
 * A document lookup that fails is reported, never re-read as a job id.
 */
export function TailoredCVPage() {
  const { id, jobId } = useParams<{ id?: string; jobId?: string }>();
  const navigate = useNavigate();

  const target = resolveTailoredCVTarget({ id, jobId });
  const targetKind = target.kind;
  const targetId =
    targetKind === "document"
      ? target.docId
      : targetKind === "job"
        ? target.jobId
        : 0;
  const invalidReason = target.kind === "invalid" ? target.reason : null;

  const [job, setJob] = useState<Job | null>(null);
  const [doc, setDoc] = useState<TailoredCV | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { profiles } = useProfileNames();
  const [profileId] = useActiveProfile();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setDoc(null);
    setJob(null);
    try {
      if (targetKind === "invalid") {
        setError(invalidReason ?? "This link does not identify a tailored CV.");
        return;
      }

      if (targetKind === "document") {
        // Document route. Only a TailoredCV id is valid here; if there is no such
        // document that is an error, never a job id to reinterpret.
        let d: TailoredCV;
        try {
          d = await api<TailoredCV>(`/tailored-cvs/${targetId}`);
        } catch {
          throw new Error(
            `Tailored CV ${targetId} was not found. It may have been deleted.`
          );
        }
        setDoc(d);
        setJob(await api<Job>(`/jobs/${d.job_id}`).catch(() => null));
        return;
      }

      // Job-scoped route.
      let j: Job;
      try {
        j = await api<Job>(`/jobs/${targetId}`);
      } catch {
        throw new Error(`Job ${targetId} was not found.`);
      }
      setJob(j);
      // Ask for this job's documents, then keep only those the backend itself
      // associates with this job.
      const list = await api<TailoredCV[]>(`/tailored-cvs?job_id=${targetId}`);
      setDoc(selectJobCVs(list, targetId)[0] ?? null);
    } catch (e: any) {
      setError(e.message ?? "Could not load the tailored CV.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetKind, targetId, id, jobId]);

  useEffect(() => {
    void load();
  }, [load]);

  const generate = async () => {
    if (targetKind !== "job" || !job) return;
    setBusy(true);
    try {
      const created = await api<TailoredCV>(`/jobs/${job.id}/tailor-cv`, {
        method: "POST",
        // Empty object when no profile is selected: the backend treats that as
        // the legacy shared-profile generation, never as a default profile.
        body: JSON.stringify(profileId === null ? {} : { cv_profile_id: profileId }),
      });
      if (!belongsToJob(created, job.id)) {
        throw new Error(
          `The generated document belongs to job ${created.job_id}, not job ${job.id}.`
        );
      }
      setDoc(created);
      notifications.show({
        title: "Tailored CV generated",
        message: `Version ${created.version} is ready to review.`,
        color: "green",
      });    } catch (e: any) {
      notifications.show({
        title: "Generation failed",
        message: e.message ?? "The tailored CV could not be generated.",
        color: "red",
      });
    } finally {
      setBusy(false);
    }
  };

  const regenerate = async () => {
    if (!doc) return;
    setBusy(true);
    try {
      const created = await api<TailoredCV>(`/tailored-cvs/${doc.id}/regenerate`, {
        method: "POST",
      });
      if (!belongsToJob(created, doc.job_id)) {
        throw new Error(
          `The regenerated document belongs to job ${created.job_id}, not job ${doc.job_id}.`
        );
      }
      setDoc(created);
      notifications.show({
        title: "Regenerated",
        message: `Version ${created.version} is ready to review.`,
        color: "green",
      });
    } catch (e: any) {
      notifications.show({
        title: "Regeneration failed",
        message: e.message ?? "The tailored CV could not be regenerated.",
        color: "red",
      });
    } finally {
      setBusy(false);
    }
  };

  const download = () => {
    if (!doc) return;
    void downloadFile(`/tailored-cvs/${doc.id}/download`, doc.filename).catch(
      (e: Error) =>
        notifications.show({
          title: "Download failed",
          message: e.message,
          color: "red",
        })
    );
  };

  if (loading) return <Loader size="lg" />;
  if (error) return <Alert color="red" title="Not available">{error}</Alert>;

  const ready = doc?.validation_status === "VALID";
  // On the job-scoped route this is the job we were asked for; on the document
  // route it is the job the backend says owns the document.
  const owningJobId = doc ? doc.job_id : job ? job.id : targetId;

  return (
    <Card padding="lg" radius="md">
      <Group justify="space-between" mb="md" align="flex-start">
        <div>
          <Title order={2}>
            Tailored CV{targetKind === "document" ? ` #${doc?.id ?? targetId}` : ""}
          </Title>
          <Text size="sm" c="dimmed">
            {job
              ? `${job.title}${job.company ? ` · ${job.company}` : ""} · job ${owningJobId}`
              : `Job ${owningJobId}`}
          </Text>
        </div>
        {doc && (
          <Group gap="sm">
            <ProvenanceBadge profileId={doc.cv_profile_id} profiles={profiles} size="sm" />
            <Badge variant="light" color="gray">
              v{doc.version}
            </Badge>
            <Badge
              variant="light"
              color={ready ? "green" : doc.validation_status === "REVIEW_REQUIRED" ? "yellow" : "red"}
            >
              {doc.validation_status}
            </Badge>
          </Group>
        )}
      </Group>

      {doc && (
        <Text size="xs" c="dimmed" mb="md">
          {doc.cv_profile_id === null
            ? "Written from your shared profile. Select a CV profile to generate this document from one specific CV."
            : `Written from “${profiles.find((p) => p.id === doc.cv_profile_id)?.label ?? `CV profile #${doc.cv_profile_id}`}”, not from your shared profile.`}
        </Text>
      )}

      {!doc ? (
        <Stack>
          <Text c="dimmed">
            No tailored CV has been generated for this job yet. Generating one selects the
            relevant experience and skills from your confirmed profile.
          </Text>
          <Group gap="xs" mb={4}>
            <Text size="xs" c="dimmed">New documents are written from</Text>
            <ProvenanceBadge profileId={profileId} profiles={profiles} size="xs" />
          </Group>
          <Group>
            <Button
              onClick={generate}
              loading={busy}
              disabled={busy || !job || targetKind !== "job"}
            >
              Generate tailored CV
            </Button>
            <Button variant="subtle" onClick={() => navigate(`/jobs/${owningJobId}`)}>
              Back to job
            </Button>
          </Group>
        </Stack>
      ) : (
        <Stack>
          {!ready && (
            <Alert color="yellow" title="Review required before sending">
              Validation reported{" "}
              <Code>{doc.validation_status}</Code>. Check the warnings below before you use
              this document — do not send it unverified.
            </Alert>
          )}

          {doc.summary && <Text size="sm">{doc.summary}</Text>}

          {doc.validation_issues.length > 0 && (
            <>
              <Divider label="Validation issues" labelPosition="left" />
              <Stack gap="xs">
                {doc.validation_issues.map((issue, i) => (
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
            </>
          )}

          {doc.changes_summary.length > 0 && (
            <>
              <Divider label="What changed for this job" labelPosition="left" />
              <Stack gap={4}>
                {doc.changes_summary.map((change, i) => (
                  <Text key={i} size="sm">
                    • {change}
                  </Text>
                ))}
              </Stack>
            </>
          )}

          {doc.analysis && (
            <>
              <Divider label="Analysis" labelPosition="left" />
              <Stack gap="xs">
                {doc.analysis.evidence_to_emphasize.length > 0 && (
                  <div>
                    <Text size="sm" fw={600}>
                      Evidence to emphasise
                    </Text>
                    {doc.analysis.evidence_to_emphasize.map((x, i) => (
                      <Text key={i} size="sm">
                        • {x}
                      </Text>
                    ))}
                  </div>
                )}
                {doc.analysis.missing_requirements.length > 0 && (
                  <div>
                    <Text size="sm" fw={600}>
                      Requirements you have not evidenced
                    </Text>
                    {doc.analysis.missing_requirements.map((x, i) => (
                      <Text key={i} size="sm">
                        • {x}
                      </Text>
                    ))}
                  </div>
                )}
                {doc.analysis.potential_problems.length > 0 && (
                  <div>
                    <Text size="sm" fw={600}>
                      Potential problems
                    </Text>
                    {doc.analysis.potential_problems.map((x, i) => (
                      <Text key={i} size="sm">
                        • {x}
                      </Text>
                    ))}
                  </div>
                )}
              </Stack>
            </>
          )}

          <Divider />
          <Group gap="sm">
            <Button onClick={download} disabled={busy}>
              Download {doc.filename}
            </Button>
            <Button variant="light" onClick={regenerate} loading={busy} disabled={busy}>
              Regenerate
            </Button>
            {targetKind === "document" && (
              <Button
                variant="subtle"
                component={Link}
                to={`/jobs/${doc.job_id}/tailored-cv`}
              >
                This job&apos;s CVs
              </Button>
            )}
            <Button variant="subtle" onClick={() => navigate(`/jobs/${doc.job_id}`)}>
              Back to job
            </Button>
            <Button
              variant="subtle"
              component={Link}
              to={`/cover-letter/${doc.job_id}`}
            >
              Cover letter
            </Button>
          </Group>
        </Stack>
      )}
    </Card>
  );
}
