import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { CoherenceGauge } from "./CoherenceGauge";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/proj_demo_001/coherence",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("CoherenceGauge", () => {
  it("renders an accessible SVG gauge with score metadata", () => {
    renderWithProviders(
      <CoherenceGauge
        score={82}
        label="Good"
        documentsAnalyzed={8}
        dataPointsChecked={2847}
      />,
    );

    expect(
      screen.getByRole("img", { name: /coherence score: 82\/100/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(
      screen.getByText((content, element) => {
        if (!element) return false;
        return (
          content.includes("Based on") &&
          element.textContent?.includes("8") &&
          element.textContent?.includes("documents")
        );
      }),
    ).toBeInTheDocument();
  });
});
