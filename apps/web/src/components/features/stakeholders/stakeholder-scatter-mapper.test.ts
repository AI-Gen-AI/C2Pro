/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */
import { describe, expect, it } from "vitest";
import { mapStakeholdersToScatter } from "@/src/components/features/stakeholders/stakeholder-scatter-mapper";

describe("S3-07 RED - stakeholder scatter mapper", () => {
  it("[S3-07-RED-UNIT-03] maps power/interest to bounded chart coordinates", () => {
    const points = mapStakeholdersToScatter([
      { id: "s1", name: "Owner", power: 9, interest: 8, raci: "A" },
      { id: "s2", name: "GC", power: 2, interest: 3, raci: "R" },
    ]);

    expect(points).toHaveLength(2);
    for (const point of points) {
      expect(point.x).toBeGreaterThanOrEqual(0);
      expect(point.x).toBeLessThanOrEqual(100);
      expect(point.y).toBeGreaterThanOrEqual(0);
      expect(point.y).toBeLessThanOrEqual(100);
    }
  });

  it("[S3-07-RED-UNIT-04] includes RACI overlay groups for legend rendering", () => {
    const points = mapStakeholdersToScatter([
      { id: "s1", name: "Owner", power: 9, interest: 8, raci: "A" },
      { id: "s2", name: "Legal", power: 5, interest: 7, raci: "C" },
    ]);

    expect(points.find((p) => p.id === "s1")?.group).toBe("A");
    expect(points.find((p) => p.id === "s2")?.group).toBe("C");
  });
});
