import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "./select";

describe("Select", () => {
  it("opens and allows selecting an option", async () => {
    const user = userEvent.setup();

    renderWithProviders(
      <Select defaultValue="alpha">
        <SelectTrigger aria-label="Project">
          <SelectValue placeholder="Select project" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="alpha">Alpha</SelectItem>
          <SelectItem value="beta">Beta</SelectItem>
        </SelectContent>
      </Select>,
    );

    const trigger = screen.getByRole("button", { name: /project/i });
    await user.click(trigger);

    const option = screen.getByRole("option", { name: /beta/i });
    await user.click(option);

    expect(screen.getByText("Beta")).toBeInTheDocument();
  });
});
