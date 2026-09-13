/**
 * Test Suite ID: TS-P0D-REPORT-UI-001
 * Current State Report view: honest states, evidence trust, scanability.
 */
import { describe, expect, it } from "vitest";
import { within } from "@testing-library/react";
import { renderWithProviders, screen } from "@/src/tests/test-utils";
import type { CurrentStateReport } from "@/lib/api/generated/models";
import { CurrentStateReportView } from "./CurrentStateReportView";
import { formatDate, formatDateTime } from "./current-state-format";
import { buildCurrentStateReport } from "./current-state-report.fixture";

function renderReport(report: CurrentStateReport = buildCurrentStateReport()) {
  renderWithProviders(<CurrentStateReportView report={report} />);
}

function section(key: string) {
  return screen.getByTestId(`section-${key}`);
}

describe("CurrentStateReportView", () => {
  it("leads with the attention items, most urgent first", () => {
    renderReport();
    const summary = screen.getByTestId("executive-summary");
    const items = within(summary).getAllByTestId("attention-item");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("Critical");
    expect(items[0]).toHaveTextContent("2 open critical or high-severity alert(s).");
    expect(items[2]).toHaveTextContent("4 review item(s) await a human decision.");
  });

  it("says plainly when nothing needs attention", () => {
    const report = buildCurrentStateReport();
    const summary = report.sections.executive_summary;
    renderReport({
      ...report,
      sections: {
        ...report.sections,
        executive_summary: {
          ...summary,
          data: summary.data ? { ...summary.data, attention_items: [] } : summary.data,
        },
      },
    });
    expect(screen.getByTestId("executive-summary")).toHaveTextContent(
      "Nothing requires attention in the data that is available.",
    );
  });

  it("states which domains the report does not cover", () => {
    renderReport();
    const summary = screen.getByTestId("executive-summary");
    expect(summary).toHaveTextContent("Not modeled yet: Risks, Obligations, Schedule");
    expect(summary).toHaveTextContent("Could not load: WBS");
  });

  it("explains a document count whose processing status is only partially known", () => {
    renderReport();
    expect(screen.getByTestId("executive-summary")).toHaveTextContent(
      "45 uploaded (document status partially loaded)",
    );
  });

  it("shows report identity, generation time and what the fingerprint means", () => {
    renderReport();
    const header = screen.getByTestId("report-header");
    expect(header).toHaveTextContent("Hospital North");
    expect(header).toHaveTextContent(formatDate("2026-09-13T12:00:00Z"));
    expect(header).toHaveTextContent("a3f1c9d2e4b5");
    expect(header).toHaveTextContent("same fingerprint means the same state");
  });

  it("gives every section a navigable heading", () => {
    renderReport();
    expect(screen.getByRole("heading", { level: 3, name: "Budget" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Awaiting decision" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: "Evidence quality" })).toBeInTheDocument();
  });

  it("renders not-modeled domains with their reason and no data", () => {
    renderReport();
    for (const key of ["risks", "obligations", "schedule"]) {
      const card = section(key);
      expect(within(card).getByTestId("section-status")).toHaveTextContent("Not modeled yet");
      expect(within(card).getByTestId("section-reason")).not.toBeEmptyDOMElement();
    }
    expect(section("risks")).toHaveTextContent("Risk-type findings are reported under Alerts");
  });

  it("renders a failed source as could-not-load, not as empty", () => {
    renderReport();
    const card = section("wbs");
    expect(within(card).getByTestId("section-status")).toHaveTextContent("Could not load");
    expect(card).toHaveTextContent("This source could not be read when the report was generated.");
  });

  it("never renders an unknown health score as zero", () => {
    renderReport();
    const card = section("health");
    expect(card).toHaveTextContent("Unknown / Insufficient evidence");
    expect(card).not.toHaveTextContent("0%");
    expect(card).toHaveTextContent("No evidence cited");
    expect(card).toHaveTextContent("upload the risk register");
  });

  it("shows every section's evidence tier visibly", () => {
    renderReport();
    expect(within(section("documents")).getByTestId("evidence-tier")).toHaveTextContent("Source document record");
    expect(within(section("stakeholders")).getByTestId("evidence-tier")).toHaveTextContent("Weak source link");
    expect(within(section("budget")).getByTestId("evidence-tier")).toHaveTextContent("No source link");
    expect(within(section("budget")).getByTestId("evidence-note")).toHaveTextContent(
      "Budget items record no source document or clause reference",
    );
  });

  it("says when a source records no timestamp instead of inventing one", () => {
    renderReport();
    expect(within(section("budget")).getByTestId("section-source")).toHaveTextContent(
      "Source records carry no timestamp",
    );
    expect(within(section("documents")).getByTestId("section-source")).toHaveTextContent(
      `As of ${formatDateTime("2026-09-12T08:00:00Z")}`,
    );
  });

  it("does not present unrecorded spend or remaining budget as fact", () => {
    renderReport();
    const card = section("budget");
    expect(card).toHaveTextContent("€1,250.50");
    expect(within(card).getByTestId("budget-spend")).toHaveTextContent("No spend recorded");
    expect(within(card).getByTestId("budget-spend")).not.toHaveTextContent("€0.00");
    expect(within(card).getByTestId("budget-remaining")).toHaveTextContent("Not shown");
    expect(card).toHaveTextContent("Currency is the system default");
  });

  it("marks partial counts instead of presenting them as complete", () => {
    renderReport();
    expect(within(section("documents")).getByTestId("partial-note")).toHaveTextContent(
      "Counts cover the documents that could be loaded, not all 45",
    );
    expect(within(section("stakeholders")).getByTestId("key-players")).toHaveTextContent("Unknown");
    expect(within(section("hitl")).getByTestId("hitl-overdue")).toHaveTextContent("Unknown");
  });

  it("flags overdue alerts and shows their evidence link strength", () => {
    renderReport();
    const card = section("alerts");
    const rows = within(card).getAllByTestId("alert-row");
    expect(rows[0]).toHaveTextContent("Penalty clause conflicts with schedule");
    expect(rows[0]).toHaveTextContent("Overdue");
    expect(rows[0]).toHaveTextContent("Strong source link");
    expect(rows[1]).not.toHaveTextContent("Overdue");
    expect(rows[1]).toHaveTextContent("No source link");
  });

  it("surfaces RACI accountability gaps", () => {
    renderReport();
    expect(section("raci")).toHaveTextContent("1 task(s) without an accountable party");
  });

  it("summarizes evidence quality for every section", () => {
    renderReport();
    const table = screen.getByTestId("evidence-quality");
    expect(within(table).getAllByTestId("evidence-quality-row")).toHaveLength(13);
    expect(table).toHaveTextContent("Stakeholders");
    expect(within(table).getAllByRole("columnheader")).toHaveLength(4);
  });

  it("shows recorded spend from the explicit flag, not from whether remaining is present", () => {
    const report = buildCurrentStateReport();
    const budget = report.sections.budget;
    renderReport({
      ...report,
      sections: {
        ...report.sections,
        budget: {
          ...budget,
          data: budget.data
            ? { ...budget.data, spent_amount: "400", spend_recorded: true, remaining_budget: null }
            : budget.data,
        },
      },
    });
    const spend = within(section("budget")).getByTestId("budget-spend");
    expect(spend).toHaveTextContent("€400.00");
    expect(spend).not.toHaveTextContent("No spend recorded");
    expect(within(section("budget")).getByTestId("budget-remaining")).toHaveTextContent("Not shown");
  });

  it("cites the health snapshot the section was projected from", () => {
    renderReport();
    expect(within(section("health")).getByTestId("section-source")).toHaveTextContent("snapshot 7e1d2c3b");
  });

  it("labels documents by lifecycle, keeping analyzed, awaiting analysis and parsed apart", () => {
    const report = buildCurrentStateReport();
    const documents = report.sections.documents;
    renderReport({
      ...report,
      sections: {
        ...report.sections,
        documents: {
          ...documents,
          data: documents.data
            ? {
                ...documents.data,
                by_lifecycle_status: { analyzed: 12, analysis_pending: 5, parsed: 3, uploaded: 3, processing: 1, error: 2 },
              }
            : documents.data,
        },
      },
    });
    const card = section("documents");
    expect(card).toHaveTextContent("Contract · Analyzed");
    expect(card).toHaveTextContent("Analyzed: 12");
    expect(card).toHaveTextContent("Analysis pending: 5");
    expect(card).toHaveTextContent("Parsed: 3");
    expect(card).toHaveTextContent("Uploaded: 3");
    expect(card).toHaveTextContent("Processing: 1");
    expect(card).toHaveTextContent("Error: 2");
    expect(card).not.toHaveTextContent("Processed");
    expect(card).not.toHaveTextContent("Queued");
  });

  it("states how many documents are analyzed and how many await analysis", () => {
    const report = buildCurrentStateReport();
    const summary = report.sections.executive_summary;
    renderReport({
      ...report,
      sections: {
        ...report.sections,
        executive_summary: {
          ...summary,
          data: summary.data
            ? { ...summary.data, document_count: 20, analyzed_document_count: 12, awaiting_analysis_document_count: 8 }
            : summary.data,
        },
      },
    });
    const card = screen.getByTestId("executive-summary");
    expect(card).toHaveTextContent("20 uploaded · 12 analyzed · 8 awaiting analysis");
    expect(card).not.toHaveTextContent("processed");
  });

  it("describes the WBS tab's items with coverage and per-item evidence strength", () => {
    const report = buildCurrentStateReport();
    renderReport({
      ...report,
      sections: {
        ...report.sections,
        wbs: {
          status: "available",
          status_reason: null,
          source_domain: "wbs",
          source_as_of: null,
          evidence_tier: "unlinked",
          evidence_note: "Some WBS items record no source document or clause. WBS items record no timestamps.",
          data: {
            item_count: 3,
            root_count: 1,
            leaf_count: 2,
            max_level: 2,
            by_item_type: { deliverable: 1, work_package: 2 },
            items_with_budget: 1,
            items_with_planned_dates: 0,
            roots: [
              {
                id: "e5e5e5e5-0000-4000-8000-000000000001",
                code: "1",
                name: "Harbour Extension",
                level: 1,
                item_type: "deliverable",
                planned_start: null,
                planned_end: null,
                budget_allocated: null,
                evidence_tier: "strong_linked",
              },
            ],
            truncated: false,
            evidence_breakdown: { strong_linked: 1, weak_linked: 0, unlinked: 2 },
          },
        },
      },
    });
    const card = section("wbs");
    expect(card).toHaveTextContent("3 item(s) · 1 top-level · 2 leaf · deepest level 2");
    expect(within(card).getByTestId("wbs-coverage")).toHaveTextContent(
      "1 of 3 with a budget · 0 of 3 with planned start and end",
    );
    expect(card).toHaveTextContent("Harbour Extension");
    expect(card).toHaveTextContent("Deliverable · Strong source link");
    expect(within(card).getByTestId("section-source")).toHaveTextContent("Source records carry no timestamp");
  });

  it("renders an empty section with its reason", () => {
    const report = buildCurrentStateReport();
    const emptyAlerts: CurrentStateReport = {
      ...report,
      sections: {
        ...report.sections,
        alerts: {
          status: "empty",
          status_reason: "No alerts have been raised for this project.",
          source_domain: "alerts",
          source_as_of: null,
          evidence_tier: "unavailable",
          evidence_note: null,
          data: null,
        },
      },
    };
    renderReport(emptyAlerts);
    const card = section("alerts");
    expect(within(card).getByTestId("section-status")).toHaveTextContent("Nothing recorded");
    expect(card).toHaveTextContent("No alerts have been raised for this project.");
    expect(within(card).getByTestId("evidence-tier")).toHaveTextContent("No data to assess");
  });
});
