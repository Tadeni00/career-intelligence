import { Button, Card, Text, Title } from "@mantine/core";
import { useNavigate } from "react-router-dom";

/** Shown for any URL that does not match a registered route. */
export function NotFoundPage() {
  const navigate = useNavigate();
  return (
    <Card padding="lg" radius="md">
      <Title order={2}>Page not found</Title>
      <Text c="dimmed" mb="md">
        That page does not exist. It may have been renamed, or the link may be out of date.
      </Text>
      <Button onClick={() => navigate("/jobs")}>Go to jobs</Button>
    </Card>
  );
}
