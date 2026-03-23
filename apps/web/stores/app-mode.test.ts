import { describe, expect, it, vi } from "vitest";

describe("useAppModeStore", () => {
  it("defaults to prod even when NEXT_PUBLIC_APP_MODE=demo", async () => {
    vi.resetModules();
    process.env.NEXT_PUBLIC_APP_MODE = "demo";
    const { useAppModeStore } = await import("./app-mode");

    const state = useAppModeStore.getState();
    expect(state.mode).toBe("prod");
    expect(state.demoEnvironmentEnabled).toBe(true);
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

  it("selectIsDemoMode returns true only in demo mode", async () => {
    vi.resetModules();
    delete process.env.NEXT_PUBLIC_APP_MODE;
    const { useAppModeStore, selectIsDemoMode } = await import("./app-mode");

    useAppModeStore.getState().setMode("prod");
    expect(selectIsDemoMode(useAppModeStore.getState())).toBe(false);

    useAppModeStore.getState().setMode("demo");
    expect(selectIsDemoMode(useAppModeStore.getState())).toBe(true);
  });

  it("activates demo mode only for explicit /demo routes when demo env is enabled", async () => {
    vi.resetModules();
    process.env.NEXT_PUBLIC_APP_MODE = "demo";
    const { useAppModeStore } = await import("./app-mode");

    useAppModeStore.getState().syncWithPathname("/projects");
    expect(useAppModeStore.getState().mode).toBe("prod");

    useAppModeStore.getState().syncWithPathname("/demo/projects");
    expect(useAppModeStore.getState().mode).toBe("demo");
  });

  it("never activates demo mode for /demo routes when demo env is disabled", async () => {
    vi.resetModules();
    delete process.env.NEXT_PUBLIC_APP_MODE;
    const { useAppModeStore } = await import("./app-mode");

    useAppModeStore.getState().syncWithPathname("/demo/projects");
    expect(useAppModeStore.getState().mode).toBe("prod");
  });

  it("isExplicitDemoRoute only matches the dedicated demo workspace", async () => {
    vi.resetModules();
    const { isExplicitDemoRoute } = await import("./app-mode");

    expect(isExplicitDemoRoute("/demo")).toBe(true);
    expect(isExplicitDemoRoute("/demo/projects")).toBe(true);
    expect(isExplicitDemoRoute("/projects")).toBe(false);
    expect(isExplicitDemoRoute("/dashboard")).toBe(false);
  });
});
