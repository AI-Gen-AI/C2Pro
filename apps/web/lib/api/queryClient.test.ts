/**
 * Test Suite ID: TS-FRT-MUT-ERR-001
 */
import { describe, expect, it, vi, beforeEach } from "vitest";
import { createQueryClient } from "./queryClient";

const showToastMock = vi.fn();

vi.mock("@/lib/ui/toast", () => ({
  showToast: (...args: unknown[]) => showToastMock(...args),
}));

describe("createQueryClient mutation error surface", () => {
  beforeEach(() => {
    showToastMock.mockReset();
  });

  it("shows a global toast with the backend detail when a mutation has no local error handler", async () => {
    const client = createQueryClient();
    const error = { response: { data: { detail: "Budget write failed" } } };
    const mutation = client.getMutationCache().build(client, {
      mutationFn: async () => {
        throw error;
      },
    });

    await expect(mutation.execute(undefined)).rejects.toBe(error);

    expect(showToastMock).toHaveBeenCalledWith("Budget write failed");
  });

  it("does not duplicate toasts when the mutation defines a local error handler", async () => {
    const client = createQueryClient();
    const error = new Error("Handled locally");
    const localOnError = vi.fn();
    const mutation = client.getMutationCache().build(client, {
      mutationFn: async () => {
        throw error;
      },
      onError: localOnError,
    });

    await expect(mutation.execute(undefined)).rejects.toBe(error);

    expect(localOnError).toHaveBeenCalled();
    expect(showToastMock).not.toHaveBeenCalled();
  });
});
