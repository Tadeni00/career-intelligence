import { useCallback, useEffect, useState } from "react";
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
  Modal,
  Textarea,
  Stack,
} from "@mantine/core";
import { notifications } from "@mantine/notifications";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { applicationMaterialsTarget } from "../tailoredCvRouting";
import { applyActionLabel, classifyApplicationUrl } from "../applicationUrl";
import { ProvenanceBadge, useProfileNames } from "../ProvenanceBadge";
import type { Application, Job, MatchResult, TailoredCV, CoverLetter } from "../types";

export function ApplicationsPage() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = searchParams.get("status") ?? "";
  const visibleApplications = applications.filter(
    (app) => !statusFilter || app.status === statusFilter
  );
  const [confirmApplied, setConfirmApplied] = useState<Application | null>(null);
  const [markingApplied, setMarkingApplied] = useState(false);
  const { profiles } = useProfileNames();

  // Create application modal state
  const [creatingApp, setCreatingApp] = useState(false);
  const [appLoading, setAppLoading] = useState(false);
  const [appError, setAppError] = useState<string | null>(null);
  const [availableJobs, setAvailableJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [availableMatches, setAvailableMatches] = useState<MatchResult[]>([]);
  const [selectedMatchId, setSelectedMatchId] = useState<number | null>(null);
  const [availableCVs, setAvailableCVs] = useState<TailoredCV[]>([]);
  const [selectedCVId, setSelectedCVId] = useState<number | null>(null);
  const [availableLetters, setAvailableLetters] = useState<CoverLetter[]>([]);
  const [selectedLetterId, setSelectedLetterId] = useState<number | null>(null);
  const [appStatus, setAppStatus] = useState<Application["status"]>("INTERESTED");
  const [appNotes, setAppNotes] = useState("");

  useEffect(() => {
    setLoading(true);
    api<Application[]>("/applications")
      .then(setApplications)
      .catch((e) => setError(errorMessage(e, "Could not load applications.")))
      .finally(() => setLoading(false));
  }, []);

  const loadJobsForApplication = useCallback(async () => {
    setAppError(null);
    try {
      const jobs = await api<Job[]>("/jobs");
      setAvailableJobs(jobs);
      if (jobs.length > 0 && !selectedJobId) setSelectedJobId(jobs[0].id);
    } catch (e) {
      setAppError(errorMessage(e, "Could not load jobs."));
    }
  }, [selectedJobId]);

  const loadMatchesForJob = useCallback(async () => {
    if (!selectedJobId) {
      setAvailableMatches([]);
      setSelectedMatchId(null);
      setAvailableCVs([]);
      setAvailableLetters([]);
      return;
    }
    try {
      // Get the active profile for scoping
      const { getActiveProfileId } = await import("../activeProfile");
      const profileId = getActiveProfileId();
      const query = profileId === null ? "" : `?cv_profile_id=${profileId}`;
      const match = await api<MatchResult | null>(`/jobs/${selectedJobId}/match${query}`)
        .catch(() => null);
      if (match) {
        setAvailableMatches([match]);
        setSelectedMatchId(match.id);
      } else {
        setAvailableMatches([]);
        setSelectedMatchId(null);
      }
      // Load tailored CVs and cover letters for this job
      const [cvs, letters] = await Promise.all([
        api<TailoredCV[]>(`/tailored-cvs?job_id=${selectedJobId}${query ? "&" + query.slice(1) : ""}`),
        api<CoverLetter[]>(`/cover-letters?job_id=${selectedJobId}${query ? "&" + query.slice(1) : ""}`),
      ]);
      setAvailableCVs(cvs);
      setAvailableLetters(letters);
      if (cvs.length > 0 && !selectedCVId) setSelectedCVId(cvs[0].id);
      if (letters.length > 0 && !selectedLetterId) setSelectedLetterId(letters[0].id);
    } catch (e) {
      setAppError(errorMessage(e, "Could not load match and materials."));
    }
  }, [selectedJobId, selectedCVId, selectedLetterId]);

  const recordExternalSubmission = async () => {
    if (!confirmApplied || markingApplied) return;
    setMarkingApplied(true);
    try {
      await api<Application>(`/applications/${confirmApplied.id}`, {
        method: "PUT",
        body: JSON.stringify({ status: "APPLIED" }),
      });
      const refreshed = await api<Application[]>("/applications");
      setApplications(refreshed);
      notifications.show({
        title: "Application recorded",
        message: "Marked as applied because you confirmed submitting on the employer's site.",
        color: "green",
      });
      setConfirmApplied(null);
    } catch (e) {
      notifications.show({
        title: "Could not update application",
        message: errorMessage(e, "Try again from the application list."),
        color: "red",
      });
    } finally {
      setMarkingApplied(false);
    }
  };

  const openCreateApplication = () => {
    loadJobsForApplication();
    setCreatingApp(true);
  };

  useEffect(() => {
    loadMatchesForJob();
  }, [selectedJobId]);

  const createApplication = async () => {
    if (!selectedJobId || !selectedMatchId) {
      setAppError("Please select a job and match first.");
      return;
    }
    setAppLoading(true);
    setAppError(null);
    try {
      await api<Application>("/applications", {
        method: "POST",
        body: JSON.stringify({
          job_id: selectedJobId,
          match_id: selectedMatchId,
          tailored_cv_id: selectedCVId,
          cover_letter_id: selectedLetterId,
          status: appStatus,
          notes: appNotes,
        }),
      });
      notifications.show({
        title: "Application created",
        message: "Your application has been recorded.",
        color: "green",
      });
      setCreatingApp(false);
      // Reload applications list
      const refreshed = await api<Application[]>("/applications");
      setApplications(refreshed);
    } catch (e) {
      setAppError(errorMessage(e, "Could not create application."));
    } finally {
      setAppLoading(false);
    }
  };

  if (error) return <Alert color="red">{error}</Alert>;
  if (loading) return <Loader size="lg" />;

  return (
    <Card padding="lg" radius="md">
      <Title order={2} mb="xs">My applications</Title>
      <Text size="sm" c="dimmed" mb="md">
        Shortlist jobs, open their original application pages, and record when
        you actually submit. Opening an employer link never marks a job as applied.
      </Text>

      <Group gap="md" mb="md">
        <Select
          label="Filter by status"
          value={statusFilter}
          data={[
            { value: "", label: "All" },
            { value: "INTERESTED", label: "Interested" },
            { value: "READY_TO_APPLY", label: "Ready to apply" },
            { value: "APPLIED", label: "Applied" },
            { value: "INTERVIEW", label: "Interview" },
            { value: "OFFER", label: "Offer" },
            { value: "REJECTED", label: "Rejected" },
            { value: "WITHDRAWN", label: "Withdrawn" },
          ]}
          onChange={(value) => {
            const next = value ?? "";
            setSearchParams(next ? { status: next } : {}, { replace: true });
          }}
        />
      </Group>

      <Text size="sm" c="dimmed" mb="md">
        Showing {visibleApplications.length} of {applications.length} tracked applications.
      </Text>
      {applications.length === 0 ? (
        <Stack gap="sm" mb="lg">
          <Text c="dimmed">Nothing tracked yet. Find a vacancy and shortlist it to start.</Text>
          <Button onClick={() => navigate("/discover")}>Discover jobs</Button>
        </Stack>
      ) : visibleApplications.length === 0 ? (
        <Alert color="blue" mb="md">
          No applications have this status. Select All to see every tracked vacancy.
        </Alert>
      ) : (
        <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }}>
          {visibleApplications.map((app) => {
            const job = app.job ?? { title: `Job ${app.job_id}`, company: "" };
            const applyUrl = classifyApplicationUrl(app.job?.url);
            const canMarkApplied = app.status === "INTERESTED" || app.status === "READY_TO_APPLY";
            return (
              <Card key={app.id} withBorder padding="sm" radius="sm">
                <Group justify="space-between" align="center">
                  <Group gap="sm">
                    <Text size="sm" fw={600}>
                      {job.title}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {job.company} {app.job?.location ?? ""}
                    </Text>
                  </Group>
                  <Group gap="2">
                    <Badge color="green" variant="light" size="sm">
                      {app.status}
                    </Badge>
                    {app.applied_at && (
                      <Text size="xxs" c="dimmed">
                        Applied {new Date(app.applied_at).toLocaleDateString()}
                      </Text>
                    )}
                  </Group>
                </Group>
                <Group gap="xs" mt={6}>
                  <ProvenanceBadge
                    profileId={app.cv_profile_id}
                    profiles={profiles}
                    prefix="CV"
                  />
                </Group>
                <Group gap="xs" mt="sm" wrap="wrap">
                  <Button
                    variant="subtle"
                    size="xs"
                    onClick={() => navigate(
                      app.job?.is_discovered
                        ? `/discovered/${app.job_id}`
                        : `/jobs/${app.job_id}`
                    )}
                  >
                    View job
                  </Button>
                  <Button
                    variant="subtle"
                    size="xs"
                    onClick={() => {
                      // The application id is never a tailored CV id.
                      const target = applicationMaterialsTarget(app);
                      navigate(
                        target.kind === "document"
                          ? `/tailored-cvs/${target.docId}`
                          : `/jobs/${target.jobId}/tailored-cv`
                      );
                    }}
                  >
                    Prepare materials
                  </Button>
                  {applyUrl.kind === "ok" ? (
                    <Button
                      component="a"
                      href={applyUrl.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      variant="outline"
                      size="xs"
                    >
                      {applyActionLabel(app.job?.company)}
                    </Button>
                  ) : (
                    <Text c="dimmed" size="xs">Employer application link unavailable</Text>
                  )}
                  {canMarkApplied && (
                    <Button size="xs" color="teal" onClick={() => setConfirmApplied(app)}>
                      I submitted this application
                    </Button>
                  )}
                </Group>
              </Card>
            );
          })}
        </SimpleGrid>
      )}

      <Group gap="md" mb="md">
        <Button variant="contained" onClick={() => navigate("/discover")}>
          Discover jobs
        </Button>
        <Button variant="contained" color="teal" onClick={openCreateApplication}>
          Create application
        </Button>
      </Group>

      <Modal
        opened={confirmApplied !== null}
        onClose={() => !markingApplied && setConfirmApplied(null)}
        title="Confirm external application submitted"
        centered
      >
        <Stack gap="md">
          <Text size="sm">
            Did you complete the application on the employer's site for{" "}
            <strong>{confirmApplied?.job?.title ?? "this job"}</strong>?
            Opening a link or preparing a CV is not the same as submitting.
          </Text>
          <Text size="sm" c="dimmed">
            If confirmed, this job will move to Applied, and the application
            date will be recorded. You can continue tracking interviews and outcomes later.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" disabled={markingApplied} onClick={() => setConfirmApplied(null)}>
              Not yet
            </Button>
            <Button color="teal" loading={markingApplied} onClick={recordExternalSubmission}>
              Yes, I submitted it
            </Button>
          </Group>
        </Stack>
      </Modal>

      {creatingApp && (
        <Modal
          opened
          onClose={() => setCreatingApp(false)}
          title="Create application"
          size="lg"
        >
          <Stack gap="md">
            <Text size="sm" c="dimmed">
              Create a new application record. The match is auto-selected based
              on your current evidence scope (shared profile or selected CV
              profile).
            </Text>

            {appError && <Alert color="red">{appError}</Alert>}

            <div>
              <Text size="sm" fw={500} mb="xs">
                Job
              </Text>
              <Select
                value={selectedJobId ?? ""}
                onChange={(v) => {
                  setSelectedJobId(v === "" ? null : Number(v));
                  setSelectedMatchId(null);
                  setSelectedCVId(null);
                  setSelectedLetterId(null);
                }}
                data={availableJobs.map((j) => ({
                  value: j.id,
                  label: `${j.title} at ${j.company ?? "Unknown"} (${j.location ?? "No location"})`,
                }))}
                placeholder="Select a job"
              />
            </div>

            <div>
              <Text size="sm" fw={500} mb="xs">
                Match
              </Text>
              {availableMatches.length > 0 ? (
                <Select
                  value={selectedMatchId ?? ""}
                  onChange={(v) => setSelectedMatchId(v === "" ? null : Number(v))}
                  data={availableMatches.map((m) => ({
                    value: m.id,
                    label: `${m.recommendation} · ${m.overall_score.toFixed(0)}/100`,
                  }))}
                  placeholder="No match for this job in current scope"
                />
              ) : (
                <Text size="sm" c="dimmed">
                  No match found for this job in your current evidence scope.
                  Run the match on the Jobs page first.
                </Text>
              )}
            </div>

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
                    label: `v${cv.version} — ${cv.validation_status}`,
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
                    label: `${cl.validation_status}`,
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