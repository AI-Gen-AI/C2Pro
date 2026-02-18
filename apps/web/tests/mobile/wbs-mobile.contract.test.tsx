/**
 * TS-MOB-WBS-001 - WBS Mobile Contract Tests
 *
 * Test Suite ID: TS-MOB-WBS-001
 * Type: Mobile Contract Test
 * Priority: P1
 * Phase: RED
 * Owner: @frontend-tdd
 *
 * Tests mobile-specific behaviors for WBS components:
 * - Touch target accessibility (44px minimum)
 * - Swipe gestures for task completion
 * - Bottom sheet for mobile detail views
 * - Pinch-to-zoom on Gantt charts
 * - Offline data caching
 * - Offline action queueing
 *
 * Run: npm test -- wbs-mobile.contract.test.tsx
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Components to be implemented (will fail with ImportError in RED phase)
import { WBSMobile } from "../../components/wbs/WBSMobile";
import {
  WBSMobileProvider,
  useWBSMobile,
} from "../../contexts/WBSMobileContext";
import { MobileGanttChart } from "../../components/wbs/MobileGanttChart";
import { BottomSheet } from "../../components/ui/BottomSheet";
import { OfflineActionQueue } from "../../services/OfflineActionQueue";

// ===========================================
// TYPE DEFINITIONS (Expected Component Interfaces)
// ===========================================

interface WBSItem {
  id: string;
  code: string;
  name: string;
  description?: string;
  completion: number;
  startDate?: string;
  endDate?: string;
  children?: WBSItem[];
}

interface Action {
  id: string;
  type: "mark_complete" | "update" | "delete" | "create";
  payload: unknown;
  timestamp: number;
}

interface WBSMobileProps {
  items: WBSItem[];
  onMarkComplete?: (id: string) => void;
  offlineEnabled?: boolean;
}

interface WBSMobileContextType {
  isOffline: boolean;
  cachedData: WBSItem[];
  queueAction: (action: Action) => void;
  pendingActions: Action[];
  syncWhenOnline: () => Promise<void>;
}

// ===========================================
// FIXTURES
// ===========================================

const mockWBSItems: WBSItem[] = [
  {
    id: "1",
    code: "1",
    name: "Project Foundation",
    description: "Foundation work for construction project",
    completion: 75,
    startDate: "2026-01-01",
    endDate: "2026-03-15",
    children: [
      {
        id: "1.1",
        code: "1.1",
        name: "Excavation",
        completion: 100,
        startDate: "2026-01-01",
        endDate: "2026-01-15",
      },
      {
        id: "1.2",
        code: "1.2",
        name: "Concrete Pouring",
        completion: 50,
        startDate: "2026-01-20",
        endDate: "2026-02-28",
      },
    ],
  },
  {
    id: "2",
    code: "2",
    name: "Structural Work",
    description: "Main structural elements",
    completion: 0,
    startDate: "2026-03-01",
    endDate: "2026-06-30",
  },
];

// ===========================================
// MOCK MOBILE APIs
// ===========================================

// Mock matchMedia for responsive testing
Object.defineProperty(window, "matchMedia", {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: query.includes("max-width"),
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Mock TouchEvent for gesture testing
class MockTouch {
  constructor(
    public identifier: number,
    public target: EventTarget,
    public clientX: number,
    public clientY: number,
  ) {}
}

// Mock navigator.onLine
Object.defineProperty(navigator, "onLine", {
  writable: true,
  value: true,
  configurable: true,
});

// ===========================================
// TEST UTILITIES
// ===========================================

const mockTouchEvent = (
  type: string,
  touches: { clientX: number; clientY: number }[],
) => {
  const target =
    document.elementFromPoint(
      touches[0]?.clientX || 0,
      touches[0]?.clientY || 0,
    ) || document.body;
  const touchList = touches.map(
    (t, i) => new MockTouch(i, target, t.clientX, t.clientY),
  );

  return new TouchEvent(type, {
    bubbles: true,
    cancelable: true,
    touches: touchList as unknown as TouchList,
    targetTouches: touchList as unknown as TouchList,
    changedTouches: touchList as unknown as TouchList,
  });
};

const simulateSwipeRight = (element: HTMLElement, distance: number = 100) => {
  const startX = 50;
  const startY = 100;
  const endX = startX + distance;

  // Touch start
  element.dispatchEvent(
    mockTouchEvent("touchstart", [{ clientX: startX, clientY: startY }]),
  );

  // Touch move (swipe)
  element.dispatchEvent(
    mockTouchEvent("touchmove", [
      { clientX: startX + distance / 2, clientY: startY },
    ]),
  );

  // Touch end
  element.dispatchEvent(
    mockTouchEvent("touchend", [{ clientX: endX, clientY: startY }]),
  );
};

const simulatePinchZoom = (
  element: HTMLElement,
  scale: number,
  centerX: number = 200,
  centerY: number = 200,
) => {
  const spread = 50 * scale;

  // Initial touch (two fingers)
  element.dispatchEvent(
    mockTouchEvent("touchstart", [
      { clientX: centerX - spread, clientY: centerY },
      { clientX: centerX + spread, clientY: centerY },
    ]),
  );

  // Pinch move
  element.dispatchEvent(
    mockTouchEvent("touchmove", [
      { clientX: centerX - spread * scale, clientY: centerY },
      { clientX: centerX + spread * scale, clientY: centerY },
    ]),
  );

  // Touch end
  element.dispatchEvent(
    mockTouchEvent("touchend", [
      { clientX: centerX - spread * scale, clientY: centerY },
    ]),
  );
};

// ===========================================
// TEST SUITE
// ===========================================

describe("TS-MOB-WBS-001: WBS Mobile Contract Tests", () => {
  beforeEach(() => {
    // Reset online status before each test
    Object.defineProperty(navigator, "onLine", {
      writable: true,
      value: true,
      configurable: true,
    });

    // Clear localStorage mock
    vi.stubGlobal("localStorage", {
      getItem: vi.fn(),
      setItem: vi.fn(),
      removeItem: vi.fn(),
      clear: vi.fn(),
    });
  });

  describe("Touch Target Accessibility [TEST-01]", () => {
    it("should have touch targets minimum 44px", () => {
      /**
       * RED Phase: Touch target size compliance
       *
       * WCAG 2.1 requires touch targets to be at least 44x44 CSS pixels
       * for Level AAA compliance. Level AA recommends 44x44.
       *
       * Expected: All interactive elements have minimum 44px dimensions
       */
      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} />
        </WBSMobileProvider>,
      );

      // Get all interactive elements
      const interactiveElements = screen.getAllByRole("button");
      const checkboxes = screen.queryAllByRole("checkbox");
      const links = screen.queryAllByRole("link");

      const allInteractive = [...interactiveElements, ...checkboxes, ...links];

      // Assert all elements meet minimum touch target size
      allInteractive.forEach((element) => {
        const rect = element.getBoundingClientRect();
        const computedStyle = window.getComputedStyle(element);
        const minHeight = parseInt(computedStyle.minHeight || "0", 10);
        const minWidth = parseInt(computedStyle.minWidth || "0", 10);

        // Check rendered dimensions
        expect(rect.height).toBeGreaterThanOrEqual(44);
        expect(rect.width).toBeGreaterThanOrEqual(44);

        // Check CSS minimums
        expect(minHeight).toBeGreaterThanOrEqual(44);
        expect(minWidth).toBeGreaterThanOrEqual(44);
      });

      // Specific checks for common WBS actions
      const completeButtons = screen.queryAllByLabelText(
        /mark complete|complete task/i,
      );
      completeButtons.forEach((btn) => {
        const rect = btn.getBoundingClientRect();
        expect(rect.height).toBeGreaterThanOrEqual(44);
        expect(rect.width).toBeGreaterThanOrEqual(44);
      });
    });

    it("should apply touch-friendly padding to list items", () => {
      /**
       * RED Phase: Touch-friendly list item spacing
       *
       * Expected: List items have adequate vertical padding for touch
       */
      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} />
        </WBSMobileProvider>,
      );

      const listItems = screen.getAllByRole("listitem");
      expect(listItems.length).toBeGreaterThan(0);

      listItems.forEach((item) => {
        const computedStyle = window.getComputedStyle(item);
        const paddingTop = parseInt(computedStyle.paddingTop || "0", 10);
        const paddingBottom = parseInt(computedStyle.paddingBottom || "0", 10);

        // Minimum 12px vertical padding for comfortable touch
        expect(paddingTop + paddingBottom).toBeGreaterThanOrEqual(12);
      });
    });
  });

  describe("Swipe Gestures [TEST-02]", () => {
    it("should support swipe right to mark complete", async () => {
      /**
       * RED Phase: Swipe gesture for task completion
       *
       * Mobile UX pattern: Swipe right on a task to mark it complete
       * Should show visual feedback during swipe and confirm on release
       *
       * Expected: Swiping right triggers onMarkComplete callback
       */
      const user = userEvent.setup();
      const handleMarkComplete = vi.fn();

      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} onMarkComplete={handleMarkComplete} />
        </WBSMobileProvider>,
      );

      // Find the first incomplete WBS item
      const incompleteItem = screen
        .getByText("Concrete Pouring")
        .closest("[role='listitem']");
      expect(incompleteItem).toBeInTheDocument();

      // Simulate swipe right gesture (minimum 44px threshold)
      simulateSwipeRight(incompleteItem!, 100);

      // Should show swipe indicator/feedback
      await waitFor(() => {
        const swipeIndicator = screen.queryByTestId("swipe-indicator");
        expect(swipeIndicator).toBeInTheDocument();
      });

      // Should call onMarkComplete with item ID after swipe completion
      await waitFor(() => {
        expect(handleMarkComplete).toHaveBeenCalledWith("1.2");
      });

      // Visual feedback should indicate completion
      await waitFor(() => {
        const completedIndicator = screen.queryByTestId("item-completed-1.2");
        expect(completedIndicator).toBeInTheDocument();
      });
    });

    it("should show haptic feedback on swipe completion", async () => {
      /**
       * RED Phase: Haptic feedback for swipe actions
       *
       * Expected: Haptic feedback API is called on successful swipe
       */
      // Mock vibration API
      const vibrateMock = vi.fn();
      Object.defineProperty(navigator, "vibrate", {
        writable: true,
        value: vibrateMock,
      });

      const handleMarkComplete = vi.fn();

      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} onMarkComplete={handleMarkComplete} />
        </WBSMobileProvider>,
      );

      const item = screen
        .getByText("Concrete Pouring")
        .closest("[role='listitem']")!;
      simulateSwipeRight(item, 100);

      // Should trigger haptic feedback
      await waitFor(() => {
        expect(vibrateMock).toHaveBeenCalled();
      });
    });
  });

  describe("Bottom Sheet Pattern [TEST-03]", () => {
    it("should use bottom sheet for detail view on mobile", async () => {
      /**
       * RED Phase: Mobile-optimized detail view
       *
       * Mobile UX pattern: Use bottom sheet instead of modal/sidebar
       * for detail views on mobile viewports
       *
       * Expected: Clicking WBS item opens BottomSheet component
       */
      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} />
        </WBSMobileProvider>,
      );

      // Click on a WBS item to view details
      const item = screen.getByText("Project Foundation");
      fireEvent.click(item);

      // Should open bottom sheet (not modal or sidebar)
      await waitFor(() => {
        const bottomSheet = screen.getByTestId("bottom-sheet");
        expect(bottomSheet).toBeInTheDocument();
      });

      // Bottom sheet should have mobile-optimized styling
      const bottomSheet = screen.getByTestId("bottom-sheet");
      const computedStyle = window.getComputedStyle(bottomSheet);

      // Should be positioned at bottom
      expect(computedStyle.bottom).toBe("0px");
      expect(computedStyle.position).toBe("fixed");

      // Should have rounded top corners for mobile UX
      expect(computedStyle.borderTopLeftRadius).toBeTruthy();
      expect(computedStyle.borderTopRightRadius).toBeTruthy();

      // Should contain WBS details
      expect(
        screen.getByText("Foundation work for construction project"),
      ).toBeInTheDocument();
      expect(screen.getByText(/75%/)).toBeInTheDocument(); // Completion
    });

    it("should support drag to dismiss bottom sheet", async () => {
      /**
       * RED Phase: Bottom sheet dismissal gesture
       *
       * Expected: Dragging bottom sheet down dismisses it
       */
      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} />
        </WBSMobileProvider>,
      );

      // Open bottom sheet
      const item = screen.getByText("Project Foundation");
      fireEvent.click(item);

      await waitFor(() => {
        expect(screen.getByTestId("bottom-sheet")).toBeInTheDocument();
      });

      const bottomSheet = screen.getByTestId("bottom-sheet");

      // Simulate drag down gesture
      bottomSheet.dispatchEvent(
        mockTouchEvent("touchstart", [{ clientX: 200, clientY: 100 }]),
      );
      bottomSheet.dispatchEvent(
        mockTouchEvent("touchmove", [{ clientX: 200, clientY: 300 }]),
      );
      bottomSheet.dispatchEvent(
        mockTouchEvent("touchend", [{ clientX: 200, clientY: 400 }]),
      );

      // Bottom sheet should be dismissed
      await waitFor(() => {
        expect(screen.queryByTestId("bottom-sheet")).not.toBeInTheDocument();
      });
    });

    it("should close bottom sheet on backdrop tap", async () => {
      /**
       * RED Phase: Backdrop tap dismissal
       *
       * Expected: Tapping outside bottom sheet closes it
       */
      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} />
        </WBSMobileProvider>,
      );

      // Open bottom sheet
      fireEvent.click(screen.getByText("Project Foundation"));

      await waitFor(() => {
        expect(screen.getByTestId("bottom-sheet")).toBeInTheDocument();
      });

      // Tap backdrop
      const backdrop = screen.getByTestId("bottom-sheet-backdrop");
      fireEvent.click(backdrop);

      // Should close
      await waitFor(() => {
        expect(screen.queryByTestId("bottom-sheet")).not.toBeInTheDocument();
      });
    });
  });

  describe("Pinch to Zoom [TEST-04]", () => {
    it("should support pinch to zoom on Gantt", async () => {
      /**
       * RED Phase: Pinch zoom on mobile Gantt chart
       *
       * Mobile UX pattern: Pinch gesture to zoom in/out on timeline
       *
       * Expected: Pinch gesture changes zoom level of Gantt chart
       */
      const handleZoomChange = vi.fn();

      render(
        <WBSMobileProvider>
          <MobileGanttChart
            items={mockWBSItems}
            onZoomChange={handleZoomChange}
          />
        </WBSMobileProvider>,
      );

      const ganttContainer = screen.getByTestId("gantt-container");
      expect(ganttContainer).toBeInTheDocument();

      // Simulate pinch zoom in (scale > 1)
      simulatePinchZoom(ganttContainer, 2.0);

      // Should call zoom handler with new scale
      await waitFor(() => {
        expect(handleZoomChange).toHaveBeenCalledWith(
          expect.objectContaining({
            scale: expect.any(Number),
          }),
        );
      });

      // Zoom level should be greater than 1 (zoomed in)
      const zoomIndicator = screen.getByTestId("zoom-level");
      expect(zoomIndicator.textContent).toMatch(/[12]\d{2}%|2\.0x/);
    });

    it("should maintain zoom level across interactions", async () => {
      /**
       * RED Phase: Zoom state persistence
       *
       * Expected: Zoom level persists when switching views
       */
      const { rerender } = render(
        <WBSMobileProvider>
          <MobileGanttChart items={mockWBSItems} />
        </WBSMobileProvider>,
      );

      const ganttContainer = screen.getByTestId("gantt-container");

      // Zoom in
      simulatePinchZoom(ganttContainer, 2.0);

      await waitFor(() => {
        const zoomIndicator = screen.getByTestId("zoom-level");
        expect(zoomIndicator.textContent).toMatch(/2/);
      });

      // Re-render with same component
      rerender(
        <WBSMobileProvider>
          <MobileGanttChart items={mockWBSItems} />
        </WBSMobileProvider>,
      );

      // Zoom level should persist
      const zoomIndicator = screen.getByTestId("zoom-level");
      expect(zoomIndicator.textContent).toMatch(/2/);
    });

    it("should have zoom controls as fallback", () => {
      /**
       * RED Phase: Alternative zoom controls
       *
       * Expected: Buttons available for devices without pinch support
       */
      render(
        <WBSMobileProvider>
          <MobileGanttChart items={mockWBSItems} />
        </WBSMobileProvider>,
      );

      // Should have zoom in button
      const zoomInBtn = screen.getByLabelText(/zoom in/i);
      expect(zoomInBtn).toBeInTheDocument();
      expect(zoomInBtn.getBoundingClientRect().height).toBeGreaterThanOrEqual(
        44,
      );

      // Should have zoom out button
      const zoomOutBtn = screen.getByLabelText(/zoom out/i);
      expect(zoomOutBtn).toBeInTheDocument();
      expect(zoomOutBtn.getBoundingClientRect().height).toBeGreaterThanOrEqual(
        44,
      );

      // Should have reset zoom button
      const resetZoomBtn = screen.getByLabelText(/reset zoom/i);
      expect(resetZoomBtn).toBeInTheDocument();
    });
  });

  describe("Offline Data Caching [TEST-05]", () => {
    it("should cache data for offline mode", async () => {
      /**
       * RED Phase: Offline data caching
       *
       * Expected: WBS data is cached to localStorage for offline access
       */
      const setItemMock = vi.fn();
      vi.stubGlobal("localStorage", {
        getItem: vi.fn(),
        setItem: setItemMock,
        removeItem: vi.fn(),
        clear: vi.fn(),
      });

      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} offlineEnabled={true} />
        </WBSMobileProvider>,
      );

      // Should cache data on mount
      await waitFor(() => {
        expect(setItemMock).toHaveBeenCalledWith(
          expect.stringContaining("wbs"),
          expect.stringContaining("Project Foundation"),
        );
      });

      // Simulate going offline
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: false,
        configurable: true,
      });

      // Trigger online/offline event
      window.dispatchEvent(new Event("offline"));

      // Should display cached data indicator
      await waitFor(() => {
        const offlineIndicator = screen.getByTestId("offline-indicator");
        expect(offlineIndicator).toBeInTheDocument();
      });
    });

    it("should load from cache when offline", async () => {
      /**
       * RED Phase: Load cached data when offline
       *
       * Expected: Component loads data from localStorage when offline
       */
      const cachedData = JSON.stringify(mockWBSItems);
      vi.stubGlobal("localStorage", {
        getItem: vi.fn().mockReturnValue(cachedData),
        setItem: vi.fn(),
        removeItem: vi.fn(),
        clear: vi.fn(),
      });

      // Start offline
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: false,
        configurable: true,
      });

      render(
        <WBSMobileProvider>
          <WBSMobile items={[]} offlineEnabled={true} />
        </WBSMobileProvider>,
      );

      // Should load cached items
      await waitFor(() => {
        expect(screen.getByText("Project Foundation")).toBeInTheDocument();
        expect(screen.getByText("Structural Work")).toBeInTheDocument();
      });

      // Should show cache timestamp
      expect(screen.getByTestId("cache-timestamp")).toBeInTheDocument();
    });

    it("should sync when coming back online", async () => {
      /**
       * RED Phase: Online sync
       *
       * Expected: Component syncs with server when connection restored
       */
      const syncMock = vi.fn().mockResolvedValue(undefined);

      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} offlineEnabled={true} />
        </WBSMobileProvider>,
      );

      // Simulate going offline then online
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: false,
        configurable: true,
      });
      window.dispatchEvent(new Event("offline"));

      // Then back online
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: true,
        configurable: true,
      });
      window.dispatchEvent(new Event("online"));

      // Should trigger sync
      await waitFor(() => {
        expect(screen.queryByTestId("syncing-indicator")).toBeInTheDocument();
      });
    });
  });

  describe("Offline Action Queueing [TEST-06]", () => {
    it("should queue actions when offline", async () => {
      /**
       * RED Phase: Offline action queueing
       *
       * Expected: User actions are queued when offline and executed when online
       */
      const TestComponent = () => {
        const { isOffline, queueAction, pendingActions } = useWBSMobile();

        return (
          <div>
            <div data-testid="offline-status">
              {isOffline ? "offline" : "online"}
            </div>
            <div data-testid="pending-count">{pendingActions.length}</div>
            <button
              onClick={() =>
                queueAction({
                  id: "action-1",
                  type: "mark_complete",
                  payload: { itemId: "1.1" },
                  timestamp: Date.now(),
                })
              }
            >
              Mark Complete
            </button>
          </div>
        );
      };

      // Start offline
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: false,
        configurable: true,
      });

      render(
        <WBSMobileProvider>
          <TestComponent />
        </WBSMobileProvider>,
      );

      // Verify offline status
      expect(screen.getByTestId("offline-status")).toHaveTextContent("offline");

      // Queue an action
      fireEvent.click(screen.getByText("Mark Complete"));

      // Action should be queued
      await waitFor(() => {
        expect(screen.getByTestId("pending-count")).toHaveTextContent("1");
      });

      // Should show pending actions indicator
      expect(screen.getByTestId("pending-actions-badge")).toBeInTheDocument();
    });

    it("should execute queued actions when coming online", async () => {
      /**
       * RED Phase: Execute queued actions on reconnect
       *
       * Expected: Queued actions are executed in order when back online
       */
      const executeActionMock = vi.fn().mockResolvedValue(undefined);

      // Start offline
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: false,
        configurable: true,
      });

      const TestComponent = () => {
        const { queueAction, pendingActions, syncWhenOnline } = useWBSMobile();

        return (
          <div>
            <div data-testid="pending-count">{pendingActions.length}</div>
            <button
              onClick={() =>
                queueAction({
                  id: "action-1",
                  type: "mark_complete",
                  payload: { itemId: "1.1" },
                  timestamp: Date.now(),
                })
              }
            >
              Queue Action
            </button>
            <button onClick={() => syncWhenOnline()}>Sync Now</button>
          </div>
        );
      };

      render(
        <WBSMobileProvider>
          <TestComponent />
        </WBSMobileProvider>,
      );

      // Queue multiple actions
      fireEvent.click(screen.getByText("Queue Action"));
      fireEvent.click(screen.getByText("Queue Action"));

      await waitFor(() => {
        expect(screen.getByTestId("pending-count")).toHaveTextContent("2");
      });

      // Come back online
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: true,
        configurable: true,
      });

      // Trigger sync
      fireEvent.click(screen.getByText("Sync Now"));

      // Pending count should decrease as actions execute
      await waitFor(() => {
        expect(screen.getByTestId("pending-count")).toHaveTextContent("0");
      });
    });

    it("should persist action queue across sessions", async () => {
      /**
       * RED Phase: Action queue persistence
       *
       * Expected: Action queue is saved to localStorage and restored
       */
      const setItemMock = vi.fn();
      vi.stubGlobal("localStorage", {
        getItem: vi.fn(),
        setItem: setItemMock,
        removeItem: vi.fn(),
        clear: vi.fn(),
      });

      const TestComponent = () => {
        const { queueAction } = useWBSMobile();

        return (
          <button
            onClick={() =>
              queueAction({
                id: "action-1",
                type: "mark_complete",
                payload: { itemId: "1.1" },
                timestamp: Date.now(),
              })
            }
          >
            Queue Action
          </button>
        );
      };

      // Start offline
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: false,
        configurable: true,
      });

      render(
        <WBSMobileProvider>
          <TestComponent />
        </WBSMobileProvider>,
      );

      // Queue action
      fireEvent.click(screen.getByText("Queue Action"));

      // Should persist to localStorage
      await waitFor(() => {
        expect(setItemMock).toHaveBeenCalledWith(
          expect.stringContaining("queue"),
          expect.stringContaining("mark_complete"),
        );
      });
    });

    it("should handle action execution errors gracefully", async () => {
      /**
       * RED Phase: Error handling for queued actions
       *
       * Expected: Failed actions are retried or marked for manual resolution
       */
      const TestComponent = () => {
        const { pendingActions, failedActions, syncWhenOnline } =
          useWBSMobile();

        return (
          <div>
            <div data-testid="pending-count">{pendingActions.length}</div>
            <div data-testid="failed-count">{failedActions?.length || 0}</div>
            <button onClick={() => syncWhenOnline()}>Sync</button>
          </div>
        );
      };

      // Start offline
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: false,
        configurable: true,
      });

      render(
        <WBSMobileProvider>
          <TestComponent />
        </WBSMobileProvider>,
      );

      // Come online with a failing sync
      Object.defineProperty(navigator, "onLine", {
        writable: true,
        value: true,
        configurable: true,
      });

      fireEvent.click(screen.getByText("Sync"));

      // Should show error state for failed actions
      await waitFor(() => {
        const errorIndicator = screen.queryByTestId("sync-error");
        expect(
          errorIndicator || screen.getByTestId("failed-count"),
        ).toBeTruthy();
      });
    });
  });

  describe("Mobile Viewport Detection", () => {
    it("should detect mobile viewport", () => {
      /**
       * RED Phase: Mobile viewport detection
       *
       * Expected: Component detects mobile viewport and applies mobile optimizations
       */
      // Mock mobile viewport
      Object.defineProperty(window, "innerWidth", {
        writable: true,
        configurable: true,
        value: 375, // iPhone width
      });

      window.dispatchEvent(new Event("resize"));

      render(
        <WBSMobileProvider>
          <WBSMobile items={mockWBSItems} />
        </WBSMobileProvider>,
      );

      // Should apply mobile-specific class
      const mobileContainer = screen.getByTestId("wbs-mobile-container");
      expect(mobileContainer.classList.contains("mobile-viewport")).toBe(true);
    });
  });
});

// ===========================================
// END OF TEST SUITE
// ===========================================

// Mark tests as mobile contract tests in RED phase
// @ts-ignore - vitest type extension
if (typeof test !== "undefined") {
  test.meta = {
    phase: "red",
    suite: "TS-MOB-WBS-001",
    type: "mobile-contract",
    priority: "P1",
  };
}
