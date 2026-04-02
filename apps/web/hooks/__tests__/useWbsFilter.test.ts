/**
 * Test Suite: TS-UAD-WBS-FILTER-001
 * Name: WBS Filter by Status Tests
 * Type: Hook Test (React Hook)
 * Phase: RED
 * Owner: @frontend-tdd
 *
 * Tests for useWbsFilter hook - filters WBS items by completion status
 * with URL query param sync and localStorage persistence.
 */

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWbsFilter } from "@/hooks/useWbsFilter";

// Mock WBS items for testing
const mockWBSItems = [
  { id: "1", code: "1", name: "Project Root", completion: 0 },
  { id: "2", code: "1.1", name: "Planning Phase", completion: 100 },
  { id: "3", code: "1.2", name: "Design Phase", completion: 50 },
  { id: "4", code: "1.3", name: "Development", completion: 25 },
  { id: "5", code: "1.4", name: "Testing", completion: 0 },
  { id: "6", code: "1.5", name: "Deployment", completion: 100 },
];

describe("useWbsFilter (TS-UAD-WBS-FILTER-001)", () => {
  let mockLocalStorage: Storage;

  beforeEach(() => {
    window.history.replaceState({}, "", "/projects/123/wbs");

    // Mock localStorage
    const store: Record<string, string> = {};
    mockLocalStorage = {
      getItem: vi.fn((key: string) => store[key] || null),
      setItem: vi.fn((key: string, value: string) => {
        store[key] = value;
      }),
      removeItem: vi.fn((key: string) => {
        delete store[key];
      }),
      clear: vi.fn(() => {
        Object.keys(store).forEach((key) => delete store[key]);
      }),
      length: 0,
      key: vi.fn(() => null),
    } as unknown as Storage;

    Object.defineProperty(window, "localStorage", {
      value: mockLocalStorage,
      writable: true,
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
    window.history.replaceState({}, "", "/projects/123/wbs");
  });

  describe("Filter by Completion Status", () => {
    it("should filter not-started items (completion = 0%)", () => {
      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      act(() => {
        result.current.setFilter("not-started");
      });

      expect(result.current.filter).toBe("not-started");
      expect(result.current.filteredItems).toHaveLength(2);
      expect(
        result.current.filteredItems.every((item) => item.completion === 0),
      ).toBe(true);
      expect(result.current.filteredItems.map((i) => i.name)).toEqual([
        "Project Root",
        "Testing",
      ]);
    });

    it("should filter in-progress items (completion = 1-99%)", () => {
      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      act(() => {
        result.current.setFilter("in-progress");
      });

      expect(result.current.filter).toBe("in-progress");
      expect(result.current.filteredItems).toHaveLength(2);
      expect(
        result.current.filteredItems.every(
          (item) => item.completion > 0 && item.completion < 100,
        ),
      ).toBe(true);
      expect(result.current.filteredItems.map((i) => i.name)).toEqual([
        "Design Phase",
        "Development",
      ]);
    });

    it("should filter complete items (completion = 100%)", () => {
      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      act(() => {
        result.current.setFilter("complete");
      });

      expect(result.current.filter).toBe("complete");
      expect(result.current.filteredItems).toHaveLength(2);
      expect(
        result.current.filteredItems.every((item) => item.completion === 100),
      ).toBe(true);
      expect(result.current.filteredItems.map((i) => i.name)).toEqual([
        "Planning Phase",
        "Deployment",
      ]);
    });
  });

  describe("URL Query Parameter Synchronization", () => {
    it("should update URL query params when filter changes", () => {
      window.history.replaceState({}, "", "/projects/123/wbs");

      const replaceStateSpy = vi.spyOn(window.history, "replaceState");

      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      act(() => {
        result.current.setFilter("in-progress");
      });

      expect(replaceStateSpy).toHaveBeenCalledWith(
        expect.any(Object),
        "",
        expect.stringContaining("filter=in-progress"),
      );
    });

    it("should read filter from URL on mount", () => {
      window.history.replaceState(
        {},
        "",
        "/projects/123/wbs?filter=complete",
      );

      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      expect(result.current.filter).toBe("complete");
      expect(result.current.filteredItems).toHaveLength(2);
      expect(
        result.current.filteredItems.every((item) => item.completion === 100),
      ).toBe(true);
    });
  });

  describe("localStorage Persistence", () => {
    it("should persist filter in localStorage", () => {
      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      act(() => {
        result.current.setFilter("not-started");
      });

      expect(mockLocalStorage.setItem).toHaveBeenCalledWith(
        "wbs-filter",
        "not-started",
      );
    });

    it("should restore filter from localStorage on mount when no URL param", () => {
      // Pre-populate localStorage
      (mockLocalStorage.getItem as ReturnType<typeof vi.fn>).mockReturnValue(
        "complete",
      );
      window.history.replaceState({}, "", "/projects/123/wbs");

      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      expect(mockLocalStorage.getItem).toHaveBeenCalledWith("wbs-filter");
      expect(result.current.filter).toBe("complete");
    });
  });

  describe("Filter Operations", () => {
    it("should combine multiple filters", () => {
      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      // Set first filter
      act(() => {
        result.current.setFilter("in-progress");
      });

      expect(result.current.filteredItems).toHaveLength(2);

      // Change to another filter
      act(() => {
        result.current.setFilter("complete");
      });

      expect(result.current.filteredItems).toHaveLength(2);
      expect(
        result.current.filteredItems.every((item) => item.completion === 100),
      ).toBe(true);
    });

    it("should clear filter and show all items", () => {
      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      // Set a filter first
      act(() => {
        result.current.setFilter("complete");
      });

      expect(result.current.filter).toBe("complete");
      expect(result.current.filteredItems).toHaveLength(2);

      // Clear the filter
      act(() => {
        result.current.clearFilter();
      });

      expect(result.current.filter).toBeNull();
      expect(result.current.filteredItems).toHaveLength(mockWBSItems.length);
    });

    it("should return all items when no filter is set", () => {
      const { result } = renderHook(() => useWbsFilter(mockWBSItems));

      expect(result.current.filter).toBeNull();
      expect(result.current.filteredItems).toEqual(mockWBSItems);
    });

    it("should handle empty items array", () => {
      const { result } = renderHook(() => useWbsFilter([]));

      act(() => {
        result.current.setFilter("complete");
      });

      expect(result.current.filteredItems).toEqual([]);
    });
  });
});
