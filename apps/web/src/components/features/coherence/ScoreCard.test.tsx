import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { ScoreCard } from "./ScoreCard";

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

describe("ScoreCard", () => {
  it("shows category, score, alerts, and weight", () => {
    renderWithProviders(
      <ScoreCard
        category="Scope"
        score={80}
        weight={0.2}
        alertCount={2}
      />,
    );

    expect(screen.getByRole("button", { name: /scope/i })).toBeInTheDocument();
    expect(screen.getByText("80")).toBeInTheDocument();
    expect(screen.getByText(/2 alerts/i)).toBeInTheDocument();
    expect(screen.getByText(/20% weight/i)).toBeInTheDocument();
  });
});
