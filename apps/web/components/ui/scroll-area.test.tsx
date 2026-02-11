import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import { ScrollArea } from "./scroll-area";

describe("ScrollArea", () => {
  it("renders content inside the scroll area viewport", () => {
    renderWithProviders(
      <ScrollArea>
        <div>Scrollable content</div>
      </ScrollArea>,
    );

    expect(screen.getByText("Scrollable content")).toBeInTheDocument();
  });
});
