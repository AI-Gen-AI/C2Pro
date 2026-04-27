"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { CoherenceGauge } from "@/components/coherence/CoherenceGauge";
import { ScoreCard } from "@/components/coherence/ScoreCard";
import { BreakdownChart } from "@/components/coherence/BreakdownChart";
import { RadarView } from "@/components/coherence/RadarView";
import { AlertsDistribution } from "@/components/coherence/AlertsDistribution";
import { CategoryDetail } from "@/components/coherence/CategoryDetail";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import type { DashboardSummary } from "@/lib/api/contracts";

const CATEGORY_LABELS: Record<string, string> = {
  LEGAL: "Legal",
  SCHEDULE: "Schedule",
  QUALITY: "Quality",
  SCOPE: "Scope",
  TECHNICAL: "Technical",
  BUDGET: "Budget",
  // Legacy aliases — kept so dashboards keep rendering while older
  // payloads still flow through normalization.
  TIME: "Schedule",
  FINANCIAL: "Budget",
  HSE: "Quality",
};

type ViewMode = "breakdown" | "radar" | "alerts";
type LayoutMode = "overview" | "focus" | "compact";
type TemplateMode = "executive" | "portfolio" | "risk-review" | "custom";

const LAYOUT_OPTIONS: Array<{
  value: LayoutMode;
  label: string;
  description: string;
}> = [
  {
    value: "overview",
    label: "Overview",
    description: "Overview layout prioritizes balanced monitoring.",
  },
  {
    value: "focus",
    label: "Focus",
    description: "Focus layout emphasizes the selected coherence analysis.",
  },
  {
    value: "compact",
    label: "Compact",
    description: "Compact layout condenses dashboard panels for quick scanning.",
  },
];

const TEMPLATE_OPTIONS: Array<{
  value: TemplateMode;
  label: string;
  description: string;
  layout: LayoutMode;
  view: ViewMode;
}> = [
  {
    value: "executive",
    label: "Executive",
    description:
      "Executive template keeps the overview layout with balanced score distribution.",
    layout: "overview",
    view: "breakdown",
  },
  {
    value: "portfolio",
    label: "Portfolio",
    description:
      "Portfolio template tracks alert load across a denser review surface.",
    layout: "compact",
    view: "alerts",
  },
  {
    value: "risk-review",
    label: "Risk Review",
    description:
      "Risk review template highlights category comparison for deeper analysis.",
    layout: "focus",
    view: "radar",
  },
];

function sanitizeFilename(value: string): string {
  return value
    .trim()
    .replace(/[^a-z0-9_.-]+/gi, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "")
    .toLowerCase();
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function buildDashboardRows(data: DashboardSummary) {
  return Object.entries(data.sub_scores)
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([category, score]) => ({
      category: CATEGORY_LABELS[category] ?? category,
      score,
      weight: data.weights_used[category] ?? 0,
    }));
}

interface DashboardClientProps {
  data: DashboardSummary;
  projectName: string;
}

export function DashboardClient({ data, projectName }: DashboardClientProps) {
  const [selectedCat, setSelectedCat] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>("breakdown");
  const [layout, setLayout] = useState<LayoutMode>("overview");
  const [template, setTemplate] = useState<TemplateMode>("executive");
  const score = data.coherence_score ?? 0;

  const barData = Object.entries(data.sub_scores).map(([k, score]) => ({
    name: CATEGORY_LABELS[k] ?? k,
    score,
  }));

  const radarData = Object.entries(data.sub_scores).map(([k, score]) => ({
    category: CATEGORY_LABELS[k] ?? k,
    score,
    target: 80,
  }));

  const catEntries = Object.entries(data.sub_scores).sort(
    ([, a], [, b]) => a - b,
  );
  const activeLayout =
    LAYOUT_OPTIONS.find((option) => option.value === layout) ?? LAYOUT_OPTIONS[0];
  const activeTemplate =
    TEMPLATE_OPTIONS.find((option) => option.value === template) ??
    null;
  const activeDescription =
    template === "custom" ? activeLayout.description : activeTemplate?.description;
  const dashboardRows = buildDashboardRows(data);

  function exportPdfReport() {
    const popup = window.open("", "_blank", "noopener,noreferrer,width=960,height=720");
    if (!popup) {
      return;
    }

    const printedAt = data.last_updated
      ? new Date(data.last_updated).toLocaleString()
      : "Unavailable";
    const rowMarkup = dashboardRows
      .map(
        (row) =>
          `<tr><td>${escapeXml(row.category)}</td><td>${row.score}</td><td>${Math.round(
            row.weight * 100,
          )}%</td></tr>`,
      )
      .join("");

    popup.document.write(`<!DOCTYPE html>
<html lang="en">
  <head>
    <title>${escapeXml(projectName)} Coherence Dashboard</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 32px; color: #111827; }
      h1 { margin-bottom: 8px; font-size: 28px; }
      p { margin: 0 0 12px; color: #4b5563; }
      .summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 24px 0; }
      .card { border: 1px solid #d1d5db; border-radius: 12px; padding: 16px; }
      .label { font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; color: #6b7280; }
      .value { margin-top: 8px; font-size: 24px; font-weight: 700; }
      table { width: 100%; border-collapse: collapse; margin-top: 24px; }
      th, td { border: 1px solid #d1d5db; padding: 10px 12px; text-align: left; }
      th { background: #f3f4f6; }
    </style>
  </head>
  <body>
    <p>Project / ${escapeXml(projectName)}</p>
    <h1>Coherence Dashboard</h1>
    <p>${escapeXml(activeDescription ?? "Dashboard export")}</p>
    <div class="summary">
      <div class="card">
        <div class="label">Coherence Score</div>
        <div class="value">${score}</div>
      </div>
      <div class="card">
        <div class="label">Documents</div>
        <div class="value">${data.document_count}</div>
      </div>
      <div class="card">
        <div class="label">Alerts</div>
        <div class="value">${data.alert_count}</div>
      </div>
    </div>
    <p>Generated ${escapeXml(printedAt)}</p>
    <table>
      <thead>
        <tr><th>Category</th><th>Score</th><th>Weight</th></tr>
      </thead>
      <tbody>${rowMarkup}</tbody>
    </table>
  </body>
</html>`);
    popup.document.close();
    popup.focus();
    popup.print();
  }

  function exportExcelReport() {
    const rowsXml = dashboardRows
      .map(
        (row) =>
          `<Row><Cell><Data ss:Type="String">${escapeXml(row.category)}</Data></Cell><Cell><Data ss:Type="Number">${row.score}</Data></Cell><Cell><Data ss:Type="Number">${row.weight}</Data></Cell></Row>`,
      )
      .join("");
    const workbook = `<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
  <Worksheet ss:Name="Dashboard">
    <Table>
      <Row><Cell><Data ss:Type="String">Project</Data></Cell><Cell><Data ss:Type="String">${escapeXml(projectName)}</Data></Cell></Row>
      <Row><Cell><Data ss:Type="String">Coherence Score</Data></Cell><Cell><Data ss:Type="Number">${score}</Data></Cell></Row>
      <Row><Cell><Data ss:Type="String">Documents</Data></Cell><Cell><Data ss:Type="Number">${data.document_count}</Data></Cell></Row>
      <Row><Cell><Data ss:Type="String">Alerts</Data></Cell><Cell><Data ss:Type="Number">${data.alert_count}</Data></Cell></Row>
      <Row><Cell><Data ss:Type="String">Category</Data></Cell><Cell><Data ss:Type="String">Score</Data></Cell><Cell><Data ss:Type="String">Weight</Data></Cell></Row>
      ${rowsXml}
    </Table>
  </Worksheet>
</Workbook>`;
    const blob = new Blob([workbook], {
      type: "application/vnd.ms-excel",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${sanitizeFilename(projectName)}_coherence_dashboard.xls`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }

  return (
    <section className="space-y-5" data-layout={layout}>
      {/* Header */}
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Project / {projectName}
          </div>
          <h1 className="text-[22px] font-semibold text-foreground">
            Coherence Dashboard
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {activeDescription}
          </p>
        </div>
        <div className="flex flex-col gap-3 xl:items-end">
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              onClick={exportPdfReport}
              className="rounded-md border border-border bg-background px-3.5 py-1.5 text-xs font-medium text-foreground transition-all duration-150 hover:border-primary/30 hover:text-primary"
            >
              Export PDF
            </button>
            <button
              type="button"
              onClick={exportExcelReport}
              className="rounded-md border border-border bg-background px-3.5 py-1.5 text-xs font-medium text-foreground transition-all duration-150 hover:border-primary/30 hover:text-primary"
            >
              Export Excel
            </button>
          </div>
          <div className="flex flex-wrap gap-2">
            {TEMPLATE_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  setTemplate(option.value);
                  setLayout(option.layout);
                  setView(option.view);
                }}
                className={cn(
                  "rounded-full border px-3.5 py-1.5 text-xs font-medium transition-all duration-150",
                  template === option.value
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-background text-muted-foreground hover:border-primary/30 hover:text-foreground",
                )}
                aria-pressed={template === option.value}
              >
                {option.label} Template
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {LAYOUT_OPTIONS.map((option) => (
              <button
                key={option.value}
                onClick={() => {
                  setTemplate("custom");
                  setLayout(option.value);
                }}
                className={cn(
                  "rounded-md border px-3.5 py-1.5 text-xs font-medium transition-all duration-150",
                  layout === option.value
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-muted-foreground hover:border-primary/30 hover:text-foreground",
                )}
                aria-pressed={layout === option.value}
              >
                {option.label} Layout
              </button>
            ))}
          </div>
          <div className="flex flex-wrap gap-2">
            {(["breakdown", "radar", "alerts"] as ViewMode[]).map((v) => (
              <button
                key={v}
                onClick={() => {
                  setTemplate("custom");
                  setView(v);
                }}
                className={cn(
                  "rounded-md border px-3.5 py-1.5 text-xs font-medium capitalize transition-all duration-150",
                  view === v
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border bg-card text-muted-foreground hover:border-primary/30 hover:text-foreground",
                )}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Top Row: Gauge + Dynamic View */}
      <div
        className={cn(
          "grid gap-5",
          layout === "focus" && "xl:grid-cols-[1fr_320px]",
          layout === "overview" && "lg:grid-cols-[280px_1fr]",
          layout === "compact" && "xl:grid-cols-[240px_1fr]",
        )}
      >
        <CoherenceGauge
          score={score}
          documentsAnalyzed={data.document_count}
          dataPointsChecked={0}
          calculatedAt={
            data.last_updated
              ? new Date(data.last_updated).toLocaleString()
              : "—"
          }
        />

        <div className="rounded-md border bg-card p-5 shadow-sm">
          {view === "breakdown" && <BreakdownChart data={barData} />}
          {view === "radar" && <RadarView data={radarData} />}
          {view === "alerts" && (
            <AlertsDistribution
              critical={0}
              high={0}
              medium={data.alert_count}
              low={0}
            />
          )}
        </div>
      </div>

      {/* Category Cards */}
      <div>
        <h3 className="mb-3 text-sm font-semibold">Sub-Category Breakdown</h3>
        <div
          className={cn(
            "grid gap-3",
            layout === "compact" && "md:grid-cols-2 xl:grid-cols-4",
            layout === "overview" && "sm:grid-cols-2 xl:grid-cols-3",
            layout === "focus" && "sm:grid-cols-2",
          )}
        >
          {catEntries.map(([cat, score]) => (
            <ScoreCard
              key={cat}
              category={cat}
              score={score}
              weight={data.weights_used[cat] ?? 0}
              alertCount={0}
              selected={selectedCat === cat}
              onClick={() => setSelectedCat(selectedCat === cat ? null : cat)}
            />
          ))}
        </div>
      </div>

      <Sheet
        open={selectedCat != null && data.sub_scores[selectedCat] != null}
        onOpenChange={(open) => {
          if (!open) {
            setSelectedCat(null);
          }
        }}
      >
        <SheetContent side="right" className="w-full overflow-y-auto sm:max-w-xl">
          {selectedCat && data.sub_scores[selectedCat] != null && (
            <div className="space-y-5">
              <SheetHeader>
                <SheetTitle>Coherence Score Drill-down</SheetTitle>
                <SheetDescription>
                  Review the {CATEGORY_LABELS[selectedCat] ?? selectedCat} score,
                  weighting, and supporting signals for {projectName}.
                </SheetDescription>
              </SheetHeader>
              <CategoryDetail
                category={selectedCat}
                score={data.sub_scores[selectedCat]}
                weight={data.weights_used[selectedCat] ?? 0}
                alertCount={0}
                trend={[]}
                onClose={() => setSelectedCat(null)}
              />
            </div>
          )}
        </SheetContent>
      </Sheet>
    </section>
  );
}
