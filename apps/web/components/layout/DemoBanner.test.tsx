import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { DemoBanner } from "./DemoBanner";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("DemoBanner", () => {
  it("renders demo status messaging with the provided project name", () => {
    renderWithProviders(<DemoBanner projectName="Atlas Plaza" />);

    expect(
      screen.getByRole("status", { name: /demo mode banner/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/sample data for atlas plaza project/i),
    ).toBeInTheDocument();
  });

  it("fires the dismiss callback when clicked", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    renderWithProviders(<DemoBanner onDismiss={onDismiss} />);

    await user.click(
      screen.getByRole("button", { name: /dismiss demo banner/i }),
    );

    expect(onDismiss).toHaveBeenCalledTimes(1);
  });
});
