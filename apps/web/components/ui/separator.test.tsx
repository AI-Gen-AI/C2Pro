import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Separator } from "./separator";

describe("Separator", () => {
  it("renders a horizontal separator by default", () => {
    renderWithProviders(<Separator data-testid="sep" />);

    const separator = screen.getByTestId("sep");
    expect(separator).toHaveClass("h-[1px]");
  });

  it("renders a vertical separator when orientation is vertical", () => {
    renderWithProviders(<Separator orientation="vertical" data-testid="sep" />);

    const separator = screen.getByTestId("sep");
    expect(separator).toHaveClass("w-[1px]");
  });
});
