/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
import { describe, expect, it } from "vitest";
import {
  mapClausesToHighlights,
  type EvidenceClauseAnchor,
} from "@/components/features/evidence/highlight-mapper";

describe("S3-01 RED - highlight mapper", () => {
  it("[S3-01-RED-UNIT-03] maps clause anchors to deterministic page/index highlights", () => {
    const anchors: EvidenceClauseAnchor[] = [
      { clauseId: "c1", page: 3, startOffset: 11, endOffset: 20, severity: "high" },
      { clauseId: "c2", page: 1, startOffset: 1, endOffset: 9, severity: "critical" },
    ];

    const highlights = mapClausesToHighlights(anchors);

    expect(highlights.map((h) => h.clauseId)).toEqual(["c2", "c1"]);
    expect(highlights[0]).toMatchObject({
      page: 1,
      startOffset: 1,
      endOffset: 9,
    });
  });

  it("[S3-01-RED-UNIT-06] ignores malformed anchors without throwing", () => {
    const malformed = [
      { clauseId: "bad-1", page: 0, startOffset: 40, endOffset: 10 },
      { clauseId: "bad-2", page: -1, startOffset: 0, endOffset: 1 },
      { clauseId: "ok-1", page: 2, startOffset: 3, endOffset: 5, severity: "low" },
    ] as EvidenceClauseAnchor[];

    expect(() => mapClausesToHighlights(malformed)).not.toThrow();
    expect(mapClausesToHighlights(malformed)).toHaveLength(1);
  });
});
