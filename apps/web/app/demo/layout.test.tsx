import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import DemoLayout from "./layout";

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/demo/projects",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

vi.mock("@/lib/api/generated", () => ({}));

describe("DemoLayout", () => {
  it("renders explicit demo route labeling around child content", () => {
    renderWithProviders(
      <DemoLayout>
        <div>Demo Page Content</div>
      </DemoLayout>,
    );

    expect(
      screen.getByRole("status", { name: /demo mode banner/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(/demo route context/i),
    ).toHaveTextContent(/sample records under \/demo/i);
    expect(screen.getByText("Demo Page Content")).toBeInTheDocument();
  });
});
