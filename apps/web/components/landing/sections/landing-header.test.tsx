/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@/src/tests/test-utils";
import { landingCopy } from "../copy";
import { LandingHeader } from "./landing-header";

vi.mock("@clerk/nextjs", () => ({
  useAuth: () => ({
    isLoaded: true,
    isSignedIn: false,
  }),
}));

describe("LandingHeader", () => {
  it("renders locale nav anchors and the locale switch", () => {
    render(<LandingHeader copy={landingCopy.es.header} locale="es" />);

    expect(screen.getByRole("navigation", { name: "Principal" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Producto" })).toHaveAttribute(
      "href",
      "#producto",
    );
    expect(screen.getByRole("link", { name: "Cómo funciona" })).toHaveAttribute(
      "href",
      "#como-funciona",
    );
    expect(screen.getByRole("link", { name: "EN" })).toHaveAttribute("href", "/en");
  });

  it("opens and closes the mobile menu", async () => {
    const user = userEvent.setup();
    render(<LandingHeader copy={landingCopy.en.header} locale="en" />);

    const button = screen.getByRole("button", { name: "Menu" });
    expect(button).toHaveAttribute("aria-expanded", "false");

    await user.click(button);

    expect(button).toHaveAttribute("aria-expanded", "true");
    const dialog = screen.getByRole("dialog", { name: "Menu" });
    expect(within(dialog).getByRole("link", { name: "How it works" })).toHaveAttribute(
      "href",
      "#como-funciona",
    );

    await user.click(screen.getByRole("button", { name: "Close menu" }));
    expect(button).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("dialog", { name: "Menu" })).not.toBeInTheDocument();
  });
});
