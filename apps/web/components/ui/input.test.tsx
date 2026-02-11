import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Input } from "./input";

describe("Input", () => {
  it("renders an input with provided placeholder", () => {
    renderWithProviders(<Input placeholder="Search projects" />);

    expect(
      screen.getByPlaceholderText(/search projects/i),
    ).toBeInTheDocument();
  });

  it("supports disabled state", () => {
    renderWithProviders(<Input placeholder="Disabled" disabled />);

    const input = screen.getByPlaceholderText(/disabled/i);
    expect(input).toBeDisabled();
  });
});
