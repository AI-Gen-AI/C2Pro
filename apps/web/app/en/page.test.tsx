/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@/src/tests/test-utils";

vi.mock("@/components/landing/landing-page", () => ({
  LandingPage: ({ locale }: { locale?: "es" | "en" }) => (
    <main>Three documents. One single truth. {locale}</main>
  ),
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: false,
  }),
}));

import EnglishLandingPage from "./page";

describe("EnglishLandingPage", () => {
  it("renders the English landing body immediately without an auth spinner", () => {
    const { container } = render(<EnglishLandingPage />);

    expect(screen.getByText(/Three documents\. One single truth\./)).toBeInTheDocument();
    expect(container).toHaveTextContent("en");
    expect(screen.queryByText("Loading...")).not.toBeInTheDocument();
  });
});
