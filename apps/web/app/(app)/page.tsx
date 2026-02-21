"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { CoherenceGauge } from "@/components/coherence/CoherenceGauge";
import { ScoreCard } from "@/components/coherence/ScoreCard";
import { BreakdownChart } from "@/components/coherence/BreakdownChart";
import { RadarView } from "@/components/coherence/RadarView";
import { AlertsDistribution } from "@/components/coherence/AlertsDistribution";
import { CategoryDetail } from "@/components/coherence/CategoryDetail";

import { categoryLabels, coherenceData } from "@/lib/demo-data/coherence";

type ViewMode = "breakdown" | "radar" | "alerts";

export default function DashboardPage() {
  const [selectedCat, setSelectedCat] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>("breakdown");

  const barData = Object.entries(coherenceData.cats).map(([k, v]) => ({
    name: categoryLabels[k],
    score: v.score,
  }));

  const radarData = Object.entries(coherenceData.cats).map(([k, v]) => ({
    category: categoryLabels[k],
    score: v.score,
    target: 80,
  }));

  const catEntries = Object.entries(coherenceData.cats).sort(
    ([, a], [, b]) => a.score - b.score,
  );

  return (
    <section className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Project / Torre Skyline
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
          score={coherenceData.score}
          documentsAnalyzed={coherenceData.docs}
          dataPointsChecked={coherenceData.points}
          calculatedAt="Feb 7, 2026 14:34"
        />

        <div className="rounded-md border bg-card p-5 shadow-sm">
          {view === "breakdown" && <BreakdownChart data={barData} />}
          {view === "radar" && <RadarView data={radarData} />}
          {view === "alerts" && (
            <AlertsDistribution
              critical={coherenceData.alertSum.critical}
              high={coherenceData.alertSum.high}
              medium={coherenceData.alertSum.medium}
              low={coherenceData.alertSum.low}
            />
          )}
        </div>
      </div>

      {/* Category Cards */}
      <div>
        <h3 className="mb-3 text-sm font-semibold">Sub-Category Breakdown</h3>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {catEntries.map(([cat, data]) => (
            <ScoreCard
              key={cat}
              category={cat}
              score={data.score}
              weight={data.w}
              alertCount={data.alerts}
              selected={selectedCat === cat}
              onClick={() => setSelectedCat(selectedCat === cat ? null : cat)}
            />
          ))}
        </div>
      </div>

      {/* Selected Category Detail */}
      {selectedCat &&
        coherenceData.cats[selectedCat as keyof typeof coherenceData.cats] && (
          <CategoryDetail
            category={selectedCat}
            score={
              coherenceData.cats[selectedCat as keyof typeof coherenceData.cats]
                .score
            }
            weight={
              coherenceData.cats[selectedCat as keyof typeof coherenceData.cats]
                .w
            }
            alertCount={
              coherenceData.cats[selectedCat as keyof typeof coherenceData.cats]
                .alerts
            }
            trend={
              coherenceData.cats[selectedCat as keyof typeof coherenceData.cats]
                .trend
            }
            onClose={() => setSelectedCat(null)}
          />
        )}
    </section>
  );
}
