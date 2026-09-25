/**
 * TS-UT-PJ01-CLASSIFY-001 — a green backend is not a usable journey.
 *
 * USABLE: every step passed and nothing was found.
 * TECHNICALLY_FUNCTIONAL: every step passed, but a non-blocking gap or violation was found
 * (e.g. Health reached by a typed URL in diagnostic mode).
 * FAIL: a step failed or a blocking finding exists.
 */
import { describe, expect, it } from "vitest";

import { classifyRun, type RunFinding } from "./classification";

const finding = (overrides: Partial<RunFinding>): RunFinding => ({
  kind: "gap",
  code: "G4_HEALTH_NOT_NAVIGABLE",
  step: "PJ01-S5",
  detail: "no Health tab",
  blocking: false,
  ...overrides,
});

describe("classifyRun", () => {
  it("is USABLE with passing steps and no findings", () => {
    expect(classifyRun({ failedSteps: 0, findings: [] })).toBe("USABLE");
  });

  it("is TECHNICALLY_FUNCTIONAL when only non-blocking findings exist", () => {
    expect(classifyRun({ failedSteps: 0, findings: [finding({})] })).toBe("TECHNICALLY_FUNCTIONAL");
  });

  it("is FAIL with a blocking finding", () => {
    expect(
      classifyRun({ failedSteps: 0, findings: [finding({ kind: "violation", code: "FALSE_SUCCESS", blocking: true })] }),
    ).toBe("FAIL");
  });

  it("is FAIL when any step failed", () => {
    expect(classifyRun({ failedSteps: 1, findings: [] })).toBe("FAIL");
  });
});
