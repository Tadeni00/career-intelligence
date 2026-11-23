import { useEffect, useState } from "react";
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
} from "@mantine/core";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { notifications } from "@mantine/notifications";
import { api, errorMessage } from "../api";
import { salaryLabel, workArrangementLabel } from "../jobMetadataLabels";
import { ApplicationReadinessPanel } from "../components/ApplicationReadinessPanel";
import {
  applyActionLabel,
  applyActionNote,
  classifyApplicationUrl,
} from "../applicationUrl";
import type { Job, JobRequirement, MatchResult, DiscoveredJobOut, SearchRelevance, Freshness, DuplicateReview } from "../types";
import { useProfiles } from "../ProfileSelector";
import { ProvenanceSummary } from "../ProvenanceBadge";

export function DiscoveredJobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [searchParams] = useSearchParams();
  const [job, setJob] = useState<Job | null>(null);
  const [match, setMatch] = useState<MatchResult | null>(null);
  const [relevance, setRelevance] = useState<SearchRelevance | null>(null);
  const [freshness, setFreshness] = useState<Freshness | null>(null);
  const [duplicate, setDuplicate] = useState<DuplicateReview | null>(null);
  const [requirements, setRequirements] = useState<JobRequirement[]>([]);
  const [loading, setLoading] = useState(true);
  const [shortlistBusy, setShortlistBusy] = useState(false);
  const [shortlisted, setShortlisted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  // The profile this view is scoped to, taken from the URL so a deep link or a
  // refresh keeps showing the same match rather than silently reverting.
  const { profiles } = useProfiles();
  const scopedProfileId = searchParams.get("cv_profile_id");
  const profileId = scopedProfileId ? Number(scopedProfileId) : null;

  useEffect(() => {
    const params = new URLSearchParams();
    const q = searchParams.get("query");
    if (q) params.set("query", q);
    const scoped = searchParams.get("cv_profile_id");
    if (scoped) params.set("cv_profile_id", scoped);
    const suffix = params.toString() ? `?${params.toString()}` : "";
    api<DiscoveredJobOut>(`/jobs/discovered/${jobId}${suffix}`)
      .then((data) => {
        setJob(data.job);
        setMatch(data.match);
        setShortlisted(data.shortlisted);
        setRelevance(data.search_relevance);
        setFreshness(data.freshness);
        setDuplicate(data.duplicate_review);
      })
      .catch((e) => setError(errorMessage(e, `Job ${jobId} was not found.`)))
      .finally(() => setLoading(false));
  }, [jobId, searchParams]);

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

  const handleShortlist = async () => {
    if (shortlistBusy || shortlisted) return;
    setShortlistBusy(true);
    try {
      const response = await api<{
        application_id: number;
        status: string;
        message: string;
        cv_profile_id: number | null;
      }>(
        `/jobs/discovered/${jobId}/shortlist`,
        {
          method: "POST",
          body: JSON.stringify(profileId !== null ? { cv_profile_id: profileId } : {}),
        }
      );
      setShortlisted(true);
      notifications.show({
        title: "Shortlisted",
        message: `${response.message} You can now tailor your CV or generate a cover letter below.`,
        color: "green",
      });
    } catch (e) {
      notifications.show({
        title: "Failed to shortlist",
        message: errorMessage(e, "Could not shortlist job"),
        color: "red",
      });
    } finally {
      setShortlistBusy(false);
    }
  };

  if (!job) return null;

  // Same destination, same wording and the same guard as the discovery card.
  // Job.url is the only source; nothing is reconstructed from title or employer.
  const applyUrl = classifyApplicationUrl(job.url);

  return (
    <Card padding="lg" radius="md">
      <Title order={2} mb="md">
        {job.title} at {job.company ?? "Unknown company"}
      </Title>

      {error && <Alert color="red">{error}</Alert>}

      {relevance && (
        <Alert
          color={
            { Aligned: "teal", Adjacent: "yellow", Mismatch: "red", Uncertain: "gray" }[
              relevance.label
            ] ?? "gray"
          }
          mb="md"
        >
          Search relevance: {relevance.label} — {relevance.reason} Candidate fit below is
          scored independently of this signal.
        </Alert>
      )}

      {freshness?.status === "stale" && (
        <Alert color="orange" mb="md">
          Possibly stale — {freshness.reason} The Apply link below still
          works, but verify the posting at the source before applying. Tailoring,
          cover letters and application tracking remain available.
        </Alert>
      )}

      {duplicate && duplicate.status !== "No duplicate signal" && duplicate.status !== "Unable to assess" && (
        <Alert
          color={duplicate.status === "Likely duplicate" ? "orange" : "gray"}
          mb="md"
        >
          {duplicate.status} — {duplicate.reason} Both records are kept; review
          them before shortlisting twice.
        </Alert>
      )}

      <Group gap="md">
        <Group>
          <Text size="sm" c="dimmed">
            Location:{" "}
            {job.location ?? "Not stated"} · {workArrangementLabel(job.remote_status)}
          </Text>
          <Text size="sm" c="dimmed">
            Employment type:{" "}
            {job.employment_type ?? "Not stated"}
          </Text>
          <Text size="sm" c="dimmed">{salaryLabel(job)}</Text>
        </Group>

        <Group>
          <Text size="sm" c="dimmed">Posted:</Text>
          <Text size="sm">{job.posted_at ?? "Posting date unavailable"}</Text>
        </Group>
        <Group>
          <Text size="sm" c="dimmed">
            Source: {job.source ?? "Unknown"}
          </Text>
        </Group>
      </Group>

      <ApplicationReadinessPanel key={job.id} job={job} match={match} freshness={freshness} />

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

      {match && (
        <Card withBorder padding="lg" radius="md">
          <Title order={3} mb="md">Match Assessment</Title>
          <ProvenanceSummary
            profileId={match.cv_profile_id ?? null}
            profiles={profiles}
            label="Scored against"
          />
          <Stack gap="md" mt="sm">
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
        )}

      {/*
        Apply is the only strong action and the only link that leaves the app.
        Shortlist, Tailor CV, Generate cover letter and Track in applications
        stay in-app and stay visually distinct from it.
      */}
      <Group gap="sm" mt="md" wrap="wrap">
        {applyUrl.kind === "ok" ? (
          <Button
            component="a"
            href={applyUrl.href}
            target="_blank"
            rel="noopener noreferrer"
          >
            {applyActionLabel(job.company)}
            <span aria-hidden="true">&nbsp;↗</span>
          </Button>
        ) : (
          <Button disabled>Apply unavailable</Button>
        )}

        <Button
          variant="default"
          onClick={() => navigate(`/jobs/${job.id}/tailored-cv`)}
        >
          Tailor CV for this job
        </Button>
        <Button
          variant="default"
          color="indigo"
          onClick={() => navigate(`/cover-letter/${job.id}`)}
        >
          Generate cover letter
        </Button>
        <Button
          variant="outline"
          onClick={handleShortlist}
          disabled={shortlistBusy || shortlisted}
          loading={shortlistBusy}
        >
          {shortlisted ? "Shortlisted" : "Shortlist this job"}
        </Button>
        {shortlisted && (
          <Button
            variant="subtle"
            onClick={() => navigate("/applications")}
          >
            Track in applications
          </Button>
        )}
      </Group>

      <Text size="xs" c="dimmed" mt={6}>
        {applyUrl.kind === "ok"
          ? applyActionNote(job.company, job.source)
          : `Application link unavailable — ${applyUrl.reason} Shortlisting, tailoring and cover letters remain available.`}
      </Text>
    </Card>
  );
}

export default DiscoveredJobDetailPage;