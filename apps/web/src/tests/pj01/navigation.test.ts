/**
 * TS-UT-PJ01-NAV-001 — PJ-01 reaches Health and Evidence through visible navigation.
 *
 * The Health tab is being added on separate branches, pointing at either
 * `/projects/{id}/health` or `/projects/{id}/analysis`. The harness must accept either and
 * report the gap (never silently type a URL) when neither exists.
 */
import { describe, expect, it } from "vitest";

import { findProjectTab, HEALTH_ROUTE_PATTERN } from "./navigation";

const PROJECT = "11111111-2222-4333-8444-555555555555";

describe("findProjectTab", () => {
  const baseTabs = [
    { name: "Overview", href: `/projects/${PROJECT}` },
    { name: "Documents", href: `/projects/${PROJECT}/documents` },
    { name: "Evidence", href: `/projects/${PROJECT}/evidence` },
  ];

  it("finds a Health tab that points at the dedicated health route", () => {
    const tabs = [...baseTabs, { name: "Health", href: `/projects/${PROJECT}/health` }];
    expect(findProjectTab(tabs, PROJECT, "health")).toEqual({ name: "Health", href: `/projects/${PROJECT}/health` });
  });

  it("finds a Health tab that points at the analysis page", () => {
    const tabs = [...baseTabs, { name: "Health", href: `/projects/${PROJECT}/analysis` }];
    expect(findProjectTab(tabs, PROJECT, "health")?.href).toBe(`/projects/${PROJECT}/analysis`);
  });

  it("returns null when Health is not navigable (PJ-01 gap G4)", () => {
    expect(findProjectTab(baseTabs, PROJECT, "health")).toBeNull();
  });

  it("does not accept a Health-looking link for another project", () => {
    const tabs = [...baseTabs, { name: "Health", href: "/projects/99999999-2222-4333-8444-555555555555/health" }];
    expect(findProjectTab(tabs, PROJECT, "health")).toBeNull();
  });

  it("finds the Evidence tab", () => {
    expect(findProjectTab(baseTabs, PROJECT, "evidence")?.href).toBe(`/projects/${PROJECT}/evidence`);
  });

  it("recognises both health destinations", () => {
    expect(HEALTH_ROUTE_PATTERN.test(`/projects/${PROJECT}/health`)).toBe(true);
    expect(HEALTH_ROUTE_PATTERN.test(`/projects/${PROJECT}/analysis`)).toBe(true);
    expect(HEALTH_ROUTE_PATTERN.test(`/projects/${PROJECT}/documents`)).toBe(false);
  });
});
