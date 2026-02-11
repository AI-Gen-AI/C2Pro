import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Skeleton } from "./skeleton";

describe("Skeleton", () => {
  it("renders with default skeleton styles", () => {
    renderWithProviders(<Skeleton data-testid="skeleton" />);

    const skeleton = screen.getByTestId("skeleton");
    expect(skeleton).toHaveClass("animate-pulse");
  });
});
