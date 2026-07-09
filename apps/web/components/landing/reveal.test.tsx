/**
 * Test Suite ID: TASK-FRT-199
 * Backlog Task: TASK-FRT-199
 */
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@/src/tests/test-utils";
import { Reveal } from "./reveal";

type ObserverCallback = IntersectionObserverCallback;

let observerCallback: ObserverCallback | undefined;
const observe = vi.fn();
const disconnect = vi.fn();
const unobserve = vi.fn();

function installIntersectionObserver() {
  observerCallback = undefined;
  observe.mockClear();
  disconnect.mockClear();
  unobserve.mockClear();

  class MockIntersectionObserver implements IntersectionObserver {
    readonly root = null;
    readonly rootMargin = "";
    readonly thresholds = [0.1];

    constructor(callback: ObserverCallback) {
      observerCallback = callback;
    }

    disconnect = disconnect;
    observe = observe;
    takeRecords = () => [];
    unobserve = unobserve;
  }

  vi.stubGlobal("IntersectionObserver", MockIntersectionObserver);
}

function setReducedMotion(matches: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
}

describe("Reveal", () => {
  beforeEach(() => {
    installIntersectionObserver();
    setReducedMotion(false);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("hides with motion-safe classes then becomes visible on intersection", () => {
    render(<Reveal>Revealed content</Reveal>);

    const wrapper = screen.getByText("Revealed content");
    expect(wrapper).toHaveClass("motion-safe:opacity-0");
    expect(wrapper).toHaveClass("motion-safe:translate-y-3");
    expect(observe).toHaveBeenCalledTimes(1);

    act(() => {
      observerCallback?.(
        [{ isIntersecting: true } as IntersectionObserverEntry],
        {} as IntersectionObserver,
      );
    });

    expect(wrapper).toHaveClass("opacity-100", "translate-y-0");
    expect(wrapper).not.toHaveClass("motion-safe:opacity-0");
  });

  it("renders without motion classes when reduced motion is preferred", async () => {
    setReducedMotion(true);

    render(<Reveal>Static content</Reveal>);

    const wrapper = screen.getByText("Static content");
    await waitFor(() => {
      expect(wrapper).toHaveClass("opacity-100", "translate-y-0");
    });
    expect(wrapper).not.toHaveClass("motion-safe:opacity-0");
    expect(observe).not.toHaveBeenCalled();
  });
});
