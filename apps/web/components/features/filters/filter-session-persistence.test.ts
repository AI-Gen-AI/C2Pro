/**
 * Test Suite ID: S3-10
 * Roadmap Reference: S3-10 sessionStorage filter persistence
 */
import { describe, expect, it } from "vitest";
import {
  FILTER_STORAGE_VERSION,
  hydrateFilters,
  makeFilterStorageKey,
  persistFilters,
} from "@/components/features/filters/filter-session-persistence";

describe("S3-10 RED - filter session persistence", () => {
  it("[S3-10-RED-UNIT-01] persists deterministic filter payload in sessionStorage", () => {
    persistFilters("filters:alerts:proj_demo_001", {
      severity: ["critical"],
      owner: "legal",
    });

    const raw = sessionStorage.getItem("filters:alerts:proj_demo_001");
    expect(raw).toContain(`\"version\":\"${FILTER_STORAGE_VERSION}\"`);
    expect(raw).toContain("\"severity\":[\"critical\"]");
    expect(raw).toContain("\"owner\":\"legal\"");
  });

  it("[S3-10-RED-UNIT-02] hydrates valid filters and ignores malformed storage safely", () => {
    sessionStorage.setItem(
      "filters:alerts:proj_demo_001",
      JSON.stringify({
        version: FILTER_STORAGE_VERSION,
        filters: { severity: ["high"], owner: "risk" },
      }),
    );

    const hydrated = hydrateFilters("filters:alerts:proj_demo_001", {
      severity: [],
      owner: "",
    });
    expect(hydrated).toEqual({ severity: ["high"], owner: "risk" });

    sessionStorage.setItem("filters:alerts:proj_demo_001", "{bad json");
    const fallback = hydrateFilters("filters:alerts:proj_demo_001", {
      severity: [],
      owner: "",
    });
    expect(fallback).toEqual({ severity: [], owner: "" });
  });

  it("[S3-10-RED-UNIT-03] composes storage key using route and project scope", () => {
    expect(makeFilterStorageKey("alerts", "proj_demo_001")).toBe(
      "filters:alerts:proj_demo_001",
    );
    expect(makeFilterStorageKey("evidence", "proj_demo_001")).toBe(
      "filters:evidence:proj_demo_001",
    );
  });

  it("[S3-10-RED-UNIT-04] migrates legacy persisted schema to current model", () => {
    sessionStorage.setItem(
      "filters:alerts:proj_demo_001",
      JSON.stringify({
        version: "legacy-v1",
        severity: "critical",
        owner_name: "legal",
      }),
    );

    const migrated = hydrateFilters("filters:alerts:proj_demo_001", {
      severity: [],
      owner: "",
    });

    expect(migrated).toEqual({ severity: ["critical"], owner: "legal" });
  });

  it("[S3-10-RED-UNIT-06] persists only to sessionStorage (not localStorage)", () => {
    persistFilters("filters:alerts:proj_demo_001", {
      severity: ["medium"],
      owner: "qa",
    });

    expect(sessionStorage.getItem("filters:alerts:proj_demo_001")).toBeTruthy();
    expect(localStorage.getItem("filters:alerts:proj_demo_001")).toBeNull();
  });
});
