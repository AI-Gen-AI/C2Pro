'use client';

import { useState } from 'react';
import { cn } from '@/lib/utils';
import { CoherenceGauge } from '@/components/coherence/CoherenceGauge';
import { ScoreCard } from '@/components/coherence/ScoreCard';
import { BreakdownChart } from '@/components/coherence/BreakdownChart';
import { RadarView } from '@/components/coherence/RadarView';
import { AlertsDistribution } from '@/components/coherence/AlertsDistribution';
import { CategoryDetail } from '@/components/coherence/CategoryDetail';
import type { DashboardSummary } from '@/lib/api/generated/models';

const LABELS: Record<string, string> = {
  SCOPE: 'Scope',
  BUDGET: 'Budget',
  QUALITY: 'Quality',
  TECHNICAL: 'Technical',
  LEGAL: 'Legal',
  TIME: 'Time',
};

type ViewMode = 'breakdown' | 'radar' | 'alerts';

interface CoherenceClientProps {
  summary: DashboardSummary;
}

export function CoherenceClient({ summary }: CoherenceClientProps) {
  const [selectedCat, setSelectedCat] = useState<string | null>(null);
  const [view, setView] = useState<ViewMode>('breakdown');

  const barData = Object.entries(summary.sub_scores).map(([k, score]) => ({
    name: LABELS[k] ?? k,
    score,
  }));

  const radarData = Object.entries(summary.sub_scores).map(([k, score]) => ({
    category: LABELS[k] ?? k,
    score,
    target: 80,
  }));

  const catEntries = Object.entries(summary.sub_scores).sort(
    ([, a], [, b]) => a - b
  );

  return (
    <>
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Coherence Dashboard</h3>
        <div className="flex gap-2">
          {(['breakdown', 'radar', 'alerts'] as ViewMode[]).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={cn(
                'rounded-md border px-3 py-1.5 text-xs font-medium capitalize transition-all duration-150',
                view === v
                  ? 'border-primary bg-primary/10 text-primary'
                  : 'border-border bg-card text-muted-foreground hover:text-foreground'
              )}
            >
              {v}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
        <CoherenceGauge
          score={summary.coherence_score}
          documentsAnalyzed={summary.document_count}
          dataPointsChecked={summary.alert_count}
        />
        <div className="rounded-md border bg-card p-5 shadow-sm">
          {view === 'breakdown' && <BreakdownChart data={barData} />}
          {view === 'radar' && <RadarView data={radarData} />}
          {view === 'alerts' && (
            <AlertsDistribution
              critical={0}
              high={0}
              medium={summary.alert_count}
              low={0}
            />
          )}
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-sm font-semibold">Sub-Category Breakdown</h3>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {catEntries.map(([cat, score]) => (
            <ScoreCard
              key={cat}
              category={cat}
              score={score}
              weight={summary.weights_used[cat] ?? 0}
              alertCount={0}
              selected={selectedCat === cat}
              onClick={() =>
                setSelectedCat(selectedCat === cat ? null : cat)
              }
            />
          ))}
        </div>
      </div>

      {selectedCat && summary.sub_scores[selectedCat] != null && (
        <CategoryDetail
          category={selectedCat}
          score={summary.sub_scores[selectedCat]}
          weight={summary.weights_used[selectedCat] ?? 0}
          alertCount={0}
          trend={[]}
          onClose={() => setSelectedCat(null)}
        />
      )}
    </>
  );
}
