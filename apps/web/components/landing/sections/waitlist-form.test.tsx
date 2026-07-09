/**
 * Test Suite ID: TASK-FRT-201
 * Backlog Task: TASK-FRT-201
 */
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@/src/tests/test-utils";
import { landingCopy } from "../copy";
import { WaitlistForm } from "./waitlist-form";

describe("WaitlistForm", () => {
  beforeEach(() => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders all Spanish waitlist fields from copy", () => {
    render(<WaitlistForm copy={landingCopy.es.waitlist} locale="es" />);

    expect(screen.getByLabelText("Nombre")).toHaveAttribute(
      "placeholder",
      "Nombre y apellidos",
    );
    expect(screen.getByLabelText("Empresa")).toHaveAttribute(
      "placeholder",
      "Empresa",
    );
    expect(screen.getByLabelText("Cargo")).toHaveAttribute(
      "placeholder",
      "Tu cargo",
    );
    expect(screen.getByLabelText("Email corporativo")).toHaveAttribute(
      "placeholder",
      "nombre@empresa.com",
    );
    expect(
      screen.getByLabelText("Volumen documental mensual (opcional)"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("checkbox", {
        name: /Acepto el tratamiento de mis datos conforme a la política de privacidad/,
      }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "RGPD" })).toHaveAttribute(
      "href",
      "https://www.ai-gen.ai/privacidad",
    );
  });

  it("renders English waitlist fields from copy", () => {
    render(<WaitlistForm copy={landingCopy.en.waitlist} locale="en" />);

    expect(screen.getByLabelText("Name")).toHaveAttribute(
      "placeholder",
      "Full name",
    );
    expect(screen.getByLabelText("Company")).toHaveAttribute(
      "placeholder",
      "Company",
    );
    expect(screen.getByRole("button", { name: "Request access" })).toBeInTheDocument();
  });

  it("blocks submission until RGPD consent is checked", async () => {
    const user = userEvent.setup();
    render(<WaitlistForm copy={landingCopy.es.waitlist} locale="es" />);

    await user.type(screen.getByLabelText("Nombre"), "Ana Lopez");
    await user.type(screen.getByLabelText("Empresa"), "Constructora Norte");
    await user.type(screen.getByLabelText("Email corporativo"), "ana@example.com");
    await user.click(screen.getByRole("button", { name: "Solicitar acceso" }));

    expect(await screen.findByText("Campo obligatorio.")).toBeInTheDocument();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("shows the success message after a successful submit", async () => {
    const user = userEvent.setup();
    render(<WaitlistForm copy={landingCopy.es.waitlist} locale="es" />);

    await user.type(screen.getByLabelText("Nombre"), "Ana Lopez");
    await user.type(screen.getByLabelText("Empresa"), "Constructora Norte");
    await user.type(screen.getByLabelText("Email corporativo"), "ana@example.com");
    await user.click(
      screen.getByRole("checkbox", {
        name: /Acepto el tratamiento de mis datos conforme a la política de privacidad/,
      }),
    );
    await user.click(screen.getByRole("button", { name: "Solicitar acceso" }));

    expect(
      await screen.findByText(
        "Gracias. Te contactaremos para coordinar tu acceso al piloto.",
      ),
    ).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/waitlist",
      expect.objectContaining({
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: expect.stringContaining('"locale":"es"'),
      }),
    );
  });

  it("keeps input and shows the honest error message after a failed submit", async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ success: false }), {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const user = userEvent.setup();
    render(<WaitlistForm copy={landingCopy.es.waitlist} locale="es" />);

    await user.type(screen.getByLabelText("Nombre"), "Ana Lopez");
    await user.type(screen.getByLabelText("Empresa"), "Constructora Norte");
    await user.type(screen.getByLabelText("Email corporativo"), "ana@example.com");
    await user.click(
      screen.getByRole("checkbox", {
        name: /Acepto el tratamiento de mis datos conforme a la política de privacidad/,
      }),
    );
    await user.click(screen.getByRole("button", { name: "Solicitar acceso" }));

    expect(
      await screen.findByText(
        "No hemos podido registrar tu solicitud. Inténtalo de nuevo o escríbenos a info@ai-gen.ai.",
      ),
    ).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByLabelText("Email corporativo")).toHaveValue(
        "ana@example.com",
      ),
    );
  });

  it("renders an aria-hidden off-screen honeypot", () => {
    render(<WaitlistForm copy={landingCopy.es.waitlist} locale="es" />);

    const honeypot = screen.getByLabelText("Website", { selector: "input" });

    expect(honeypot).toHaveAttribute("aria-hidden", "true");
    expect(honeypot).toHaveAttribute("tabIndex", "-1");
    expect(honeypot).toHaveClass("absolute");
    expect(honeypot).toHaveClass("-left-[9999px]");
  });
});
