import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Button } from "./button";

describe("Button", () => {
  it("renders a button with default variant classes", () => {
    renderWithProviders(<Button>Submit</Button>);

    const button = screen.getByRole("button", { name: /submit/i });
    expect(button).toHaveClass("bg-primary");
  });

  it("supports rendering as a child element", () => {
    renderWithProviders(
      <Button asChild>
        <a href="/projects">Projects</a>
      </Button>,
    );

    const link = screen.getByRole("link", { name: /projects/i });
    expect(link).toHaveClass("inline-flex");
  });
});
