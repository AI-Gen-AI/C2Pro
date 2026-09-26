import { describe, expect, it } from "vitest";

import { normalizeGeneratedApiUrl } from "./client";

// apiClient.baseURL is "/api" (config/env default), so the normalized path must NOT re-carry an
// "/api" prefix — otherwise axios produces "/api/api/...". This is the exact bug from the
// coherence-scoped generated client ("/api/coherence/...").
const cases: Array<[string, string]> = [
  ["/api/coherence/dashboard/p1", "/coherence/dashboard/p1"], // the regression
  ["/api/v1/coherence/dashboard/p1", "/coherence/dashboard/p1"],
  ["/api/v1/projects/p1", "/projects/p1"],
  ["/api/projects/p1", "/projects/p1"],
  ["/api/alerts/projects/p1", "/alerts/projects/p1"],
  ["/api", "/"],
  ["/api/v1", "/"],
  ["/apixyz/thing", "/apixyz/thing"], // must NOT be wrongly stripped (no "/" or end after api)
];

describe("normalizeGeneratedApiUrl — single /api owner", () => {
  it.each(cases)("normalizes %s -> %s", (input, expected) => {
    expect(normalizeGeneratedApiUrl(input)).toBe(expected);
  });

  it("no covered canonical path can produce /api/api/ after baseURL join", () => {
    for (const [input] of cases) {
      const finalUrl = `/api${normalizeGeneratedApiUrl(input)}`; // axios baseURL + url
      expect(finalUrl).not.toMatch(/\/api\/api(\/|$)/);
    }
  });

  it("passes non-string urls through unchanged", () => {
    expect(normalizeGeneratedApiUrl(undefined)).toBeUndefined();
  });
});
