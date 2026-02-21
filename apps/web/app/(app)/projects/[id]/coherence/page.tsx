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

export default function ProjectCoherencePage() {
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
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Coherence Dashboard</h3>
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
        <CoherenceGauge
          score={coherenceData.score}
          documentsAnalyzed={coherenceData.docs}
          dataPointsChecked={coherenceData.points}
        />
        <div className="rounded-md border bg-card p-5 shadow-sm">
          {view === "breakdown" && <BreakdownChart data={barData} />}
          {view === "radar" && <RadarView data={radarData} />}
          {view === "alerts" && (
            <AlertsDistribution {...coherenceData.alertSum} />
          )}
        </div>
      </div>

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
    </div>
  );
}
