import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Textarea } from "./textarea";

describe("Textarea", () => {
  it("renders a textarea with placeholder", () => {
    renderWithProviders(<Textarea placeholder="Describe the issue" />);

    expect(
      screen.getByPlaceholderText(/describe the issue/i),
    ).toBeInTheDocument();
  });

  it("supports disabled state", () => {
    renderWithProviders(<Textarea placeholder="Disabled" disabled />);

    const textarea = screen.getByPlaceholderText(/disabled/i);
    expect(textarea).toBeDisabled();
  });
});
