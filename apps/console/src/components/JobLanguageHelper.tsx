import { Alert, Button, Card, Group, Text, Title } from "@mantine/core";
import { jobEnglishTranslation } from "../jobTranslation";

type Props = { description: string | null | undefined };

export function JobLanguageHelper({ description }: Props) {
  const original = description?.trim() ?? "";
  const translation = jobEnglishTranslation(original);
  return (
    <Card withBorder padding="md" radius="md" mb="md">
      <Group justify="space-between" align="center" mb="xs">
        <Title order={3}>Job description · Original language</Title>
        {translation && (
          <Button
            component="a"
            href={translation.url}
            target="_blank"
            rel="noopener noreferrer"
            variant="light"
            size="sm"
          >
            Read in English ↗
          </Button>
        )}
      </Group>
      <Text size="xs" c="dimmed" mb="sm">
        The original advert is kept unchanged. “Read in English” opens Google Translate
        only when clicked and shares the displayed job-description text with Google,
        not your CV or career profile. Verify deadlines, location, eligibility and
        application instructions against the original posting.
      </Text>
      {translation?.partial && (
        <Alert color="yellow" mb="sm">
          The advert is long. The English translation link includes only the first
          3,500 characters; review the full original below.
        </Alert>
      )}
      <Text style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
        {original || "No original job description was supplied."}
      </Text>
    </Card>
  );
}
