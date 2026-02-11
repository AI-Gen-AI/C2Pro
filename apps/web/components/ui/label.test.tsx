import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { Label } from "./label";

describe("Label", () => {
  it("associates with a form control", () => {
    renderWithProviders(
      <div>
        <Label htmlFor="project">Project</Label>
        <input id="project" />
      </div>,
    );

    const control = screen.getByLabelText(/project/i);
    expect(control).toBeInTheDocument();
  });
});
