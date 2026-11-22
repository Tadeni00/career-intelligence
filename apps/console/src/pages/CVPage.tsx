import { Card } from "@mantine/core";
import { ProfileManager } from "../ProfileManager";

export function CVPage() {
  return (
    <Card padding="lg" radius="md">
      <ProfileManager />
    </Card>
  );
}