/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@/src/tests/test-utils";

vi.mock("@/components/landing/landing-page", () => ({
  LandingPage: ({ locale }: { locale?: "es" | "en" }) => (
    <main>Tres documentos. Una sola verdad. {locale}</main>
  ),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: false,
  }),
}));

import RootPage from "./page";

describe("RootPage", () => {
  it("renders the Spanish landing body immediately without an auth spinner", () => {
    const { container } = render(<RootPage />);

    expect(screen.getByText(/Tres documentos\. Una sola verdad\./)).toBeInTheDocument();
    expect(container).toHaveTextContent("es");
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
    expect(screen.queryByText("Redirecting...")).not.toBeInTheDocument();
  });
});
