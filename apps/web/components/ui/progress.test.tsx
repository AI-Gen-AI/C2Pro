import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Progress } from "./progress";

describe("Progress", () => {
  it("renders indicator with translated width", () => {
    renderWithProviders(<Progress value={40} />);

    const root = screen.getByRole("progressbar");
    const indicator = root.firstElementChild as HTMLElement | null;
    expect(indicator).not.toBeNull();
    expect(indicator).toHaveStyle({ transform: "translateX(-60%)" });
  });
});
