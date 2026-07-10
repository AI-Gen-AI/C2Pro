/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { LandingPage } from "./landing-page";

vi.mock("./fonts", () => ({
  landingFontClasses: "font-sans",
}));

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: false,
  }),
}));

describe("LandingPage", () => {
  it("renders the Spanish landing with the required copy and landmarks", () => {
    render(<LandingPage locale="es" />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Tres documentos. Una sola verdad.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Programa piloto · en validación")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Plazas limitadas para organizaciones con alto volumen documental.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toBeInTheDocument();
    expect(screen.getByRole("contentinfo")).toBeInTheDocument();
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Privacidad (RGPD)" })).toHaveAttribute(
      "href",
      "https://www.ai-gen.ai/privacidad",
    );
  });

  it("renders the English landing with the required copy", () => {
    render(<LandingPage locale="en" />);

    expect(
      screen.getByRole("heading", {
        level: 1,
        name: "Three documents. One single truth.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByText("Pilot program · in validation")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: "Limited seats for organizations with high document volume.",
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Privacy (GDPR)" })).toHaveAttribute(
      "href",
      "https://www.ai-gen.ai/privacidad",
    );
  });

  it("does not render the old fabricated landing strings", () => {
    const { container } = render(<LandingPage locale="es" />);
    const oldClaims = [
      ["94", "%"],
      ["$", "2", ".", "4", "M"],
      ["6x", " Faster"],
      ["Join", " enterprise"],
      ["Access", " Real Workspace"],
    ].map((parts) => parts.join(""));

    for (const oldClaim of oldClaims) {
      expect(container).not.toHaveTextContent(oldClaim);
    }
  });
});
