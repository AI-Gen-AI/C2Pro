import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Checkbox } from "./checkbox";

describe("Checkbox", () => {
  it("renders an unchecked checkbox", () => {
    renderWithProviders(<Checkbox aria-label="Accept terms" />);

    const checkbox = screen.getByRole("checkbox", { name: /accept terms/i });
    expect(checkbox).toBeInTheDocument();
    expect(checkbox).not.toBeChecked();
  });

  it("renders a checked checkbox", () => {
    renderWithProviders(<Checkbox aria-label="Subscribe" checked />);

    const checkbox = screen.getByRole("checkbox", { name: /subscribe/i });
    expect(checkbox).toBeChecked();
  });
});
