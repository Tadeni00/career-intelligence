import { useCallback, useEffect, useState } from "react";
import {
  Card,
  Group,
  Title,
  Text,
  Button,
  Alert,
  Badge,
  Loader,
  Progress,
  SimpleGrid,
  Stack,
  Modal,
  Textarea,
  Select,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { ApplicationReadinessPanel } from "../components/ApplicationReadinessPanel";
import { StrategyPanel } from "../components/StrategyPanel";
import { useActiveProfile } from "../ProfileSelector";
import { ProvenanceBadge, ProvenanceSummary, useProfileNames } from "../ProvenanceBadge";
import { useRunMatch } from "../runMatch";
import type { Job, JobRequirement, MatchResult, Application, TailoredCV, CoverLetter } from "../types";

export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<Job | null>(null);
  const [match, setMatch] = useState<MatchResult | null>(null);
  const { profiles } = useProfileNames();
  const [profileId] = useActiveProfile();
  const { run, busyId } = useRunMatch(profileId, profiles);
  const [requirements, setRequirements] = useState<JobRequirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  // Create application modal state
  const [creatingApp, setCreatingApp] = useState(false);
  const [appLoading, setAppLoading] = useState(false);
  const [appError, setAppError] = useState<string | null>(null);
  const [availableCVs, setAvailableCVs] = useState<TailoredCV[]>([]);
  const [availableLetters, setAvailableLetters] = useState<CoverLetter[]>([]);
  const [selectedCVId, setSelectedCVId] = useState<number | null>(null);
  const [selectedLetterId, setSelectedLetterId] = useState<number | null>(null);
  const [appStatus, setAppStatus] = useState<Application["status"]>("INTERESTED");
  const [appNotes, setAppNotes] = useState("");

  useEffect(() => {
    api<Job>(`/jobs/${jobId}`)
      .then(setJob)
      .catch((e) => setError(errorMessage(e, `Job ${jobId} was not found.`)))
      .finally(() => setLoading(false));
  }, [jobId]);

  useEffect(() => {
    // A match is optional: a job with no match yet is a normal state, not a
    // page-level failure, so this must not blank out the job.
    //
    // Scoped when a CV profile is selected, so the score shown belongs to that
    // profile's evidence rather than the shared record. The job itself is not
    // profile-scoped, so it is deliberately not part of this effect.
    const query = profileId === null ? "" : `?cv_profile_id=${profileId}`;
    api<MatchResult>(`/jobs/${jobId}/match${query}`)
      .then((m) => setMatch(m))
      .catch(() => setMatch(null));
  }, [jobId, profileId]);

  const runMatch = async () => {
    const result = await run(Number(jobId));
    if (result) setMatch(result);
  };

  const loadApplicationMaterials = useCallback(async () => {
    setAppError(null);
    try {
      const [cvs, letters] = await Promise.all([
        api<TailoredCV[]>(`/tailored-cvs?job_id=${jobId}&cv_profile_id=${profileId ?? ""}`),
        api<CoverLetter[]>(`/cover-letters?job_id=${jobId}&cv_profile_id=${profileId ?? ""}`),
      ]);
      setAvailableCVs(cvs);
      setAvailableLetters(letters);
      // Pre-select the first one if available
      if (cvs.length > 0 && !selectedCVId) setSelectedCVId(cvs[0].id);
      if (letters.length > 0 && !selectedLetterId) setSelectedLetterId(letters[0].id);
    } catch (e) {
      setAppError(errorMessage(e, "Could not load application materials."));
    }
  }, [jobId, profileId, selectedCVId, selectedLetterId]);

  const openCreateApplication = () => {
    loadApplicationMaterials();
    setCreatingApp(true);
  };

  const createApplication = async () => {
    if (!match) return;
    setAppLoading(true);
    setAppError(null);
    try {
      await api<Application>("/applications", {
        method: "POST",
        body: JSON.stringify({
          job_id: Number(jobId),
          match_id: match.id,
          tailored_cv_id: selectedCVId,
          cover_letter_id: selectedLetterId,
          status: appStatus,
          notes: appNotes,
          cv_profile_id: profileId,
        }),
      });
      notifications.show({
        title: "Application created",
        message: "Your application has been recorded.",
        color: "green",
      });
      setCreatingApp(false);
      // Reload applications list - the ApplicationsPage will pick it up on next visit
    } catch (e) {
      setAppError(errorMessage(e, "Could not create application."));
    } finally {
      setAppLoading(false);
    }
  };

  useEffect(() => {
    if (job && job.requirements) {
      setRequirements(job.requirements);
    }
  }, [job]);

  if (!job && !loading) {
    return <Alert color="red" title="Job not found">The requested job could not be found.</Alert>;
  }

  if (loading) {
    return <Loader size="lg" />;
  }

  return (
    <Card padding="lg" radius="md">
      <Title order={2} mb="md">
        {job?.title} at {job?.company ?? "Unknown company"}
      </Title>

      {error && <Alert color="red">{error}</Alert>}

      <Group gap="md">
        <Group>
          <Text size="sm" c="dimmed">
            Location:{" "}
            {job?.location ?? "Not stated"} {job?.remote_status ?? ""}
          </Text>
          <Text size="sm" c="dimmed">
            Employment type:{" "}
            {job?.employment_type ?? "Not stated"}
          </Text>
          {job?.salary_min !== null && (
            <Text size="sm" c="dimmed">
              Salary:{" "}
              {job?.salary_min?.toLocaleString()} -{" "}
              {job?.salary_max ?? "not stated"}k
            </Text>
          )}
        </Group>

        <Group>
          <Text size="sm" c="dimmed">Posted:</Text>
          <Text size="sm">{job?.posted_at ?? "Not stated"}</Text>
        </Group>
      </Group>

      {job && <ApplicationReadinessPanel key={job.id} job={job} match={match} />}

      <Card withBorder padding="lg" radius="md" mb="md">
        <Title order={3} mb="md">Requirements</Title>
        {requirements.length === 0 ? (
          <Text c="dimmed">No requirements extracted yet.</Text>
        ) : (
          <SimpleGrid cols={{ base: 2, md: 3, lg: 4 }} spacing="sm">
            {requirements.map((req) => (
              <Card key={req.id} withBorder padding="xs" radius="xs">
                <Group justify="space-between" align="center">
                  <Text size="sm" fw={500}>
                    {req.name}
                  </Text>
                  <Badge
                    color={req.importance === "REQUIRED" ? "red" : "blue"}
                    size="xs"
                    variant="light"
                  >
                    {req.importance}
                  </Badge>
                </Group>
                <Text size="xs" c="dimmed">
                  {req.description ?? ""}
                </Text>
                {req.years_required !== null && (
                  <Text size="xxs">
                    {req.years_required}+ years
                  </Text>
                )}
              </Card>
            ))}
          </SimpleGrid>
        )}
      </Card>

      {match ? (
        <Card withBorder padding="lg" radius="md" mt="md">
          <Group justify="space-between" align="flex-start" mb="md">
            <Title order={3}>Match Assessment</Title>
            <Button
              variant="subtle"
              size="xs"
              loading={busyId === Number(jobId)}
              disabled={busyId !== null}
              onClick={runMatch}
            >
              Re-run match
            </Button>
          </Group>
          <Stack gap="md">
            <SimpleGrid cols={5}>
              <div style={{ textAlign: "center" }}>
                <Text size="xl" fw={700}>{match.technical_score.toFixed(0)}</Text>
                <Text size="xxs" c="dimmed">
                  Technical
                </Text>
              </div>
              <div style={{ textAlign: "center" }}>
                <Text size="xl" fw={700}>{match.experience_score.toFixed(0)}</Text>
                <Text size="xxs" c="dimmed">
                  Experience
                </Text>
              </div>
              <div style={{ textAlign: "center" }}>
                <Text size="xl" fw={700}>{match.education_score.toFixed(0)}</Text>
                <Text size="xxs" c="dimmed">
                  Education
                </Text>
              </div>
              <div style={{ textAlign: "center" }}>
                <Text size="xl" fw={700}>{match.location_score.toFixed(0)}</Text>
                <Text size="xxs" c="dimmed">
                  Location
                </Text>
              </div>
              <div style={{ textAlign: "center" }}>
                <Text size="xl" fw={700}>{match.other_score.toFixed(0)}</Text>
                <Text size="xxs" c="dimmed">
                  Other
                </Text>
              </div>
            </SimpleGrid>

            <ProvenanceSummary
              profileId={match.cv_profile_id ?? null}
              profiles={profiles}
              label="Scored against"
            />

            <Progress size="sm" value={match.overall_score}>
              <Progress.Label>{`${match.overall_score.toFixed(0)}/100`}</Progress.Label>
            </Progress>

            <Badge
              color={
                {
                  APPLY: "green",
                  APPLY_WITH_TAILORING: "blue",
                  STRETCH: "orange",
                  SKIP: "red",
                }[match.recommendation] ?? "gray"
              }
              variant="light"
              size="lg"
            >
              {match.recommendation}
            </Badge>

            <Text size="sm" c="dimmed">
              {match.explanation ?? "No explanation available."}
            </Text>

            <Group gap="sm">
              <Card withBorder padding="sm" radius="sm">
                <Title order={4} size="sm">Strong matches</Title>
                <SimpleGrid cols={3} spacing="md">
                  {match.matched_items?.map((item) => (
                    <Badge key={item.name} color="green" variant="light" size="sm">
                      {item.name}
                    </Badge>
                  ))}
                </SimpleGrid>
              </Card>

              <Card withBorder padding="sm" radius="sm">
                <Title order={4} size="sm">Gaps</Title>
                <SimpleGrid cols={3} spacing="md">
                  {match.gap_items?.map((item) => (
                    <Badge key={item.name} color="orange" variant="light" size="sm">
                      {item.name}
                    </Badge>
                  ))}
                </SimpleGrid>
              </Card>

              <Card withBorder padding="sm" radius="sm">
                <Title order={4} size="sm">Blockers</Title>
                <SimpleGrid cols={3} spacing="md">
                  {match.blocker_items?.map((item) => (
                    <Badge key={item.name} color="red" variant="light" size="sm">
                      {item.name}
                    </Badge>
                  ))}
                </SimpleGrid>
              </Card>

              <Card withBorder padding="sm" radius="sm">
                <Title order={4} size="sm">Unknowns</Title>
                <SimpleGrid cols={3} spacing="md">
                  {match.unknown_items?.map((item) => (
                    <Badge key={item.name} color="gray" variant="light" size="sm">
                      {item.name}
                    </Badge>
                  ))}
                </SimpleGrid>
              </Card>
            </Group>
          </Stack>
        </Card>
        ) : (
          <Card withBorder padding="lg" radius="md" mt="md">
            <Group justify="space-between" align="flex-start" mb="xs">
              <Title order={3}>Match Assessment</Title>
              <Button
                variant="light"
                size="sm"
                loading={busyId === Number(jobId)}
                disabled={busyId !== null}
                onClick={runMatch}
              >
                Run match
              </Button>
            </Group>
            <Text size="sm" c="dimmed" mb="sm">
              This job has not been scored against your current evidence yet. The
              strategy below appears once a match exists for the same scope.
            </Text>
            <Group gap="xs">
              <Text size="xs" c="dimmed">Will be scored against</Text>
              <ProvenanceBadge profileId={profileId} profiles={profiles} size="xs" />
            </Group>
          </Card>
        )}

      {match && jobId && (
        <div style={{ marginTop: "md" }}>
          <StrategyPanel jobId={jobId} cvProfileId={profileId} />
        </div>
      )}

      <Group gap="md" mt="md">
        <Button
          variant="contained"
          onClick={() => navigate(`/jobs/${jobId}/tailored-cv`)}
        >
          Tailor CV for this job
        </Button>
        <Button
          variant="contained"
          color="indigo"
          onClick={() => navigate(`/cover-letter/${jobId}`)}
        >
          Generate cover letter
        </Button>
        {match && (
          <Button
            variant="contained"
            color="teal"
            onClick={openCreateApplication}
          >
            Create application
          </Button>
        )}
      </Group>

      {creatingApp && (
        <Modal
          opened
          onClose={() => setCreatingApp(false)}
          title="Create application"
          size="lg"
        >
          <Stack gap="md">
            <Text size="sm" c="dimmed">
              Create an application record for this job. The provenance will be
              set to your current evidence scope.
            </Text>

            {appError && <Alert color="red">{appError}</Alert>}

            {availableCVs.length > 0 && (
              <div>
                <Text size="sm" fw={500} mb="xs">
                  Tailored CV
                </Text>
                <Select
                  value={selectedCVId ?? ""}
                  onChange={(v) => setSelectedCVId(v === "" ? null : Number(v))}
                  data={availableCVs.map((cv) => ({
                    value: cv.id,
                    label: `v${cv.version} — ${cv.validation_status} (${new Date(cv.created_at).toLocaleDateString()})`,
                  }))}
                  placeholder="None"
                />
              </div>
            )}

            {availableLetters.length > 0 && (
              <div>
                <Text size="sm" fw={500} mb="xs">
                  Cover letter
                </Text>
                <Select
                  value={selectedLetterId ?? ""}
                  onChange={(v) => setSelectedLetterId(v === "" ? null : Number(v))}
                  data={availableLetters.map((cl) => ({
                    value: cl.id,
                    label: `${cl.validation_status} (${new Date(cl.created_at).toLocaleDateString()})`,
                  }))}
                  placeholder="None"
                />
              </div>
            )}

            <div>
              <Text size="sm" fw={500} mb="xs">
                Status
              </Text>
              <Select
                value={appStatus}
                onChange={(v) => setAppStatus(v as Application["status"])}
                data={[
                  { value: "INTERESTED", label: "Interested" },
                  { value: "READY_TO_APPLY", label: "Ready to apply" },
                  { value: "APPLIED", label: "Applied" },
                  { value: "INTERVIEW", label: "Interview" },
                  { value: "OFFER", label: "Offer" },
                  { value: "REJECTED", label: "Rejected" },
                  { value: "WITHDRAWN", label: "Withdrawn" },
                ]}
              />
            </div>

            <div>
              <Text size="sm" fw={500} mb="xs">
                Notes
              </Text>
              <Textarea
                value={appNotes}
                onChange={(e) => setAppNotes(e.currentTarget.value)}
                minRows={3}
                placeholder="Optional notes about this application..."
              />
            </div>

            <Group justify="flex-end" gap="sm" mt="md">
              <Button variant="default" onClick={() => setCreatingApp(false)}>
                Cancel
              </Button>
              <Button
                variant="contained"
                loading={appLoading}
                onClick={createApplication}
              >
                Create application
              </Button>
            </Group>
          </Stack>
        </Modal>
      )}
    </Card>
  );
}