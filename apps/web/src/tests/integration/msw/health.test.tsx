import { describe, expect, it } from "vitest";

describe("MSW integration", () => {
  it("responds to health checks in demo mode", async () => {
    const response = await fetch("/api/v1/health");
    const data = await response.json();

    expect(response.ok).toBe(true);
    expect(data).toEqual({ status: "ok" });
  });
});
