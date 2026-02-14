/**
 * Test Suite ID: S2-09
 * Roadmap Reference: S2-09 Document upload (drag-drop, PDF/XLSX/BC3, chunked)
 */
import { describe, expect, it } from "vitest";
import { planFileChunks } from "@/src/lib/uploads/chunking";

describe("S2-09 RED - chunk planner", () => {
  it("[S2-09-RED-04] creates exact chunk count and byte boundaries", () => {
    /** Roadmap: S2-09 */
    const plan = planFileChunks({
      fileName: "contract.pdf",
      fileSizeBytes: 10_485_761,
      chunkSizeBytes: 5_242_880,
    });

    expect(plan.totalChunks).toBe(3);
    expect(plan.chunks[0]).toMatchObject({ index: 0, start: 0, end: 5_242_879 });
    expect(plan.chunks[1]).toMatchObject({
      index: 1,
      start: 5_242_880,
      end: 10_485_759,
    });
    expect(plan.chunks[2]).toMatchObject({
      index: 2,
      start: 10_485_760,
      end: 10_485_760,
    });
  });

  it("[S2-09-RED-04b] rejects empty files explicitly", () => {
    /** Roadmap: S2-09 */
    expect(() =>
      planFileChunks({
        fileName: "empty.pdf",
        fileSizeBytes: 0,
        chunkSizeBytes: 5_242_880,
      }),
    ).toThrowError(/file size must be greater than 0/i);
  });
});

