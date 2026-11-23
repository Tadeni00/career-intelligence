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
import { salaryLabel, workArrangementLabel } from "../jobMetadataLabels";
import { BENIN_LOCAL_SOURCES, showBeninLocalSources } from "../beninLocalSources";
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
import { filterDiscoveredResults, sourceCounts, sourcesFromResults, type DiscoveryArrangement } from "../discoverySourceFilters";
import type { DiscoveredJobOut, JobSearchResponse, ProfileSummary } from "../types";
import { profileRemoteOnly } from "../profileEditing";
import {
  MAX_SAVED_SEARCHES, addSavedSearch, readSavedSearches,
  writeSavedSearches, validCriteria,
  type SavedSearch, type SearchCriteria,
} from "../savedSearches";

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
  { value: "false", label: "Any work arrangement" },
  { value: "true", label: "Remote only" },
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
            {workArrangementLabel(job.remote_status)}
          </Badge>
        </Group>
      </Group>

      <Stack gap="xs" mt="sm">
        <Text size="sm" c="dimmed">{salaryLabel(job)}</Text>

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
        {job.source === "careerjet" && (
          <Text size="xs" c="dimmed">
            Optioncarriere / Careerjet publisher result. Confirm work location,
            arrangement, deadline and eligibility on the source page.
          </Text>
        )}
        {job.source === "devglobaljobs" && (
          <Text size="xs">
            <a href="https://devglobaljobs.com/" target="_blank" rel="noopener noreferrer">
              Powered by Dev Global Jobs
            </a>
            {" "}— local workplace and vacancy status must still be verified.
          </Text>
        )}

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
  const [savedSearches, setSavedSearches] = useState<SavedSearch[]>(readSavedSearches);
  const [selectedPreset, setSelectedPreset] = useState<string | null>(null);
  const [presetMessage, setPresetMessage] = useState<string | null>(null);
  const [usingProfilePrefs, setUsingProfilePrefs] = useState(false);
  const [results, setResults] = useState<JobSearchResponse | null>(null);
  const [sort, setSort] = useState<DiscoverySort>("review");
  const [promisingOnly, setPromisingOnly] = useState(false);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [arrangementFilter, setArrangementFilter] = useState<DiscoveryArrangement>("all");
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

  const sourceSummary = useMemo(() => sourceCounts(results?.jobs ?? []), [results]);
  const availableSources = useMemo(() => sourcesFromResults(results?.jobs ?? []), [results]);
  const visible = useMemo(() => visibleOpportunities(
    filterDiscoveredResults(results?.jobs ?? [], sourceFilter, arrangementFilter),
    sort, promisingOnly,
  ), [results, sort, promisingOnly, sourceFilter, arrangementFilter]);

  const currentCriteria = (): SearchCriteria | null =>
    validCriteria({ query, country, location, remoteOnly, maxResults });

  const fillCriteria = (criteria: SearchCriteria) => {
    setQuery(criteria.query);
    setCountry(criteria.country);
    setLocation(criteria.location);
    setRemoteOnly(criteria.remoteOnly);
    setMaxResults(criteria.maxResults);
    setResults(null);
    setSourceFilter("all");
    setArrangementFilter("all");
    setError(null);
  };

  const saveCurrentSearch = () => {
    const criteria = currentCriteria();
    if (!criteria) {
      setPresetMessage("Enter valid keywords, country and result limit before saving.");
      return;
    }
    const next = addSavedSearch(
      savedSearches, criteria, `search-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    );
    if (next.length === savedSearches.length) {
      setPresetMessage("Those search criteria are already saved.");
      return;
    }
    if (!writeSavedSearches(next)) {
      setPresetMessage("Your browser blocked saving. You can still run this search.");
      return;
    }
    setSavedSearches(next);
    setSelectedPreset(next[0].id);
    setPresetMessage("Search saved in this browser. Saving did not contact the job provider.");
  };

  const loadSavedSearch = (id: string | null) => {
    setSelectedPreset(id);
    const saved = savedSearches.find((item) => item.id === id);
    if (!saved) return;
    fillCriteria(saved);
    setPresetMessage("Search fields loaded. Press Search to request fresh vacancies.");
  };

  const removeSavedSearch = () => {
    const next = savedSearches.filter((item) => item.id !== selectedPreset);
    if (!selectedPreset || !writeSavedSearches(next)) {
      setPresetMessage("Unable to remove this saved search.");
      return;
    }
    setSavedSearches(next);
    setSelectedPreset(null);
    setPresetMessage("Saved search removed. This does not delete any tracked jobs.");
  };

  const fillProfilePreferences = async () => {
    setUsingProfilePrefs(true);
    setPresetMessage(null);
    try {
      // A selected, confirmed CV profile has its own role/location preferences.
      // Never silently substitute the shared candidate's preferences for it.
      const source = profileId !== null
        ? profiles.find((p) => p.id === profileId)?.confirmed
        : await api<ProfileSummary>("/candidate");
      if (!source) {
        setPresetMessage("The selected CV profile has no confirmed preferences.");
        return;
      }
      const role = source.preferred_roles?.find((value) => value.trim()) ??
        (source.professional_title?.trim() || "");
      const place = source.preferred_locations?.find((value) => value.trim()) ?? "";
      if (!role && !place) {
        setPresetMessage("No preferred role or location found. Add them on the Profile page or choose another CV.");
        return;
      }
      if (role) setQuery(role);
      if (place) setLocation(place);
      setRemoteOnly(profileRemoteOnly(source.remote_preference));
      setResults(null);
      setError(null);
      setPresetMessage("Profile preferences filled role, location and supported remote-only filter. Check the country, location and work restrictions, then press Search. Hybrid/on-site preferences cannot be enforced by this provider. No provider request was made.");
    } catch (error) {
      setPresetMessage(errorMessage(error, "Could not load profile preferences."));
    } finally {
      setUsingProfilePrefs(false);
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) {
      setError("Please enter a search query");
      return;
    }
    if (!/^[a-z]{2}$/.test(country)) {
      setError("Enter a two-letter country code, such as bj for Benin.");
      return;
    }

    setLoading(true);
    setError(null);
    setResults(null);
    setSourceFilter("all");
    setArrangementFilter("all");
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
        <Title order={4} mb="xs">Start with your preferences</Title>
        <Text size="sm" c="dimmed" mb="sm">
          Fill this form using your selected CV profile or shared career profile,
          or reuse a search saved in this browser. Neither action requests live jobs.
        </Text>
        <Group align="flex-end" gap="sm" wrap="wrap">
          <Button variant="light" onClick={fillProfilePreferences} loading={usingProfilePrefs}>
            Use profile preferences
          </Button>
          <Select
            label="Saved searches"
            placeholder="Choose saved criteria"
            clearable
            searchable
            value={selectedPreset}
            onChange={loadSavedSearch}
            data={savedSearches.map((item) => ({ value: item.id, label: item.label }))}
            style={{ minWidth: 220, flexGrow: 1 }}
          />
          <Button
            variant="outline"
            disabled={!query.trim() || savedSearches.length >= MAX_SAVED_SEARCHES}
            onClick={saveCurrentSearch}
          >
            Save this search
          </Button>
          <Button variant="subtle" color="red" disabled={!selectedPreset} onClick={removeSavedSearch}>
            Remove saved search
          </Button>
        </Group>
        <Text size="xs" c="dimmed" mt="xs">
          {savedSearches.length}/{MAX_SAVED_SEARCHES} browser-local searches saved. No CV content,
          selected CV identity or employer data is stored in these presets. Do not use
          shared or untrusted browser profiles for private search criteria.
        </Text>
        {presetMessage && <Alert color="blue" mt="sm">{presetMessage}</Alert>}
      </Card>

      <Card withBorder padding="md" radius="md" mb="md">
        <Title order={4} mb="md">Search</Title>
        <form onSubmit={handleSearch}>
          <Stack gap="md">
            {country === "bj" && (
              <Alert color="blue" title="Benin Republic — provider coverage">
                <Text size="sm">
                  With Any work arrangement, we combine Benin-located jobs and
                  geographically eligible remote jobs from supported sources.
                  Remote only searches Remotive alone, with geographic restrictions
                  checked conservatively. Remote does not guarantee work authorization.
                  Benin workplace jobs are checked using a no-key Dev Global Jobs source,
                  with unsupported locations excluded. Its real coverage may be limited.
                  If an approved Optioncarriere publisher connection is configured,
                  both sources are searched and clear cross-provider duplicates removed.
                  Vacancies unique to either provider are retained.
                  Remotive and Dev Global Jobs listings retain original source links.
                  Verify the work arrangement and job status with the employer.
                </Text>
              </Alert>
            )}
            <TextInput
              label="Search keywords"
              placeholder="e.g., data scientist, software engineer"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />
            <Group gap="md" wrap="wrap">
              <TextInput
                label="Country code (ISO 2-letter)"
                placeholder="bj, ng, gh, fr..."
                description="Any country code; provider coverage varies."
                value={country}
                maxLength={2}
                onChange={(e) => setCountry(e.currentTarget.value.toLowerCase().replace(/[^a-z]/g, ""))}
                style={{ minWidth: 200 }}
              />
              <Select
                label="Quick country"
                placeholder="Choose a common country"
                value={COUNTRIES.some((item) => item.value === country) ? country : null}
                onChange={(v) => { if (v) setCountry(v); }}
                data={COUNTRIES}
                searchable
                clearable
                style={{ minWidth: 190 }}
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

      {showBeninLocalSources(country, remoteOnly) && (
        <Card withBorder padding="md" radius="md" mb="md">
          <Title order={4} mb="xs">Jobs located in Benin — local sources</Title>
          <Text size="sm" c="dimmed" mb="sm">
            The integrated Dev Global Jobs feed can return Benin-located vacancies in
            the normal search results, but may have limited coverage. These additional
            Benin-focused sites help you find other on-site and hybrid vacancies.
            These are browsing shortcuts, not automatically imported records or proof
            that any vacancy is still open. Check location, deadline and application
            requirements on the original posting. You can add a verified vacancy
            manually to track it in Career Intelligence.
          </Text>
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
            {BENIN_LOCAL_SOURCES.map((source) => (
              <Card key={source.url} withBorder padding="sm" radius="sm">
                <Text size="sm" fw={600}>{source.name}</Text>
                <Text size="xs" c="dimmed" mb="sm">{source.note}</Text>
                <Button component="a" href={source.url} target="_blank"
                  rel="noopener noreferrer" variant="light" size="xs">
                  Browse original listings
                </Button>
              </Card>
            ))}
          </SimpleGrid>
          <Group mt="md">
            <Button size="sm" onClick={() => navigate("/jobs/import")}>
              Import a verified vacancy
            </Button>
            <Button variant="outline" size="sm" onClick={() => navigate("/jobs")}>
              Add or review saved jobs
            </Button>
          </Group>
        </Card>
      )}

      {error && (
        <Alert color="red" title="Live job search is unavailable" mt="md">
          <Stack gap="xs">
            <Text size="sm">{error}</Text>
            <Text size="sm">
              No new vacancies were confirmed by this search. You can review
              jobs already saved on this device without another provider request,
              or adjust the country, location or keywords and retry when ready.
              Results from past searches are not automatically verified as open.
            </Text>
            <Group gap="xs">
              <Button size="xs" variant="outline" color="red" onClick={() => navigate("/jobs")}>
                Browse saved jobs
              </Button>
              <Button size="xs" variant="subtle" color="red" onClick={() => navigate("/applications")}>
                Review applications
              </Button>
            </Group>
          </Stack>
        </Alert>
      )}

      {results && (
        <Stack gap="md" mt="md">
          <Group justify="space-between">
            <Title order={3}>
              {results.total} job{results.total !== 1 ? "s" : ""} returned for &quot;{results.query}&quot; in {results.country.toUpperCase()}
            </Title>
          </Group>
          <Text size="sm" c="dimmed">
            Sources in this response: {sourceSummary.length
              ? sourceSummary.map(({ source, count }) => `${source} (${count})`).join(" · ")
              : "None"}. Counts are returned listings, not comprehensive provider coverage.
          </Text>
          <Group gap="md" wrap="wrap">
            <Select label="Provider source" value={sourceFilter} onChange={(value) => setSourceFilter(value ?? "all")}
              data={[{ value: "all", label: "All returned providers" },
                ...availableSources.map((source) => ({ value: source, label: source }))]}
              style={{ minWidth: 195 }} />
            <Select label="Workplace type" value={arrangementFilter}
              onChange={(value) => setArrangementFilter((value ?? "all") as DiscoveryArrangement)}
              data={[
                { value: "all", label: "All arrangements" },
                { value: "local", label: "Benin workplace (not necessarily on-site)" },
                { value: "remote", label: "Remote eligible for search country" },
              ]}
              style={{ minWidth: 245 }} />
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
            <Stack align="center" gap="sm" py="lg">
              <Text c="dimmed" ta="center">
                No jobs were returned by the configured providers for this search.
                Try different keywords or country. Provider coverage varies, and
                an empty response is not proof that no relevant jobs exist.
              </Text>
              <Button variant="light" onClick={() => navigate("/jobs")}>
                Browse previously saved jobs
              </Button>
              <Text c="dimmed" ta="center" size="xs">
                Saved vacancies may be out of date; verify them at the original source before applying.
              </Text>
            </Stack>
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