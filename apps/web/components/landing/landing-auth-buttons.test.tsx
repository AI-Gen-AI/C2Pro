/**
 * Test Suite ID: TASK-FRT-198
 * Backlog Task: TASK-FRT-198
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@/src/tests/test-utils";

let signedIn = false;

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: signedIn,
  }),
}));

import { LandingAuthButtons } from "./landing-auth-buttons";

describe("LandingAuthButtons", () => {
  beforeEach(() => {
    signedIn = false;
  });

  it("shows the sign-in action for signed-out visitors", () => {
    render(<LandingAuthButtons />);

    expect(
      screen.getByRole("link", { name: "Iniciar sesión" }),
    ).toHaveAttribute("href", "/login");
    expect(
      screen.getByRole("link", { name: "Unirse al piloto" }),
    ).toHaveAttribute("href", "#waitlist");
    expect(
      screen.queryByRole("link", { name: "Ir al workspace" }),
    ).not.toBeInTheDocument();
  });

  it("shows the workspace action for signed-in users", () => {
    signedIn = true;

    render(<LandingAuthButtons />);

    expect(
      screen.getByRole("link", { name: "Ir al workspace" }),
    ).toHaveAttribute("href", "/dashboard");
    expect(
      screen.queryByRole("link", { name: "Iniciar sesión" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Unirse al piloto" }),
    ).not.toBeInTheDocument();
  });

  it("uses provided labels for locale-specific copy", () => {
    render(
      <LandingAuthButtons
        labels={{
          signIn: "Sign in",
          joinPilot: "Join the pilot",
          workspace: "Go to workspace",
        }}
      />,
    );

    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute(
      "href",
      "/login",
    );
    expect(
      screen.getByRole("link", { name: "Join the pilot" }),
    ).toHaveAttribute("href", "#waitlist");
  });
});
