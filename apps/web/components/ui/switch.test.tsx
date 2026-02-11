import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Switch } from "./switch";

describe("Switch", () => {
  it("toggles the checked state", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Switch aria-label="Enable notifications" />);

    const toggle = screen.getByRole("switch", { name: /enable notifications/i });
    expect(toggle).toHaveAttribute("data-state", "unchecked");

    await user.click(toggle);
    expect(toggle).toHaveAttribute("data-state", "checked");
  });
});
