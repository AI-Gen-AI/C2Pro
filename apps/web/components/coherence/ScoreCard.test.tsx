import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { ScoreCard } from "@/components/coherence/ScoreCard";

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

// Mock useCountUp to return target value immediately (no animation in tests)
vi.mock("@/hooks/useCountUp", () => ({
  useCountUp: (target: number) => target,
}));

describe("ScoreCard", () => {
  it("shows category, score, alerts, and weight", () => {
    renderWithProviders(
      <ScoreCard
        category="SCOPE"
        score={80}
        weight={0.2}
        alertCount={2}
      />,
    );

    // components/ version renders Card with role="button" and aria-label containing category label
    // CATEGORY_CONFIG["SCOPE"] → label: "Scope", score 80 → severity "Good"
    expect(
      screen.getByRole("button", { name: /scope/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
    expect(screen.getByText("Scope")).toBeInTheDocument();
    expect(screen.getByText("20%")).toBeInTheDocument();
  });
});
