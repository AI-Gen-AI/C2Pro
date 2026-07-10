/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import { describe, expect, it } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { landingCopy } from "../copy";
import { ConsoleMock } from "./console-mock";

describe("ConsoleMock", () => {
  it("renders the Spanish illustrative console with the pilot evidence line", () => {
    render(<ConsoleMock copy={landingCopy.es.console} />);

    expect(screen.getByTestId("landing-console-mock")).toHaveAttribute(
      "aria-hidden",
      "true",
    );
    expect(screen.getByText("Vista ilustrativa")).toBeInTheDocument();
    expect(
      screen.getByText(
        "«La suma de partidas (636 M) difiere del total declarado (654 M): desviación del 2,8 %.»",
      ),
    ).toBeInTheDocument();
  });

  it("renders the English illustrative console with the pilot evidence line", () => {
    render(<ConsoleMock copy={landingCopy.en.console} />);

    expect(screen.getByText("Illustrative view")).toBeInTheDocument();
    expect(
      screen.getByText(
        "“The sum of line items (636 M) differs from the declared total (654 M): a 2.8 % deviation.”",
      ),
    ).toBeInTheDocument();
  });
});
