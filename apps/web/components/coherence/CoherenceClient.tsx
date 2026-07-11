"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { CoherenceGauge } from "@/components/coherence/CoherenceGauge";
import { ScoreCard } from "@/components/coherence/ScoreCard";
import { BreakdownChart } from "@/components/coherence/BreakdownChart";
import { RadarView } from "@/components/coherence/RadarView";
import { AlertsDistribution } from "@/components/coherence/AlertsDistribution";
import { CategoryDetail } from "@/components/coherence/CategoryDetail";
import { CategoryV2Panel } from "@/components/coherence/CategoryV2Panel";
import type { DashboardSummary } from "@/lib/api/contracts";
import { ScoreVersionBadge } from "@/src/components/coherence/ScoreVersionBadge";
import { useListProjectAlertsApiV1AlertsProjectsProjectIdGet } from "@/lib/api/generated/alerts/alerts";
import type { AlertResponse } from "@/lib/api/generated/models";

const LABELS: Record<string, string> = {
  SCOPE: "Scope",
  BUDGET: "Budget",
  QUALITY: "Quality",
  TECHNICAL: "Technical",
  LEGAL: "Legal",
  TIME: "Time",
};

type ViewMode = "breakdown" | "radar" | "alerts";

interface CoherenceClientProps {
  summary: DashboardSummary;
}

export function CoherenceClient({ summary }: CoherenceClientProps) {
  const [selectedCat, setSelectedCat] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>("breakdown");
  const {
    data: alertsResponse,
    isLoading: alertsLoading,
    error: alertsError,
  } = useListProjectAlertsApiV1AlertsProjectsProjectIdGet(summary.project_id, undefined);
  const score = typeof summary.coherence_score === "number" ? summary.coherence_score : null;
  const hasScore = score !== null;
  const missingDimensions = summary.score_missing_dimensions ?? [];
  const alerts = alertsResponse?.items ?? [];
  const alertsAvailable = !alertsLoading && !alertsError;
  const severityCounts = alerts.reduce(
    (counts: { critical: number; high: number; medium: number; low: number }, alert: AlertResponse) => {
      const severity = alert.severity.toLowerCase();
      if (severity === "critical" || severity === "high" || severity === "medium" || severity === "low") {
        counts[severity] += 1;
      }
      return counts;
    },
    { critical: 0, high: 0, medium: 0, low: 0 },
  );
  const alertCountByCategory = alerts.reduce<Record<string, number>>((counts: Record<string, number>, alert: AlertResponse) => {
    const current = counts[alert.category];
    counts[alert.category] = (current === undefined ? 0 : current) + 1;
    return counts;
  }, {});
  // ADR-009 §18: an unloaded/errored alert list means the count is unknown,
  // not zero — return null so ScoreCard/CategoryDetail render it as absent.
  const alertCountFor = (category: string): number | null => {
    if (!alertsAvailable) return null;
    const count = alertCountByCategory[category];
    return count === undefined ? 0 : count;
  };

  const barData = Object.entries(summary.sub_scores).map(([k, score]) => ({
    name: LABELS[k] ?? k,
    score,
  }));

  const radarData = Object.entries(summary.sub_scores).map(([k, score]) => ({
    category: LABELS[k] ?? k,
    score,
    target: 80,
  }));

  // ADR-009 §18: nulls last; never NaN-coerce via `a - b` on partial coverage.
  const catEntries = Object.entries(summary.sub_scores).sort(
    ([, a], [, b]) => {
      if (a === null && b === null) return 0;
      if (a === null) return 1;
      if (b === null) return -1;
      return a - b;
    },
  );

  return (
    <>
      {!hasScore ? (
        <div className="rounded-md border border-amber-300 bg-amber-50 px-4 py-4 text-sm text-amber-950">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div className="flex gap-3">
              <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-700" aria-hidden />
              <div>
                <p className="font-semibold">
                  Supply missing dimensions to unlock full Coherence Score
                </p>
                <p className="mt-1 text-amber-900/80">
                  Score withheld: this audit is missing{" "}
                  <span className="font-semibold">
                    {missingDimensions.length > 0
                      ? missingDimensions.join(", ")
                      : "required schedule or budget evidence"}
                  </span>
                  . Upload them to unlock the full Coherence Score.
                </p>
              </div>
            </div>
            <Link
              className="inline-flex h-9 items-center justify-center rounded-md bg-amber-900 px-3 text-xs font-semibold text-white transition-colors hover:bg-amber-800"
              href={`/projects/${summary.project_id}/documents`}
            >
              Upload schedule and budget
            </Link>
          </div>
        </div>
      ) : null}

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold">Coherence Dashboard</h3>
          <ScoreVersionBadge scoreVersion={summary.score_version} />
        </div>
        <div className="flex gap-2">
          {(["breakdown", "radar", "alerts"] as ViewMode[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={cn(
                "rounded-md border px-3 py-1.5 text-xs font-medium capitalize transition-all duration-150",
                view === v
                  ? "border-primary bg-primary/10 text-primary"
                  : "border-border bg-card text-muted-foreground hover:text-foreground",
              )}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        {hasScore ? (
          <CoherenceGauge
            score={score}
            documentsAnalyzed={summary.document_count}
            dataPointsChecked={summary.alert_count}
          />
        ) : (
          <div className="flex min-h-[230px] flex-col items-center justify-center rounded-md border border-dashed bg-card p-6 text-center shadow-sm">
            <div className="font-mono text-[40px] font-bold leading-none text-muted-foreground">
              --
            </div>
            <p className="mt-2 text-sm font-medium">Score withheld</p>
            <p className="mt-1 max-w-[220px] text-xs leading-relaxed text-muted-foreground">
              Provide the full contract, schedule, and budget triplet to calculate v1.
            </p>
          </div>
        )}
        <div className="rounded-md border bg-card p-5 shadow-sm">
          {view === "breakdown" && <BreakdownChart data={barData} />}
          {view === "radar" && <RadarView data={radarData} />}
          {view === "alerts" && (
            alertsAvailable && alerts.length > 0 ? (
              <AlertsDistribution
                critical={severityCounts.critical}
                high={severityCounts.high}
                medium={severityCounts.medium}
                low={severityCounts.low}
              />
            ) : (
              <div className="flex min-h-[190px] flex-col items-center justify-center rounded-md border border-dashed bg-muted/20 p-6 text-center">
                <p className="text-sm font-medium text-foreground">
                  {alertsLoading ? "Loading alert data" : "No alert data"}
                </p>
                <p className="mt-1 max-w-sm text-xs text-muted-foreground">
                  {alertsLoading
                    ? "Alert distribution will appear when the backend response is available."
                    : "Alert distribution requires live project alerts from the backend."}
                </p>
              </div>
            )
          )}
        </div>
      </div>

      {summary.categories_v2 ? (
        <CategoryV2Panel payload={summary.categories_v2} />
      ) : (
        <>
          <div>
            <h3 className="mb-3 text-sm font-semibold">Sub-Category Breakdown</h3>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {catEntries.map(([cat, score]) => (
                <ScoreCard
                  key={cat}
                  category={cat}
                  score={score}
                  weight={summary.weights_used[cat] ?? 0}
                  alertCount={alertCountFor(cat)}
                  selected={selectedCat === cat}
                  onClick={() => setSelectedCat(selectedCat === cat ? null : cat)}
                />
              ))}
            </div>
          </div>

          {selectedCat && summary.sub_scores[selectedCat] != null && (
            <CategoryDetail
              category={selectedCat}
              score={summary.sub_scores[selectedCat]}
              weight={summary.weights_used[selectedCat] ?? 0}
              alertCount={alertCountFor(selectedCat)}
              onClose={() => setSelectedCat(null)}
            />
          )}
        </>
      )}
    </>
  );
}
