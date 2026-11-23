import { useState } from "react";
import { Alert, Button, Card, Group, Select, Stack, Text, Textarea, TextInput, Title } from "@mantine/core";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api";
import { extractVacancyDraft } from "../vacancyDraftExtraction";

type ImportedJob = { job_id: number; created: boolean; message: string };

export function ImportVacancyPage() {
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [company, setCompany] = useState("");
  const [location, setLocation] = useState("");
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [arrangement, setArrangement] = useState("UNKNOWN");
  const [saving, setSaving] = useState(false);
  const [sourceSnippet, setSourceSnippet] = useState("");
  const [extractionNotice, setExtractionNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const previewStructuredData = () => {
    setError(null);
    setExtractionNotice(null);
    const draft = extractVacancyDraft(sourceSnippet);
    if (!draft) {
      setError("No single complete JobPosting record was found. You can still paste the description and fill in the fields manually.");
      return;
    }
    // A draft is never saved automatically; the person verifies it first.
    setTitle(draft.title);
    setCompany(draft.company);
    setLocation(draft.location);
    setDescription(draft.description);
    setArrangement(draft.arrangement);
    setExtractionNotice("Fields were prefilled from pasted structured data. " + draft.warning);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!title.trim() || !company.trim() || !location.trim()) {
      setError("Confirm the title, employer and workplace before importing.");
      return;
    }
    if (description.trim().length < 30) {
      setError("Paste at least 30 characters of the original job description.");
      return;
    }
    if (url.trim()) {
      try {
        const parsed = new URL(url.trim());
        if (parsed.protocol !== "https:" || parsed.username || parsed.password) {
          setError("The original posting link must use HTTPS without credentials.");
          return;
        }
      } catch {
        setError("Enter a valid original posting URL, or leave it blank.");
        return;
      }
    }
    setSaving(true);
    try {
      const result = await api<ImportedJob>("/jobs/import", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          company: company.trim(),
          location: location.trim(),
          url: url.trim() || null,
          description: description.trim(),
          remote_status: arrangement,
        }),
      });
      navigate(`/jobs/${result.job_id}`);
    } catch (caught) {
      setError(errorMessage(caught, "Unable to save the vacancy."));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card padding="lg" radius="md" maw={850}>
      <Title order={2} mb="xs">Import a job vacancy</Title>
      <Text size="sm" c="dimmed" mb="lg">
        Found a vacancy on ANPE Bénin, an employer website or another job board?
        Paste its description, confirm the facts and save it to Career Intelligence.
        No external site is fetched; the URL is a reference to the original posting,
        not proof that it is still open. Requirement extraction and CV matching can
        be run from the saved job's detail page.
      </Text>
      {error && <Alert color="red" mb="md" title="Import could not be saved">{error}</Alert>}
      <Card withBorder padding="md" radius="md" mb="lg">
        <Title order={4} mb="xs">Assisted extraction (optional)</Title>
        <Text size="sm" c="dimmed" mb="sm">
          If the source page includes JobPosting JSON-LD, paste that block or the
          copied page HTML here. The browser reads it locally without requesting
          the website or executing its scripts. This is an unverified draft.
          If unavailable, use the manual fields below instead.
        </Text>
        <Textarea label="Paste JobPosting JSON-LD or copied HTML"
          value={sourceSnippet} onChange={(event) => setSourceSnippet(event.currentTarget.value)}
          autosize minRows={3} maxRows={7}
          placeholder='{"@context":"https://schema.org","@type":"JobPosting", ...}' />
        <Group justify="flex-end" mt="sm">
          <Button variant="light" onClick={previewStructuredData} disabled={!sourceSnippet.trim()}>
            Extract draft for review
          </Button>
        </Group>
        {extractionNotice && <Alert color="blue" mt="sm">{extractionNotice}</Alert>}
      </Card>
      <form onSubmit={submit}>
        <Stack gap="md">
          <TextInput label="Job title" required maxLength={255} value={title}
            onChange={(event) => setTitle(event.currentTarget.value)}
            placeholder="e.g. Chargé de suivi-évaluation" />
          <TextInput label="Employer / organisation" required maxLength={255} value={company}
            onChange={(event) => setCompany(event.currentTarget.value)}
            placeholder="Name shown in the original vacancy" />
          <TextInput label="Workplace (city and country)" required maxLength={255} value={location}
            onChange={(event) => setLocation(event.currentTarget.value)}
            placeholder="e.g. Cotonou, Bénin" />
          <Select label="Work arrangement (only if explicitly stated)"
            value={arrangement} onChange={(value) => setArrangement(value ?? "UNKNOWN")}
            data={[
              { value: "UNKNOWN", label: "Not verified" },
              { value: "ONSITE", label: "On-site" },
              { value: "HYBRID", label: "Hybrid" },
              { value: "REMOTE", label: "Remote" },
            ]} />
          <TextInput label="Original vacancy URL (optional)" value={url}
            onChange={(event) => setUrl(event.currentTarget.value)}
            maxLength={2048} placeholder="https://..." />
          <Textarea label="Paste original job description" required minRows={9}
            autosize maxRows={18} value={description}
            onChange={(event) => setDescription(event.currentTarget.value)}
            description="Keep the responsibilities, requirements and application deadline where stated. Do not paste personal information."
            placeholder="Copy the published job description here..." />
          <Alert color="blue">
            Please verify employer, location, deadline and application instructions.
            We do not auto-submit applications or claim that an imported posting is verified.
          </Alert>
          <Group justify="flex-end">
            <Button variant="subtle" onClick={() => navigate("/jobs")}>Cancel</Button>
            <Button type="submit" loading={saving} disabled={saving}>
              Save vacancy and review
            </Button>
          </Group>
        </Stack>
      </form>
    </Card>
  );
}
