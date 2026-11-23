import { useEffect, useMemo, useRef, useState } from "react";
import {
  Card,
  Group,
  Title,
  Text,
  Select,
  Button,
  Alert,
  TextInput,
  Badge,
  Stack,
  SimpleGrid,
  Divider,
} from "@mantine/core";
import { useNavigate, useSearchParams } from "react-router-dom";
import { notifications } from "@mantine/notifications";
import { api, errorMessage } from "../api";
import {
  applyActionLabel,
  applyActionNote,
  classifyApplicationUrl,
} from "../applicationUrl";
import {
  ActiveProfileBanner,
  NoProfilesNotice,
  useActiveProfile,
  useProfiles,
} from "../ProfileSelector";
import { ProvenanceBadge } from "../ProvenanceBadge";
import { visibleOpportunities, type DiscoverySort } from "../discoveryTriage";
import type { DiscoveredJobOut, JobSearchResponse } from "../types";

const COUNTRIES = [
  { value: "ng", label: "Nigeria" },
  { value: "us", label: "United States" },
  { value: "gb", label: "United Kingdom" },
  { value: "ca", label: "Canada" },
  { value: "au", label: "Australia" },
  { value: "de", label: "Germany" },
  { value: "fr", label: "France" },
  { value: "nl", label: "Netherlands" },
  { value: "br", label: "Brazil" },
  { value: "pl", label: "Poland" },
  { value: "za", label: "South Africa" },
  { value: "ru", label: "Russia" },
  { value: "sg", label: "Singapore" },
  { value: "mx", label: "Mexico" },
  { value: "it", label: "Italy" },
  { value: "at", label: "Austria" },
  // Benin Republic, ISO-3166-1: BJ. Added as a first-class choice —
  // see the note in DiscoverPage about live results.
  { value: "bj", label: "Benin Republic" },
];

const REMOTE_OPTIONS = [
  { value: "", label: "Any" },
  { value: "true", label: "Remote only" },
  { value: "false", label: "On-site/Hybrid only" },
];

function JobCard({
  job,
  match,
  relevance,
  freshness,
  duplicate,
  query,
  busy,
  shortlisted,
  onShortlist,
  navigate,
  profileId,
  profiles,
}: {
  job: any;
  match: any;
  relevance: { label: string; reason: string } | null;
  freshness: { status: string; reason: string } | null;
  duplicate: { status: string; reason: string; related_job_ids: number[] } | null;
  query: string;
  busy: boolean;
  shortlisted: boolean;
  onShortlist: (jobId: number) => void;
  navigate: (path: string) => void;
  profileId: number | null;
  profiles: any[];
}) {
  const matchScore = match?.overall_score;
  const recommendation: string = match?.recommendation ?? "";
  const relevanceColor =
    {
      Aligned: "teal",
      Adjacent: "yellow",
      Mismatch: "red",
      Uncertain: "gray",
    }[relevance?.label ?? ""] ?? "gray";

  // The application destination is the stored Job.url and nothing else. It is
  // never rebuilt from the title or employer; if it is absent or unusable the
  // action says so instead of rendering a dead link.
  const applyUrl = classifyApplicationUrl(job?.url);

  return (
    <Card withBorder padding="sm" radius="sm">
      <Group justify="space-between" align="flex-start" mb="sm">
        <Group gap="sm" grow>
          <Text size="sm" fw={600}>
            {job.title} at {job.company ?? "Unknown"}
          </Text>
          <Text size="xs" c="dimmed">
            {job.location ?? ""} {job.remote_status ? ` · ${job.remote_status}` : ""}
          </Text>
        </Group>
        <Group gap="2">
          {job.is_discovered && (
            <Badge variant="light" size="xs" color="blue">
              Discovered
            </Badge>
          )}
          <Badge
            color={job.remote_status === "REMOTE" ? "cyan" : "gray"}
            size="xs"
            variant="light"
          >
            {job.remote_status ?? "On-site"}
          </Badge>
        </Group>
      </Group>

      <Stack gap="xs" mt="sm">
        {job.salary_min !== null || job.salary_max !== null ? (
          <Text size="sm" c="dimmed">
            Salary: {job.salary_min ? `${job.salary_min.toLocaleString()}k` : ""} - {job.salary_max ? `${job.salary_max.toLocaleString()}k` : "Not stated"}
          </Text>
        ) : null}

        {job.posted_at ? (
          <Text size="sm" c="dimmed">
            Posted: {new Date(job.posted_at).toLocaleDateString()}
          </Text>
        ) : (
          <Text size="sm" c="dimmed">
            Posting date unavailable
          </Text>
        )}

        {freshness?.status === "stale" && (
          <Group gap="xs">
            <Badge color="orange" size="sm" variant="light">
              Possibly stale
            </Badge>
            <Text size="xs" c="dimmed">
              {freshness.reason}
            </Text>
          </Group>
        )}

        <Text size="xs" c="dimmed">
          Source: {job.source ?? "Unknown"} {job.source_id ? `(${job.source_id})` : ""}
        </Text>

        {relevance && (
          <Group gap="xs">
            <Badge color={relevanceColor} size="sm" variant="light">
              Role: {relevance.label}
            </Badge>
            <Text size="xs" c="dimmed">
              {relevance.reason}
            </Text>
          </Group>
        )}

        {duplicate && duplicate.status !== "No duplicate signal" && duplicate.status !== "Unable to assess" && (
          <Group gap="xs">
            <Badge
              color={duplicate.status === "Likely duplicate" ? "orange" : "gray"}
              size="sm"
              variant="light"
            >
              {duplicate.status === "Likely duplicate" ? "Likely duplicate" : "Possible duplicate"}
            </Badge>
            <Text size="xs" c="dimmed">
              {duplicate.reason}
            </Text>
          </Group>
        )}

        {match && (
          <Group gap="xs">
            <Badge
              color={
                {
                  APPLY: "green",
                  APPLY_WITH_TAILORING: "blue",
                  STRETCH: "orange",
                  SKIP: "red",
                }[recommendation ?? ""] ?? "gray"
              }
              size="sm"
              variant="light"
            >
              {recommendation} {matchScore != null ? `${matchScore.toFixed(0)}/100` : ""}
            </Badge>
            <ProvenanceBadge profileId={match?.cv_profile_id ?? null} profiles={profiles} size="xs" />
          </Group>
        )}

        <Divider my="xs" />

        {/*
          Exactly one strong action per card: Apply, the external destination.
          Details is subtle and Shortlist is an outline, so the hierarchy is
          legible and the two in-app actions never compete with the external
          link. The group wraps, so nothing overflows a narrow card.
        */}
        <Group gap="xs" wrap="wrap" mt="sm">
          {applyUrl.kind === "ok" ? (
            <Button
              component="a"
              href={applyUrl.href}
              target="_blank"
              rel="noopener noreferrer"
              size="sm"
              maw="100%"
            >
              {applyActionLabel(job.company)}
              <span aria-hidden="true">&nbsp;↗</span>
            </Button>
          ) : (
            <Button size="sm" disabled maw="100%">
              Apply unavailable
            </Button>
          )}

          <Button
            variant="subtle"
            size="sm"
            onClick={() =>
              navigate(
                `/discovered/${job.id}?query=${encodeURIComponent(query)}` +
                  (profileId !== null ? `&cv_profile_id=${profileId}` : "")
              )
            }
          >
            View details
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={() => onShortlist(job.id)}
            disabled={busy || shortlisted}
            loading={busy}
          >
            {shortlisted ? "Shortlisted" : "Shortlist"}
          </Button>
        </Group>

        <Text size="xs" c="dimmed" mt={6}>
          {applyUrl.kind === "ok"
            ? applyActionNote(job.company, job.source)
            : `Application link unavailable — ${applyUrl.reason} You can still view the details and shortlist this job.`}
        </Text>
      </Stack>
    </Card>
  );
}

export function DiscoverPage() {
  const [query, setQuery] = useState("");
  const [country, setCountry] = useState("ng");
  const [location, setLocation] = useState("");
  const [remoteOnly, setRemoteOnly] = useState(false);
  const [maxResults, setMaxResults] = useState(20);
  const [results, setResults] = useState<JobSearchResponse | null>(null);
  const [sort, setSort] = useState<DiscoverySort>("review");
  const [promisingOnly, setPromisingOnly] = useState(false);
  const [shortlistedIds, setShortlistedIds] = useState<Set<number>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  // Per-card in-flight guard. The ref is checked synchronously so rapid
  // clicks in the same tick cannot both pass; the state drives the
  // button's disabled/loading rendering. Matches DiscoveredJobDetailPage.
  const shortlistingIdsRef = useRef<Set<number>>(new Set());
  const [shortlistingId, setShortlistingId] = useState<number | null>(null);

  // Which CV profile this search is matched against. Chosen explicitly by the
  // user; the shared profile is used when none is selected.
  const { profiles } = useProfiles();
  const [profileId, setProfileId] = useActiveProfile();

  useEffect(() => {
    // Load saved search params from URL
    const params = Object.fromEntries(searchParams.entries());
    if (params.query) setQuery(params.query);
    if (params.country) setCountry(params.country);
    if (params.location) setLocation(params.location);
    if (params.remote_only) setRemoteOnly(params.remote_only === "true");
    if (params.max_results) {
      const count = Number(params.max_results);
      if (Number.isInteger(count) && count >= 1 && count <= 50) setMaxResults(count);
    }
  }, []);

  const visible = useMemo(
    () => visibleOpportunities(results?.jobs ?? [], sort, promisingOnly),
    [results, sort, promisingOnly],
  );

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) {
      setError("Please enter a search query");
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);
    setShortlistedIds(new Set());

    try {
      const response = await api<JobSearchResponse>("/jobs/discover", {
        method: "POST",
        body: JSON.stringify({
          query: query.trim(),
          country,
          location: location || undefined,
          remote_only: remoteOnly,
          max_results: maxResults,
          ...(profileId !== null ? { cv_profile_id: profileId } : {}),
        }),
      });

      setResults({
        jobs: Array.isArray(response.jobs) ? response.jobs : [],
        total: typeof response.total === "number" ? response.total : 0,
        query: response.query ?? query.trim(),
        country: response.country ?? country.toUpperCase(),
      });
      const params = new URLSearchParams({
        query: query.trim(),
        country,
        remote_only: String(remoteOnly),
        max_results: String(maxResults),
      });
      if (location.trim()) params.set("location", location.trim());
      if (profileId !== null) params.set("cv_profile_id", String(profileId));
      setSearchParams(params, { replace: true });
    } catch (e) {
      setError(errorMessage(e, "Search failed"));
    } finally {
      setLoading(false);
    }
  };

  const handleShortlist = async (jobId: number) => {
    if (shortlistingIdsRef.current.has(jobId)) return;
    shortlistingIdsRef.current.add(jobId);
    setShortlistingId(jobId);
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
      setShortlistedIds((previous) => new Set(previous).add(jobId));
      notifications.show({
        title: "Shortlisted",
        message:
          response.message +
          (profileId !== null
            ? ` It is tracked under ${profiles.find((p) => p.id === profileId)?.label ?? "your selected CV profile"}.`
            : ""),
        color: "green",
      });
    } catch (e) {
      notifications.show({
        title: "Failed to shortlist",
        message: errorMessage(e, "Could not shortlist job"),
        color: "red",
      });
    } finally {
      shortlistingIdsRef.current.delete(jobId);
      setShortlistingId((current) => (current === jobId ? null : current));
    }
  };

  return (
    <Card padding="lg" radius="md">
      <Title order={2} mb="xs">Find suitable jobs</Title>
      <Text size="sm" c="dimmed" mb="md">
        Search vacancies, review role fit and evidence, then open the original
        employer application page. Shortlist roles to prepare materials and track applications.
      </Text>

      {profiles.length === 0 ? <NoProfilesNotice /> : null}
      <ActiveProfileBanner
        profiles={profiles}
        profileId={profileId}
        onChange={setProfileId}
      />

      <Card withBorder padding="md" radius="md" mb="md">
        <Title order={4} mb="md">Search</Title>
        <form onSubmit={handleSearch}>
          <Stack gap="md">
            <TextInput
              label="Search keywords"
              placeholder="e.g., data scientist, software engineer"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
            <Group gap="md" wrap="wrap">
              <Select
                label="Country"
                value={country}
                onChange={(v) => setCountry(v ?? "ng")}
                data={COUNTRIES}
                style={{ minWidth: 200 }}
              />
              <TextInput
                label="Location (city/region)"
                placeholder="e.g., Lagos, London, Remote"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                style={{ minWidth: 200 }}
              />
              <Select
                label="Remote"
                value={remoteOnly ? "true" : "false"}
                onChange={(v) => setRemoteOnly(v === "true")}
                data={REMOTE_OPTIONS}
                style={{ minWidth: 160 }}
              />
              <TextInput
                type="number"
                label="Max results"
                value={String(maxResults)}
                onChange={(e) => setMaxResults(parseInt(e.target.value) || 20)}
                min={1}
                max={50}
                style={{ minWidth: 120 }}
              />
            </Group>
            <Group>
              <Button type="submit" loading={loading} disabled={loading}>
                {loading ? "Searching..." : "Search"}
              </Button>
            </Group>
          </Stack>
        </form>
      </Card>

      {error && <Alert color="red" mt="md">{error}</Alert>}

      {results && (
        <Stack gap="md" mt="md">
          <Group justify="space-between">
            <Title order={3}>
              {results.total} job{results.total !== 1 ? "s" : ""} returned for &quot;{results.query}&quot; in {results.country.toUpperCase()}
            </Title>
          </Group>
          <Group gap="md" wrap="wrap">
            <Select
              label="Order results"
              aria-label="Order results"
              value={sort}
              onChange={(value) => setSort((value ?? "review") as DiscoverySort)}
              data={[
                { value: "review", label: "Review first (advisory signals)" },
                { value: "newest", label: "Newest postings first" },
                { value: "score", label: "Highest match score first" },
              ]}
              style={{ minWidth: 240 }}
            />
            <Select
              label="Show"
              value={promisingOnly ? "promising" : "all"}
              onChange={(value) => setPromisingOnly(value === "promising")}
              data={[
                { value: "all", label: "All returned vacancies" },
                { value: "promising", label: "Promising matches only" },
              ]}
              style={{ minWidth: 225 }}
            />
          </Group>
          <Text size="sm" c="dimmed">
            Showing {visible.length} of {results.jobs.length} returned vacancies.
            Review-first ordering uses role relevance, existing match recommendation,
            staleness and duplicate warnings; it is not a new eligibility score.
            Promising matches require aligned/adjacent roles, APPLY or
            APPLY_WITH_TAILORING, and no stale or likely-duplicate flag.
            Missing match data is never treated as a confirmed fit.
          </Text>

          {results.jobs.length === 0 ? (
            <Text c="dimmed" ta="center" pt="lg">
              No jobs found. Try adjusting your search criteria.
            </Text>
          ) : visible.length === 0 ? (
            <Alert color="blue" title="No results match this view">
              {promisingOnly
                ? "No returned vacancy meets all promising-match conditions. Switch Show to All returned vacancies to review uncertain, unscored or stretch opportunities."
                : "No vacancies are available for the current search."}
            </Alert>
          ) : (
            <SimpleGrid cols={{ base: 1, md: 2, lg: 3 }} spacing="md">
              {visible.map((item: DiscoveredJobOut) => {
                return (
                  <JobCard
                    key={item.job.id}
                    job={item.job}
                    match={item.match}
                    relevance={item.search_relevance}
                    freshness={item.freshness}
                    duplicate={item.duplicate_review}
                    query={results.query}
                    busy={shortlistingId === item.job.id}
                    shortlisted={item.shortlisted || shortlistedIds.has(item.job.id)}
                    onShortlist={handleShortlist}
                    profileId={profileId}
                    profiles={profiles}
                    navigate={navigate}
                  />
                );
              })}
            </SimpleGrid>
          )}
        </Stack>
      )}

      {results === null && !loading && !error && (
        <Text c="dimmed" ta="center" pt="xl">
          Enter a role or keyword to find vacancies. Search criteria will be saved in this page URL after a successful search; re-run Search to refresh external results.
        </Text>
      )}
    </Card>
  );
}