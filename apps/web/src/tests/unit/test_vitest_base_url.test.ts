import { describe, it, expect } from "vitest";

describe("Vitest Environment Base URL", () => {
  it("should be able to parse relative URLs in fetch", () => {
    // This will fail if no base URL is configured in the test environment
    // and the test runs in a Node-like environment without window.location
    try {
      const url = new URL("/api/v1/health", window.location.origin);
      expect(url.toString()).toContain("/api/v1/health");
    } catch (e) {
      throw new Error(`Failed to parse relative URL: ${e}`);
    }
  });

  it("global fetch should handle relative paths", async () => {
    // This often fails in jsdom/node if not configured
    try {
      const response = await fetch("/api/v1/health");
      expect(response).toBeDefined();
    } catch (e) {
      // In RED phase, we expect this to throw "TypeError: Failed to parse URL from /api/v1/health"
      // or similar if base URL is missing.
      throw e;
    }
  });
});
