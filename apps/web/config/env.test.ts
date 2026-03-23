import { afterEach, describe, expect, it, vi } from "vitest";

describe("web API environment config", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
  });

  it("derives backend origin from NEXT_PUBLIC_API_URL", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "https://api.example.com/api/v1");

    const { env } = await import("./env");

    expect(env.API_BASE_URL).toBe("https://api.example.com/api/v1");
    expect(env.BACKEND_ORIGIN).toBe("https://api.example.com");
    expect(env.COHERENCE_BASE_URL).toBe("/coherence");
  });

  it("keeps relative API base urls aligned for browser-side direct calls", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_URL", "/api/v1");

    const { env } = await import("./env");

    expect(env.API_BASE_URL).toBe("/api/v1");
    expect(env.BACKEND_ORIGIN).toBe("");
    expect(env.COHERENCE_BASE_URL).toBe("/coherence");
  });
});
