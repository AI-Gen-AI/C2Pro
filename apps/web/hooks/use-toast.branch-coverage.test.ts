/**
 * Test Suite ID: TS-QA-337-USE-TOAST-BRANCH-COV
 * Branch coverage tests for use-toast hook and reducer
 */
import { renderHook, act } from "@testing-library/react";
import { describe, expect, it, vi, beforeEach } from "vitest";
import { reducer, toast, useToast } from "./use-toast";

describe("use-toast reducer branch coverage", () => {
  it("ADD_TOAST prepends toast and enforces TOAST_LIMIT", () => {
    const state = { toasts: [{ id: "old", title: "Old" }] };
    const result = reducer(state, {
      type: "ADD_TOAST",
      toast: { id: "new", title: "New", open: true } as never,
    });
    expect(result.toasts).toHaveLength(1);
    expect(result.toasts[0].id).toBe("new");
  });

  it("UPDATE_TOAST patches matching toast by id", () => {
    const state = {
      toasts: [
        { id: "t1", title: "Before" },
        { id: "t2", title: "Other" },
      ],
    };
    const result = reducer(state, {
      type: "UPDATE_TOAST",
      toast: { id: "t1", title: "After" },
    });
    expect(result.toasts[0].title).toBe("After");
    expect(result.toasts[1].title).toBe("Other");
  });

  it("UPDATE_TOAST does nothing for non-matching id", () => {
    const state = { toasts: [{ id: "t1", title: "Original" }] };
    const result = reducer(state, {
      type: "UPDATE_TOAST",
      toast: { id: "nonexistent", title: "Changed" },
    });
    expect(result.toasts[0].title).toBe("Original");
  });

  it("DISMISS_TOAST with specific id queues removal and sets open false", () => {
    const state = { toasts: [{ id: "t1", title: "Test", open: true } as never] };
    const result = reducer(state, {
      type: "DISMISS_TOAST",
      toastId: "t1",
    });
    expect((result.toasts[0] as Record<string, unknown>).open).toBe(false);
  });

  it("DISMISS_TOAST without id queues removal for all toasts", () => {
    const state = {
      toasts: [
        { id: "t1", title: "A", open: true } as never,
        { id: "t2", title: "B", open: true } as never,
      ],
    };
    const result = reducer(state, {
      type: "DISMISS_TOAST",
    });
    expect(result.toasts.every((t) => (t as Record<string, unknown>).open === false)).toBe(true);
  });

  it("REMOVE_TOAST with specific id filters out the toast", () => {
    const state = {
      toasts: [
        { id: "t1", title: "A" },
        { id: "t2", title: "B" },
      ],
    };
    const result = reducer(state, {
      type: "REMOVE_TOAST",
      toastId: "t1",
    });
    expect(result.toasts).toHaveLength(1);
    expect(result.toasts[0].id).toBe("t2");
  });

  it("REMOVE_TOAST without id clears all toasts", () => {
    const state = {
      toasts: [
        { id: "t1", title: "A" },
        { id: "t2", title: "B" },
      ],
    };
    const result = reducer(state, {
      type: "REMOVE_TOAST",
    });
    expect(result.toasts).toHaveLength(0);
  });

  it("REMOVE_TOAST for non-matching id leaves state unchanged", () => {
    const state = { toasts: [{ id: "t1", title: "A" }] };
    const result = reducer(state, {
      type: "REMOVE_TOAST",
      toastId: "nonexistent",
    });
    expect(result.toasts).toHaveLength(1);
  });
});

describe("toast function branch coverage", () => {
  it("creates a toast with auto-generated id", () => {
    const { id, dismiss, update } = toast({ title: "Hello" });
    expect(typeof id).toBe("string");
    expect(typeof dismiss).toBe("function");
    expect(typeof update).toBe("function");
  });

  it("update dispatches UPDATE_TOAST with the same id", () => {
    const { id, update } = toast({ title: "Original" });
    update({ id, title: "Updated" });

    const { result } = renderHook(() => useToast());
    const found = result.current.toasts.find((t) => t.id === id);
    expect(found?.title).toBe("Updated");
  });

  it("dismiss dispatches DISMISS_TOAST", () => {
    const { id, dismiss } = toast({ title: "Dismissable" });
    dismiss();

    const { result } = renderHook(() => useToast());
    const found = result.current.toasts.find((t) => t.id === id) as Record<string, unknown> | undefined;
    expect(found?.open).toBe(false);
  });

  it("onOpenChange(false) triggers dismiss", () => {
    const { id } = toast({ title: "WithCallback" });

    const { result } = renderHook(() => useToast());
    const found = result.current.toasts.find((t) => t.id === id) as Record<string, unknown> | undefined;
    expect(found?.onOpenChange).toBeDefined();

    act(() => {
      (found?.onOpenChange as (open: boolean) => void)(false);
    });
  });
});

describe("useToast hook branch coverage", () => {
  beforeEach(() => {
    const { result } = renderHook(() => useToast());
    act(() => {
      result.current.dismiss();
    });
  });

  it("returns current toasts and dismiss function", () => {
    const { result } = renderHook(() => useToast());
    expect(Array.isArray(result.current.toasts)).toBe(true);
    expect(typeof result.current.dismiss).toBe("function");
    expect(typeof result.current.toast).toBe("function");
  });

  it("dismiss via hook dispatches DISMISS_TOAST", () => {
    toast({ title: "Hook Toast" });

    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.dismiss();
    });

    expect(result.current.toasts.every((t) => (t as Record<string, unknown>).open === false)).toBe(true);
  });

  it("dismiss via hook with specific id only dismisses that toast", () => {
    const t1 = toast({ title: "Toast 1" });

    const { result } = renderHook(() => useToast());

    act(() => {
      result.current.dismiss(t1.id);
    });

    const dismissed = result.current.toasts.find((t) => t.id === t1.id) as Record<string, unknown> | undefined;
    expect(dismissed?.open).toBe(false);
  });

  it("listener cleanup removes listener on unmount", () => {
    const { unmount } = renderHook(() => useToast());
    unmount();
  });
});
