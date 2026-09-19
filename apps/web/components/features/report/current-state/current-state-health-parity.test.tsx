/**
 * Test Suite ID: TS-P0D-REPORT-UI-006
 * Current State Health speaks the canonical six-category contract on every surface.
 *
 * MASTER / ADR-018 (2026-09-13 amendment): user-facing Health is SCOPE, BUDGET, TIME,
 * TECHNICAL, LEGAL, QUALITY. The legacy ADR-018 v0 dimensions stay internal, and there is no
 * composite Health headline until a canonical six-category roll-up exists. Screen, JSON and
 * CSV must describe the same six categories with the same state, evidence, missing data and gap.
 */
import { within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CurrentStateReport } from "@/lib/api/generated/models";
import { renderWithProviders, screen } from "@/src/tests/test-utils";

import { CurrentStateReportView } from "./CurrentStateReportView";
import { buildCurrentStateCsv, buildCurrentStateJson } from "./current-state-export";
import { buildCurrentStateReport } from "./current-state-report.fixture";

const CANONICAL = ["SCOPE", "BUDGET", "TIME", "TECHNICAL", "LEGAL", "QUALITY"];
const LEGACY_LABEL = /^(contract|risk|documentation|governance|schedule|cost|deliverables)$/i;

type Row = Record<string, string>;

function parseCsv(text: string): Row[] {
  const rows: string[][] = [];
  let field = "";
  let row: string[] = [];
  let quoted = false;
  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (quoted) {
      if (char === '"' && text[index + 1] === '"') {
        field += '"';
        index += 1;
      } else if (char === '"') {
        quoted = false;
      } else {
        field += char;
      }
    } else if (char === '"') {
      quoted = true;
    } else if (char === ",") {
      row.push(field);
      field = "";
    } else if (char === "\n") {
      row.push(field.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  const [header, ...body] = rows;
  return body.map((cells) => Object.fromEntries(header.map((name, index) => [name.replace(/^\uFEFF/, ""), cells[index] ?? ""])));
}

interface HealthFacts {
  state: string;
  evidence_count: string;
  missing_data: string;
  gap: string;
}

function renderReport(report: CurrentStateReport) {
  renderWithProviders(<CurrentStateReportView report={report} />);
}

describe("Current State Health — canonical six-category contract", () => {
  it("screen, JSON and CSV carry the same six canonical categories with the same facts", () => {
    const report = buildCurrentStateReport();
    renderReport(report);

    const rows = within(screen.getByTestId("section-health")).getAllByTestId("health-category");
    const fromScreen = Object.fromEntries(
      rows.map((row) => [
        row.getAttribute("data-category") ?? "",
        {
          state: row.getAttribute("data-state") ?? "",
          evidence_count: row.getAttribute("data-evidence-count") ?? "",
          missing_data: row.getAttribute("data-missing-data") ?? "",
          gap: row.getAttribute("data-gap") ?? "",
        } satisfies HealthFacts,
      ]),
    );

    const json = JSON.parse(buildCurrentStateJson(report)) as CurrentStateReport;
    const categories = json.sections.health.data?.categories ?? [];
    const fromJson = Object.fromEntries(
      categories.map((item) => [
        item.category,
        {
          state: item.state,
          evidence_count: String(item.evidence_count),
          missing_data: (item.missing_data ?? []).join("; "),
          gap: item.gap ?? "",
        } satisfies HealthFacts,
      ]),
    );

    const csvHealth = parseCsv(buildCurrentStateCsv(report)).filter(
      (row) => row.section === "health" && row.record_type === "item",
    );
    const fromCsv: Record<string, HealthFacts> = {};
    for (const row of csvHealth) {
      fromCsv[row.record_id] ??= { state: "", evidence_count: "", missing_data: "", gap: "" };
      fromCsv[row.record_id][row.field as keyof HealthFacts] = row.value;
    }

    expect(rows.map((row) => row.getAttribute("data-category"))).toEqual(CANONICAL);
    expect(categories.map((item) => item.category)).toEqual(CANONICAL);
    expect(Object.keys(fromCsv)).toEqual(CANONICAL);
    expect(fromScreen).toEqual(fromJson);
    expect(fromCsv).toEqual(fromJson);
  });

  it("never shows a legacy internal dimension or a composite as Health", () => {
    const report = buildCurrentStateReport();
    renderReport(report);

    const card = screen.getByTestId("section-health");
    expect(within(card).queryAllByText(LEGACY_LABEL)).toHaveLength(0);
    expect(card).not.toHaveTextContent(/composite/i);
    expect(screen.getByTestId("executive-summary")).not.toHaveTextContent(/health composite/i);

    const csv = parseCsv(buildCurrentStateCsv(report));
    const healthRecords = csv.filter((row) => row.section === "health" && row.record_type === "item");
    expect(healthRecords.every((row) => CANONICAL.includes(row.record_id))).toBe(true);
    expect(csv.some((row) => /composite/.test(row.field))).toBe(false);
    const healthGaps = csv.filter((row) => row.section === "missing_evidence" && row.field === "health");
    expect(healthGaps.every((row) => CANONICAL.includes(row.value))).toBe(true);
  });

  it("names unknown categories as unknown and never renders zero", () => {
    renderReport(buildCurrentStateReport());
    const unknownRows = within(screen.getByTestId("section-health"))
      .getAllByTestId("health-category")
      .filter((row) => row.getAttribute("data-state") === "insufficient_evidence");
    expect(unknownRows.length).toBeGreaterThan(0);
    for (const row of unknownRows) {
      expect(row).toHaveTextContent("Unknown / Insufficient evidence");
      expect(row).not.toHaveTextContent(/\b0\s*%/);
    }
    expect(screen.getByTestId("health-granularity")).toHaveTextContent(/clause-level/i);
  });

  it("renders an unevaluated Health section as unavailable, not as six unknown categories", () => {
    const report = buildCurrentStateReport();
    const notEvaluated: CurrentStateReport = {
      ...report,
      sections: {
        ...report.sections,
        health: {
          ...report.sections.health,
          status: "unavailable",
          status_reason: "The six Health categories have not been evaluated for this project yet.",
          evidence_tier: "unavailable",
          evidence_note: null,
          data: null,
        },
      },
    };
    renderReport(notEvaluated);
    const card = screen.getByTestId("section-health");
    expect(within(card).queryAllByTestId("health-category")).toHaveLength(0);
    expect(card).toHaveTextContent("The six Health categories have not been evaluated for this project yet.");
    const csvHealth = parseCsv(buildCurrentStateCsv(notEvaluated)).filter(
      (row) => row.section === "health" && row.record_type !== "section",
    );
    expect(csvHealth).toHaveLength(0);
  });
});
