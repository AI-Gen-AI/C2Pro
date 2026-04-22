"use client";

import type { AICostAnalytics } from "@/lib/api/contracts";

type Props = {
  data: AICostAnalytics;
  loading: boolean;
  error: string | null;
};

export function CostDashboard({ data, loading, error }: Props) {
  if (loading) return <div className="rounded-md border p-4 text-sm text-muted-foreground">Loading cost analytics…</div>;
  if (error) return <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>;
  if (data.series.length === 0) return <div className="rounded-md border p-4 text-sm text-muted-foreground">No cost data in selected timeframe.</div>;

  const maxCost = Math.max(...data.series.map((item) => item.total_cost), 0.01);

  return (
    <section className="space-y-3 rounded-md border p-4">
      <h2 className="text-lg font-semibold">Cost Dashboard</h2>
      <div className="grid gap-3 md:grid-cols-3 text-sm">
        <div>Total Cost: <strong>${data.summary.total_cost.toFixed(4)}</strong></div>
        <div>Total Tokens: <strong>{data.summary.total_tokens.toLocaleString()}</strong></div>
        <div>Total Requests: <strong>{data.summary.total_requests.toLocaleString()}</strong></div>
      </div>
      <div className="space-y-2">
        {data.series.map((point) => (
          <div key={`${point.bucket}-${point.model}-${point.prompt_version}`} className="space-y-1">
            <div className="flex justify-between text-xs text-muted-foreground">
              <span>{point.bucket ? new Date(point.bucket).toLocaleDateString() : "Unknown"} · {point.model} · {point.prompt_version}</span>
              <span>${point.total_cost.toFixed(4)}</span>
            </div>
            <div className="h-2 rounded bg-muted">
              <div className="h-2 rounded bg-primary" style={{ width: `${(point.total_cost / maxCost) * 100}%` }} />
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
