import { describe, expect, it, vi } from "vitest";

describe("useAppModeStore", () => {
  it("defaults to demo when NEXT_PUBLIC_APP_MODE=demo", async () => {
    vi.resetModules();
    process.env.NEXT_PUBLIC_APP_MODE = "demo";
    const { useAppModeStore } = await import("./app-mode");

    const state = useAppModeStore.getState();
    expect(state.mode).toBe("demo");
  });

  it("allows switching modes", async () => {
    vi.resetModules();
    delete process.env.NEXT_PUBLIC_APP_MODE;
    const { useAppModeStore } = await import("./app-mode");

    useAppModeStore.getState().setMode("demo");
    expect(useAppModeStore.getState().mode).toBe("demo");

    useAppModeStore.getState().setMode("prod");
    expect(useAppModeStore.getState().mode).toBe("prod");
  });
});
