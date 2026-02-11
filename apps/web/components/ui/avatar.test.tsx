import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Avatar, AvatarFallback, AvatarImage } from "./avatar";

describe("Avatar", () => {
  it("renders fallback content when provided", () => {
    renderWithProviders(
      <Avatar>
        <AvatarImage src="/profile.png" alt="Profile" />
        <AvatarFallback>JD</AvatarFallback>
      </Avatar>,
    );

    expect(screen.getByText("JD")).toBeInTheDocument();
  });
});
