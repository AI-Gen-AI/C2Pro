/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */
import { describe, expect, it } from "vitest";
import { resolveRaciGridViolations } from "@/src/components/features/stakeholders/raci-grid-rules";

describe("S3-07 RED - RACI grid rules", () => {
  it("[S3-07-RED-UNIT-05] flags rows with multiple Accountable assignments", () => {
    const violations = resolveRaciGridViolations([
      {
        workItemId: "w1",
        assignments: [
          { stakeholderId: "s1", role: "A" },
          { stakeholderId: "s2", role: "A" },
        ],
      },
    ]);

    expect(violations).toEqual([
      {
        workItemId: "w1",
        code: "MULTIPLE_ACCOUNTABLE",
      },
    ]);
  });
});
