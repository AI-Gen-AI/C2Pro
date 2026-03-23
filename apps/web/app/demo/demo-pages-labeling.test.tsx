import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import DemoAlertsPage from "./alerts/page";
import DemoDocumentsPage from "./documents/page";
import DemoEvidencePage from "./evidence/page";
import DemoRaciPage from "./raci/page";
import DemoSettingsPage from "./settings/page";
import DemoStakeholdersPage from "./stakeholders/page";
import DemoProjectDetailPage from "./projects/[id]/page";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/demo/projects/demo-proj-001",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
  useParams: () => ({
    id: "demo-proj-001",
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("Demo page labeling", () => {
  it("keeps explicit demo/sample wording on every reviewed demo screen", () => {
    const screens = [
      {
        component: <DemoAlertsPage />,
        text: /demo alerts showing sample contract coherence issues/i,
      },
      {
        component: <DemoDocumentsPage />,
        text: /demo documents showing sample contract analysis/i,
      },
      {
        component: <DemoEvidencePage />,
        text: /this is a demo feature/i,
      },
      {
        component: <DemoRaciPage />,
        text: /demo raci matrix showing sample responsibility assignments/i,
      },
      {
        component: <DemoSettingsPage />,
        text: /settings are view-only in demo mode/i,
      },
      {
        component: <DemoStakeholdersPage />,
        text: /demo stakeholder matrix showing sample project participants/i,
      },
      {
        component: <DemoProjectDetailPage />,
        text: /viewing demo project details/i,
      },
    ];

    for (const demoScreen of screens) {
      const view = renderWithProviders(demoScreen.component);
      expect(screen.getByText(demoScreen.text)).toBeInTheDocument();
      view.unmount();
    }
  });
});
