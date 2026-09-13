/**
 * Test Suite ID: TS-P0D-REPORT-UI-004
 * Current State Report export: JSON is lossless; CSV keeps identity, timing,
 * section status, evidence tiers and unknown semantics, and is spreadsheet-safe.
 */
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CurrentStateReport } from "@/lib/api/generated/models";
import {
  CSV_COLUMNS,
  buildCurrentStateCsv,
  buildCurrentStateJson,
  currentStateExportFilename,
  downloadTextFile,
} from "./current-state-export";
import { buildCurrentStateReport } from "./current-state-report.fixture";

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
    } else if (char === "\r") {
      continue;
    } else if (char === "\n") {
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  const [header, ...body] = rows;
  return body.map((values) => Object.fromEntries(header.map((name, position) => [name, values[position] ?? ""])));
}

function csvRows(report: CurrentStateReport = buildCurrentStateReport()): Row[] {
  return parseCsv(buildCurrentStateCsv(report));
}

function withFirstAlertTitle(title: string): CurrentStateReport {
  const report = buildCurrentStateReport();
  const alerts = report.sections.alerts;
  return {
    ...report,
    sections: {
      ...report.sections,
      alerts: {
        ...alerts,
        data: alerts.data ? { ...alerts.data, items: [{ ...alerts.data.items[0], title }] } : alerts.data,
      },
    },
  };
}

function firstAlertRow(report: CurrentStateReport): Row | undefined {
  return csvRows(report).find((entry) => entry.section === "alerts" && entry.record_type === "item");
}

describe("buildCurrentStateJson", () => {
  it("is a lossless serialization of the report", () => {
    const report = buildCurrentStateReport();
    expect(JSON.parse(buildCurrentStateJson(report))).toEqual(report);
  });
});

describe("buildCurrentStateCsv", () => {
  it("starts with the documented export contract header", () => {
    const [header] = buildCurrentStateCsv(buildCurrentStateReport()).split("\r\n");
    expect(header.split(",")).toEqual([
      "report_schema_version",
      "generated_at",
      "project_id",
      "project_name",
      "project_code",
      "content_fingerprint",
      "section",
      "section_status",
      "status_reason",
      "source_domain",
      "source_as_of",
      "source_as_of_state",
      "evidence_tier",
      "evidence_note",
      "record_type",
      "record_id",
      "record_label",
      "field",
      "value",
      "value_state",
      "record_status",
      "record_due_at",
      "record_overdue",
      "record_evidence_tier",
      "record_source_ref",
    ]);
    expect(header.split(",")).toEqual([...CSV_COLUMNS]);
  });

  it("stamps every row with report identity and generation time", () => {
    const rows = csvRows();
    expect(rows.length).toBeGreaterThan(20);
    for (const row of rows) {
      expect(row.report_schema_version).toBe("current-state-report/v1");
      expect(row.generated_at).toBe("2026-09-13T12:00:00Z");
      expect(row.project_id).toBe("5d5c2a3e-1f7e-4c4a-9a51-2d9a7b0c1e11");
      expect(row.project_name).toBe("Hospital North");
      expect(row.content_fingerprint).toHaveLength(64);
    }
  });

  it("emits one section row per section with status, reason and evidence tier", () => {
    const sectionRows = csvRows().filter((row) => row.record_type === "section");
    expect(sectionRows.map((row) => row.section)).toEqual([
      "executive_summary",
      "documents",
      "health",
      "missing_evidence",
      "coherence",
      "alerts",
      "hitl",
      "budget",
      "wbs",
      "stakeholders",
      "raci",
      "risks",
      "obligations",
      "schedule",
      "evidence_quality",
    ]);
    const risks = sectionRows.find((row) => row.section === "risks");
    expect(risks?.section_status).toBe("not_modeled");
    expect(risks?.status_reason).toContain("risk register");
    expect(risks?.evidence_tier).toBe("unavailable");
    const wbs = sectionRows.find((row) => row.section === "wbs");
    expect(wbs?.section_status).toBe("error");
    const budget = sectionRows.find((row) => row.section === "budget");
    expect(budget?.source_as_of).toBe("");
    expect(budget?.source_as_of_state).toBe("null");
  });

  it("exports document rows with the user-facing processing status", () => {
    const rows = csvRows();
    const document = rows.find((row) => row.section === "documents" && row.record_type === "item");
    expect(document?.record_status).toBe("parsed");
    expect(rows.some((row) => row.section === "documents" && row.field === "by_processing_status.parsed")).toBe(true);
  });

  it("exports the WBS item summary with per-item evidence tiers", () => {
    const report = buildCurrentStateReport();
    const rows = csvRows({
      ...report,
      sections: {
        ...report.sections,
        wbs: {
          status: "available",
          status_reason: null,
          source_domain: "wbs",
          source_as_of: null,
          evidence_tier: "weak_linked",
          evidence_note: "Some WBS items reference only their source document. WBS items record no timestamps.",
          data: {
            item_count: 2,
            root_count: 1,
            leaf_count: 1,
            max_level: 2,
            by_item_type: { unclassified: 2 },
            items_with_budget: 0,
            items_with_planned_dates: 0,
            roots: [
              {
                id: "e5e5e5e5-0000-4000-8000-000000000001",
                code: "1",
                name: "Quay wall",
                level: 1,
                item_type: "deliverable",
                evidence_tier: "weak_linked",
              },
            ],
            truncated: false,
            evidence_breakdown: { strong_linked: 0, weak_linked: 2, unlinked: 0 },
          },
        },
      },
    });
    const wbs = rows.filter((row) => row.section === "wbs");
    expect(wbs.find((row) => row.field === "item_count")?.value).toBe("2");
    expect(wbs.find((row) => row.field === "max_level")?.value).toBe("2");
    expect(wbs.find((row) => row.field === "items_with_budget")?.value_state).toBe("known");
    expect(wbs.find((row) => row.field === "by_item_type.unclassified")?.value).toBe("2");
    const root = wbs.find((row) => row.record_type === "item");
    expect(root?.value).toBe("1");
    expect(root?.record_status).toBe("");
    expect(root?.record_evidence_tier).toBe("weak_linked");
  });

  it("keeps unknown metrics distinguishable from zero", () => {
    const rows = csvRows();
    const remaining = rows.find((row) => row.section === "budget" && row.field === "remaining_budget");
    expect(remaining?.value).toBe("");
    expect(remaining?.value_state).toBe("null");
    const spent = rows.find((row) => row.section === "budget" && row.field === "spent_amount");
    expect(spent?.value).toBe("0");
    expect(spent?.value_state).toBe("known");
    const keyPlayers = rows.find((row) => row.section === "stakeholders" && row.field === "key_player_count");
    expect(keyPlayers?.value_state).toBe("null");
    const overdue = rows.find((row) => row.section === "hitl" && row.field === "overdue_count");
    expect(overdue?.value_state).toBe("null");
    const composite = rows.find((row) => row.section === "health" && row.field === "composite_score");
    expect(composite?.value_state).toBe("null");
  });

  it("marks unknown item values as null rather than known-empty", () => {
    const report = buildCurrentStateReport();
    const stakeholders = report.sections.stakeholders;
    const withNullRole: CurrentStateReport = {
      ...report,
      sections: {
        ...report.sections,
        stakeholders: {
          ...stakeholders,
          data: stakeholders.data
            ? { ...stakeholders.data, items: [{ ...stakeholders.data.items[0], role: null }] }
            : stakeholders.data,
        },
      },
    };
    const row = csvRows(withNullRole).find((entry) => entry.section === "stakeholders" && entry.record_type === "item");
    expect(row?.value).toBe("");
    expect(row?.value_state).toBe("null");
  });

  it("exports an empty accountable list as a known 'none'", () => {
    const rows = csvRows().filter((row) => row.section === "raci" && row.record_type === "item");
    const structure = rows.find((row) => row.record_id === "1.2");
    expect(structure?.value).toBe("none");
    expect(structure?.value_state).toBe("known");
  });

  it("exports item rows with their own evidence tier and source link", () => {
    const rows = csvRows().filter((row) => row.section === "alerts" && row.record_type === "item");
    expect(rows).toHaveLength(2);
    expect(rows[0].record_id).toBe("a1a1a1a1-0000-4000-8000-000000000001");
    expect(rows[0].record_label).toBe("Penalty clause conflicts with schedule");
    expect(rows[0].record_evidence_tier).toBe("strong_linked");
    expect(rows[0].record_source_ref).toBe("c1c1c1c1-0000-4000-8000-000000000001");
    expect(rows[1].record_evidence_tier).toBe("unlinked");
    expect(rows[1].record_source_ref).toBe("");
  });

  it("exports missing-evidence gaps and attention items", () => {
    const rows = csvRows();
    const gaps = rows.filter((row) => row.section === "missing_evidence" && row.record_type === "item");
    expect(gaps.map((row) => row.record_label)).toContain("upload the risk register");
    const attention = rows.filter((row) => row.section === "executive_summary" && row.record_type === "item");
    expect(attention[0].field).toBe("critical");
  });

  it("escapes commas, quotes and newlines", () => {
    expect(firstAlertRow(withFirstAlertTitle('Clause 4.2, "late"\npenalty'))?.record_label).toBe(
      'Clause 4.2, "late"\npenalty',
    );
  });

  it("quotes values with leading or trailing spaces so they survive import", () => {
    const report = withFirstAlertTitle("  padded title  ");
    expect(buildCurrentStateCsv(report)).toContain('"  padded title  "');
    expect(firstAlertRow(report)?.record_label).toBe("  padded title  ");
  });

  it("neutralizes spreadsheet formula injection in text but not in numbers", () => {
    const row = firstAlertRow(withFirstAlertTitle('=HYPERLINK("http://x","click")'));
    expect(row?.record_label.startsWith("'=")).toBe(true);
    const total = csvRows().find((entry) => entry.section === "budget" && entry.field === "total_budget");
    expect(total?.value).toBe("1250.50");
  });

  it("neutralizes formulas hidden behind leading whitespace", () => {
    expect(firstAlertRow(withFirstAlertTitle(" =1+1"))?.record_label.startsWith("'")).toBe(true);
    expect(firstAlertRow(withFirstAlertTitle("\n@SUM(A1)"))?.record_label.startsWith("'")).toBe(true);
  });
});

describe("currentStateExportFilename", () => {
  it("names the file after the project and generation time", () => {
    const report = buildCurrentStateReport();
    expect(currentStateExportFilename(report, "csv")).toBe("current-state-report-HN-01-20260913T120000Z.csv");
    expect(currentStateExportFilename(report, "json")).toBe("current-state-report-HN-01-20260913T120000Z.json");
  });

  it("falls back to the project id and strips unsafe filename characters", () => {
    const report = buildCurrentStateReport();
    const noCode = { ...report, project: { ...report.project, code: null } };
    expect(currentStateExportFilename(noCode, "json")).toBe(
      "current-state-report-5d5c2a3e-1f7e-4c4a-9a51-2d9a7b0c1e11-20260913T120000Z.json",
    );
    const unsafe = { ...report, project: { ...report.project, code: "../HN 01/x" } };
    expect(currentStateExportFilename(unsafe, "csv")).toBe("current-state-report-HN-01-x-20260913T120000Z.csv");
  });

  it("caps very long project codes", () => {
    const report = buildCurrentStateReport();
    const long = { ...report, project: { ...report.project, code: "X".repeat(300) } };
    const filename = currentStateExportFilename(long, "csv");
    expect(filename).toContain("X".repeat(80));
    expect(filename).not.toContain("X".repeat(81));
  });
});

describe("downloadTextFile", () => {
  const originalCreate = URL.createObjectURL;
  const originalRevoke = URL.revokeObjectURL;

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    URL.createObjectURL = originalCreate;
    URL.revokeObjectURL = originalRevoke;
  });

  function stubUrls() {
    const blobs: Blob[] = [];
    const createObjectURL = vi.fn((blob: Blob) => {
      blobs.push(blob);
      return "blob:report";
    });
    const revokeObjectURL = vi.fn();
    URL.createObjectURL = createObjectURL as typeof URL.createObjectURL;
    URL.revokeObjectURL = revokeObjectURL;
    return { blobs, revokeObjectURL };
  }

  it("clicks an attached link and revokes the URL only after the download has started", () => {
    vi.useFakeTimers();
    const { revokeObjectURL } = stubUrls();
    const attachedWhenClicked: boolean[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      attachedWhenClicked.push(document.body.contains(this));
    });

    downloadTextFile("report.csv", "a,b", "text/csv;charset=utf-8");

    expect(attachedWhenClicked).toEqual([true]);
    expect(revokeObjectURL).not.toHaveBeenCalled();
    vi.runAllTimers();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:report");
    expect(document.querySelector('a[download="report.csv"]')).toBeNull();
  });

  it("adds a UTF-8 byte order mark to CSV but not to JSON", () => {
    const { blobs } = stubUrls();
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);

    downloadTextFile("report.csv", "a,b", "text/csv;charset=utf-8");
    downloadTextFile("report.json", "a,b", "application/json;charset=utf-8");

    expect(blobs[0].size).toBe(6);
    expect(blobs[1].size).toBe(3);
  });
});
