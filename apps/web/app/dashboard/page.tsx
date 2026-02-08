"use client";

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { CoherenceGauge } from '@/components/coherence/CoherenceGauge';
import { ScoreCard } from '@/components/coherence/ScoreCard';
import { BreakdownChart } from '@/components/coherence/BreakdownChart';
import { RadarView } from '@/components/coherence/RadarView';
import { AlertsDistribution } from '@/components/coherence/AlertsDistribution';
import { CategoryDetail } from '@/components/coherence/CategoryDetail';

// ── Mock Data (TDD v3.0 spec) ──
const DATA = {
  score: 78,
  project: 'Torre Skyline — Contract Review',
  docs: 8,
  points: 2847,
  cats: {
    SCOPE: { score: 80, alerts: 2, w: 0.2, trend: [72, 75, 78, 80] },
    BUDGET: { score: 62, alerts: 5, w: 0.2, trend: [58, 60, 61, 62] },
    QUALITY: { score: 85, alerts: 1, w: 0.15, trend: [80, 82, 84, 85] },
    TECHNICAL: { score: 72, alerts: 3, w: 0.15, trend: [65, 68, 70, 72] },
    LEGAL: { score: 90, alerts: 0, w: 0.15, trend: [85, 87, 89, 90] },
    TIME: { score: 75, alerts: 4, w: 0.15, trend: [70, 72, 73, 75] },
  },
  alertSum: { critical: 2, high: 5, medium: 8, low: 3 },
};

const CATEGORY_LABELS: Record<string, string> = {
  SCOPE: 'Scope',
  BUDGET: 'Budget',
  QUALITY: 'Quality',
  TECHNICAL: 'Technical',
  LEGAL: 'Legal',
  TIME: 'Time',
};

type ViewMode = 'breakdown' | 'radar' | 'alerts';

export default function DashboardPage() {
  const [selectedCat, setSelectedCat] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>('breakdown');

  const barData = Object.entries(DATA.cats).map(([k, v]) => ({
    name: CATEGORY_LABELS[k],
    score: v.score,
  }));

  const radarData = Object.entries(DATA.cats).map(([k, v]) => ({
    category: CATEGORY_LABELS[k],
    score: v.score,
    target: 80,
  }));

  const catEntries = Object.entries(DATA.cats).sort(
    ([, a], [, b]) => a.score - b.score
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
          {(['breakdown', 'radar', 'alerts'] as ViewMode[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={cn(
                'rounded-md border px-3.5 py-1.5 text-xs font-medium capitalize transition-all duration-150',
                view === v
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:border-primary/30 hover:text-foreground'
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
          score={DATA.score}
          documentsAnalyzed={DATA.docs}
          dataPointsChecked={DATA.points}
          calculatedAt="Feb 7, 2026 14:34"
        />

        <div className="rounded-md border bg-card p-5 shadow-sm">
          {view === 'breakdown' && <BreakdownChart data={barData} />}
          {view === 'radar' && <RadarView data={radarData} />}
          {view === 'alerts' && (
            <AlertsDistribution
              critical={DATA.alertSum.critical}
              high={DATA.alertSum.high}
              medium={DATA.alertSum.medium}
              low={DATA.alertSum.low}
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
              onClick={() =>
                setSelectedCat(selectedCat === cat ? null : cat)
              }
            />
          ))}
        </div>
      </div>

      {/* Selected Category Detail */}
      {selectedCat && DATA.cats[selectedCat as keyof typeof DATA.cats] && (
        <CategoryDetail
          category={selectedCat}
          score={DATA.cats[selectedCat as keyof typeof DATA.cats].score}
          weight={DATA.cats[selectedCat as keyof typeof DATA.cats].w}
          alertCount={DATA.cats[selectedCat as keyof typeof DATA.cats].alerts}
          trend={DATA.cats[selectedCat as keyof typeof DATA.cats].trend}
          onClose={() => setSelectedCat(null)}
        />
      )}
    </section>
  );
}
