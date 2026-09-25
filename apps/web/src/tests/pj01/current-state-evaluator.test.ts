/**
 * TS-UT-PJ01-CURRENT-STATE-001 — PJ-01 step I judge: Current State after revision B.
 */
import { describe, expect, it } from "vitest";

import {
  evaluateCurrentStateReport,
  evaluateExportParity,
  type CurrentStateReportLike,
  type ScreenHealthRow,
} from "./current-state-evaluator";

const CANONICAL = ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"];

function report(overrides: Partial<CurrentStateReportLike["sections"]> = {}): CurrentStateReportLike {
  return {
    report_schema_version: "current-state-report/v2",
    generated_at: "2026-09-14T12:00:00Z",
    sections: {
      documents: {
        status: "available",
        data: { total: 1, by_type: { contract: 1 }, by_lifecycle_status: { analyzed: 1 } },
      },
      health: {
        status: "available",
        source_as_of: "2026-09-14T11:59:00",
        data: {
          computed_at: "2026-09-14T11:59:00",
          evidence_granularity: "clause",
          categories: CANONICAL.map((category) => ({
            category,
            state: "present",
            evidence_count: 1,
            missing_data: [],
            gap: null,
          })),
        },
      },
      schedule: { status: "not_modeled", status_reason: "Schedules are not modeled yet." },
      ...overrides,
    },
  };
}

const expectation = { expectedDocumentTotal: 1, latestRevisionAnalyzedAt: "2026-09-14T11:58:00" };

describe("PJ-01 Current State report judge", () => {
  it("accepts six canonical categories, one document and reasons on unavailable sections", () => {
    expect(evaluateCurrentStateReport(report(), expectation)).toEqual([]);
  });

  it("rejects a category set other than the six canonical categories in order", () => {
    const base = report();
    const health = base.sections.health!;
    const shuffled = report({
      health: { ...health, data: { ...health.data!, categories: [...health.data!.categories].reverse() } },
    });
    expect(evaluateCurrentStateReport(shuffled, expectation).map((v) => v.code)).toEqual(["HEALTH_CATEGORY_SET"]);
  });

  it("rejects the legacy Health taxonomy and any composite score", () => {
    const base = report();
    const health = base.sections.health!;
    const legacy = report({
      health: { ...health, data: { ...health.data!, dimensions: [{ dimension: "contract", score: 70 }], composite_score: 70 } as never },
    });
    const codes = evaluateCurrentStateReport(legacy, expectation).map((v) => v.code);
    expect(codes).toContain("LEGACY_HEALTH_TAXONOMY");
    expect(codes).toContain("HEALTH_SCORE_FABRICATED");
  });

  it("rejects dishonest unknowns: insufficient evidence with evidence, present without it", () => {
    const base = report();
    const health = base.sections.health!;
    const categories = health.data!.categories.map((item, index) =>
      index === 0 ? { ...item, state: "insufficient_evidence", evidence_count: 2 } : index === 1 ? { ...item, evidence_count: 0 } : item,
    );
    const codes = evaluateCurrentStateReport(report({ health: { ...health, data: { ...health.data!, categories } } }), expectation).map(
      (v) => v.code,
    );
    expect(codes.filter((code) => code === "HEALTH_DISHONEST_UNKNOWN")).toHaveLength(2);
  });

  it("requires a reason for every section that is not available, and one logical document", () => {
    const codes = evaluateCurrentStateReport(
      report({
        schedule: { status: "unavailable", status_reason: null },
        documents: { status: "available", data: { total: 2, by_type: { contract: 2 }, by_lifecycle_status: { analyzed: 2 } } },
      }),
      expectation,
    ).map((v) => v.code);
    expect(codes).toContain("SECTION_WITHOUT_REASON");
    expect(codes).toContain("DOCUMENT_DUPLICATED");
  });

  it("rejects Health older than the latest analysed revision", () => {
    const base = report();
    const stale = report({ health: { ...base.sections.health!, source_as_of: "2026-09-14T11:00:00" } });
    expect(evaluateCurrentStateReport(stale, expectation).map((v) => v.code)).toEqual(["HEALTH_STALE_FOR_REVISION"]);
  });
});

describe("PJ-01 Current State screen / JSON / CSV parity", () => {
  const screen: ScreenHealthRow[] = CANONICAL.map((category) => ({ category, state: "present", evidenceCount: "1" }));
  const csv = [
    "﻿section,record_type,record_id,field,value,value_state",
    ...CANONICAL.flatMap((category) => [
      `health,item,${category},state,present,`,
      `health,item,${category},evidence_count,1,`,
    ]),
  ].join("\n");

  it("accepts identical category facts on screen, in JSON and in CSV", () => {
    const json = JSON.stringify(report());
    expect(evaluateExportParity(report(), json, csv, screen)).toEqual([]);
  });

  it("reports a divergence between screen, JSON and CSV", () => {
    const json = JSON.stringify(report());
    const drifted = csv.replace("health,item,LEGAL,state,present", "health,item,LEGAL,state,insufficient_evidence");
    const codes = evaluateExportParity(report(), json, drifted, screen).map((v) => v.code);
    expect(codes).toEqual(["CSV_PARITY"]);
    const screenDrift = screen.map((row) => (row.category === "TIME" ? { ...row, evidenceCount: "0" } : row));
    expect(evaluateExportParity(report(), json, csv, screenDrift).map((v) => v.code)).toEqual(["SCREEN_PARITY"]);
    expect(evaluateExportParity(report(), "{}", csv, screen).map((v) => v.code)).toEqual(["JSON_PARITY"]);
  });
});
