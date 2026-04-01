import { act, renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { reducer, toast, useToast } from "../../hooks/use-toast";

describe("use-toast store", () => {
  it("enforces the single-toast limit in the reducer", () => {
    const state = {
      toasts: [{ id: "existing", title: "Existing" }],
    };

    const next = reducer(state, {
      type: "ADD_TOAST",
      toast: { id: "new", title: "New toast" },
    });

    expect(next.toasts).toEqual([{ id: "new", title: "New toast" }]);
  });

  it("marks a toast as closed when dismissed", () => {
    const state = {
      toasts: [{ id: "toast-1", title: "Dismiss me", open: true }],
    };

    const next = reducer(state, {
      type: "DISMISS_TOAST",
      toastId: "toast-1",
    });

    expect(next.toasts).toEqual([
      { id: "toast-1", title: "Dismiss me", open: false },
    ]);
  });

  it("exposes toast updates through the hook subscription", async () => {
    const { result } = renderHook(() => useToast());

    act(() => {
      toast({
        title: "Saved",
        description: "Profile updated",
      });
    });

    await waitFor(() =>
      expect(result.current.toasts[0]).toMatchObject({
        title: "Saved",
        description: "Profile updated",
        open: true,
      }),
    );

    act(() => {
      result.current.dismiss(result.current.toasts[0]?.id);
    });

    await waitFor(() =>
      expect(result.current.toasts[0]).toMatchObject({
        title: "Saved",
        open: false,
      }),
    );
  });
});
