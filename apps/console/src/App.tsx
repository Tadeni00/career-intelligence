import { AppShell, Group, NavLink, Title, Text, Badge, useMantineColorScheme } from "@mantine/core";
import {
  IconDashboard,
  IconUser,
  IconFileText,
  IconBriefcase,
  IconClipboardList,
  IconSun,
  IconMoon,
} from "@tabler/icons-react";
import { Routes, Route, useNavigate } from "react-router-dom";
import { DashboardPage } from "./pages/DashboardPage";
import { ProfilePage } from "./pages/ProfilePage";
import { CVPage } from "./pages/CVPage";
import { JobsPage } from "./pages/JobsPage";
import { JobDetailPage } from "./pages/JobDetailPage";
import { ApplicationsPage } from "./pages/ApplicationsPage";
import { TailoredCVPage } from "./pages/TailoredCVPage";
import { CoverLetterPage } from "./pages/CoverLetterPage";
import { DiscoverPage } from "./pages/DiscoverPage";
import { DiscoveredJobDetailPage } from "./pages/DiscoveredJobDetailPage";
import { NotFoundPage } from "./pages/NotFoundPage";

const navItems = [
  { to: "/dashboard", label: "Dashboard", icon: IconDashboard },
  { to: "/profile", label: "Profile", icon: IconUser },
  { to: "/cv", label: "CV", icon: IconFileText },
  { to: "/jobs", label: "Jobs", icon: IconBriefcase },
  { to: "/discover", label: "Discover", icon: IconBriefcase },
  { to: "/applications", label: "Applications", icon: IconClipboardList },
];

export function App() {
  const navigate = useNavigate();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 240, breakpoint: "sm" }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Group gap="xs">
            <Title order={3}>Career Intelligence</Title>
            <Badge variant="light" size="sm">V1</Badge>
          </Group>
          <Group gap="xs">
            <Text size="sm" c="dimmed">Evidence-driven career operations</Text>
            <NavLink
              component="button"
              onClick={() => toggleColorScheme()}
              label={colorScheme === "dark" ? "Light mode" : "Dark mode"}
              leftSection={colorScheme === "dark" ? <IconSun size={16} /> : <IconMoon size={16} />}
              variant="subtle"
            />
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="xs">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            label={item.label}
            leftSection={<item.icon size={18} />}
            onClick={() => navigate(item.to)}
            active={window.location.pathname === item.to}
            mb={4}
          />
        ))}
      </AppShell.Navbar>

      <AppShell.Main>
        <Routes>
          <Route path="/" element={<DashboardPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="/cv" element={<CVPage />} />
          <Route path="/jobs" element={<JobsPage />} />
          {/* :jobId must match the param JobDetailPage destructures via useParams */}
          <Route path="/jobs/:jobId" element={<JobDetailPage />} />
          {/* Job-scoped tailored-CV workflow. Separate route so a job id is never
              reinterpreted as a tailored-CV id. */}
          <Route path="/jobs/:jobId/tailored-cv" element={<TailoredCVPage />} />
          <Route path="/discover" element={<DiscoverPage />} />
          <Route path="/discovered/:jobId" element={<DiscoveredJobDetailPage />} />
          <Route path="/applications" element={<ApplicationsPage />} />
          {/* Document-specific: always a TailoredCV id, never a job id. */}
          <Route path="/tailored-cvs/:id" element={<TailoredCVPage />} />
          <Route path="/cover-letter/:jobId" element={<CoverLetterPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}
