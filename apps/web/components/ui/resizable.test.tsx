import { describe, expect, it } from "vitest";
import { renderWithProviders, screen } from "../../src/tests/test-utils";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "./resizable";

describe("Resizable primitives", () => {
  it("renders panels and passes custom classes to the group", () => {
    const { container } = renderWithProviders(
      <ResizablePanelGroup
        direction="horizontal"
        className="test-group"
        data-testid="panel-group"
      >
        <ResizablePanel defaultSize={50}>
          <div>Left panel</div>
        </ResizablePanel>
        <ResizableHandle />
        <ResizablePanel defaultSize={50}>
          <div>Right panel</div>
        </ResizablePanel>
      </ResizablePanelGroup>,
    );

    expect(screen.getByTestId("panel-group")).toHaveClass("test-group");
    expect(screen.getByText("Left panel")).toBeInTheDocument();
    expect(screen.getByText("Right panel")).toBeInTheDocument();
    expect(
      container.querySelector("[data-panel-resize-handle-id]"),
    ).toBeTruthy();
  });

  it("renders the optional grip handle affordance", () => {
    const { container } = renderWithProviders(
      <ResizablePanelGroup direction="horizontal">
        <ResizablePanel defaultSize={50}>
          <div>Primary</div>
        </ResizablePanel>
        <ResizableHandle withHandle />
        <ResizablePanel defaultSize={50}>
          <div>Secondary</div>
        </ResizablePanel>
      </ResizablePanelGroup>,
    );

    expect(container.querySelector("svg")).toBeTruthy();
    expect(container.querySelector(".rounded-sm.border.bg-border")).toBeTruthy();
  });
});
