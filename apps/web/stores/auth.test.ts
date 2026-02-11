import { describe, expect, afterEach, it } from "vitest";
import { useAuthStore } from "./auth";

describe("useAuthStore", () => {
  afterEach(() => {
    useAuthStore.setState({ token: null, tenantId: null });
  });

  it("defaults to null token and tenant", () => {
    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.tenantId).toBeNull();
  });

  it("updates token and tenant via setAuth and clears state", () => {
    const state = useAuthStore.getState();
    state.setAuth({ token: "token-123", tenantId: "tenant-1" });

    const updated = useAuthStore.getState();
    expect(updated.token).toBe("token-123");
    expect(updated.tenantId).toBe("tenant-1");

    updated.clear();
    const cleared = useAuthStore.getState();
    expect(cleared.token).toBeNull();
    expect(cleared.tenantId).toBeNull();
  });
});
