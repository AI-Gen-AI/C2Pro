import { describe, expect, it } from "vitest";
import userEvent from "@testing-library/user-event";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "./dropdown-menu";

describe("DropdownMenu", () => {
  it("opens and renders menu items", async () => {
    const user = userEvent.setup();
    renderWithProviders(
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button type="button">Open</button>
        </DropdownMenuTrigger>
        <DropdownMenuContent>
          <DropdownMenuItem>Profile</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>,
    );

    await user.click(screen.getByRole("button", { name: /open/i }));
    expect(screen.getByRole("menuitem", { name: /profile/i })).toBeInTheDocument();
  });
});
