import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Badge } from "./badge";

describe("Badge", () => {
  it("renders with default variant styles", () => {
    renderWithProviders(<Badge>Default</Badge>);

    const badge = screen.getByText("Default");
    expect(badge).toHaveClass("bg-primary");
  });

  it("supports success variant styles", () => {
    renderWithProviders(<Badge variant="success">Success</Badge>);

    const badge = screen.getByText("Success");
    expect(badge).toHaveClass("bg-success-bg");
  });
});
