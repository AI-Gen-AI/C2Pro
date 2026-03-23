import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import ProjectsPage from "./page";

const useProjectsMock = vi.fn();
const useAuthStoreMock = vi.fn();

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

vi.mock("@/hooks/useProjects", () => ({
  useProjects: (...args: unknown[]) => useProjectsMock(...args),
}));

vi.mock("@/stores/auth", () => ({
  useAuthStore: (selector: (state: { token: string | null }) => unknown) =>
    useAuthStoreMock(selector),
}));

describe("ProjectsPage real-data boundary", () => {
  it("renders the real empty state instead of seeded demo records", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: { items: [] },
      isLoading: false,
      error: null,
    });

    renderWithProviders(<ProjectsPage />);

    expect(
      screen.getByRole("heading", { level: 1, name: /^projects$/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/0 projects/i)).toBeInTheDocument();
    expect(screen.getByText(/no projects yet/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/petrochemical plant epc/i),
    ).not.toBeInTheDocument();
  });

  it("surfaces the backend error instead of rendering demo-backed project rows", () => {
    useAuthStoreMock.mockImplementation(
      (selector: (state: { token: string | null }) => unknown) =>
        selector({ token: "real-token" }),
    );
    useProjectsMock.mockReturnValue({
      data: undefined,
      isLoading: false,
      error: new Error("401 Unauthorized"),
    });

    renderWithProviders(<ProjectsPage />);

    expect(screen.getByText(/api request failed/i)).toBeInTheDocument();
    expect(
      screen.queryByText(/petrochemical plant epc/i),
    ).not.toBeInTheDocument();
  });
});
