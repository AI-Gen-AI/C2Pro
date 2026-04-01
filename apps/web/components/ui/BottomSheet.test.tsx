import { act, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderWithProviders, screen } from "../../src/tests/test-utils";
import { BottomSheet } from "./BottomSheet";

describe("BottomSheet", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders title and content when opened", async () => {
    renderWithProviders(
      <BottomSheet isOpen onClose={vi.fn()} title="Activity details">
        <div>Sheet content</div>
      </BottomSheet>,
    );

    await act(async () => {
      vi.runAllTimers();
    });

    expect(screen.getByText("Activity details")).toBeInTheDocument();
    expect(screen.getByText("Sheet content")).toBeInTheDocument();
    expect(screen.getByTestId("bottom-sheet-backdrop")).toBeInTheDocument();
  });

  it("calls onClose when the backdrop is clicked", async () => {
    const onClose = vi.fn();
    renderWithProviders(
      <BottomSheet isOpen onClose={onClose} title="Closable">
        <div>Body</div>
      </BottomSheet>,
    );

    await act(async () => {
      vi.runAllTimers();
    });

    fireEvent.click(screen.getByTestId("bottom-sheet-backdrop"));

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes when dragged down past the dismissal threshold", async () => {
    const onClose = vi.fn();
    renderWithProviders(
      <BottomSheet isOpen onClose={onClose} title="Drag me">
        <div>Body</div>
      </BottomSheet>,
    );

    await act(async () => {
      vi.runAllTimers();
    });

    const sheet = screen.getByTestId("bottom-sheet");

    fireEvent.touchStart(sheet, {
      touches: [{ clientY: 100 }],
    });
    fireEvent.touchMove(sheet, {
      touches: [{ clientY: 180 }],
    });
    fireEvent.touchEnd(sheet);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("unmounts after close animation completes", async () => {
    const { rerender } = renderWithProviders(
      <BottomSheet isOpen onClose={vi.fn()} title="Animated">
        <div>Body</div>
      </BottomSheet>,
    );

    await act(async () => {
      vi.runAllTimers();
    });

    expect(screen.getByTestId("bottom-sheet")).toBeInTheDocument();

    rerender(
      <BottomSheet isOpen={false} onClose={vi.fn()} title="Animated">
        <div>Body</div>
      </BottomSheet>,
    );

    await act(async () => {
      vi.advanceTimersByTime(299);
    });
    expect(screen.getByTestId("bottom-sheet")).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.queryByTestId("bottom-sheet")).not.toBeInTheDocument();
  });
});
