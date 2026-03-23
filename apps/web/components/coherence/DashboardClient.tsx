"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { CoherenceGauge } from "@/components/coherence/CoherenceGauge";
import { ScoreCard } from "@/components/coherence/ScoreCard";
import { BreakdownChart } from "@/components/coherence/BreakdownChart";
import { RadarView } from "@/components/coherence/RadarView";
import { AlertsDistribution } from "@/components/coherence/AlertsDistribution";
import { CategoryDetail } from "@/components/coherence/CategoryDetail";
import type { DashboardSummary } from "@/lib/api/contracts";

const CATEGORY_LABELS: Record<string, string> = {
  SCOPE: "Scope",
  BUDGET: "Budget",
  QUALITY: "Quality",
  TECHNICAL: "Technical",
  LEGAL: "Legal",
  TIME: "Time",
};

type ViewMode = "breakdown" | "radar" | "alerts";

interface DashboardClientProps {
  data: DashboardSummary;
  projectName: string;
}

export function DashboardClient({ data, projectName }: DashboardClientProps) {
  const [selectedCat, setSelectedCat] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>("breakdown");

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

  return (
    <section className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Project / {projectName}
          </div>
          <h1 className="text-[22px] font-semibold text-foreground">
            Coherence Dashboard
          </h1>
        </div>
        <div className="flex gap-2">
          {(["breakdown", "radar", "alerts"] as ViewMode[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
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

      {/* Top Row: Gauge + Dynamic View */}
      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        <CoherenceGauge
          score={data.coherence_score}
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
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
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

      {/* Selected Category Detail */}
      {selectedCat && data.sub_scores[selectedCat] != null && (
        <CategoryDetail
          category={selectedCat}
          score={data.sub_scores[selectedCat]}
          weight={data.weights_used[selectedCat] ?? 0}
          alertCount={0}
          trend={[]}
          onClose={() => setSelectedCat(null)}
        />
      )}
    </section>
  );
}
