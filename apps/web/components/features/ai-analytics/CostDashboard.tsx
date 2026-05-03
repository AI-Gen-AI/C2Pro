"use client";

import type { AICostAnalytics } from "@/lib/api/contracts";

type Props = {
  data: AICostAnalytics;
  loading: boolean;
  error: string | null;
};

const PIE_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

function calculatePieSlices(series: AICostAnalytics["series"]) {
  const modelCostMap = new Map<string, number>();
  for (const point of series) {
    const current = modelCostMap.get(point.model) ?? 0;
    modelCostMap.set(point.model, current + point.total_cost);
  }

  const entries = Array.from(modelCostMap.entries()).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, cost]) => sum + cost, 0);

  let currentAngle = 0;
  return entries.map(([model, cost], idx) => {
    const percentage = total > 0 ? (cost / total) * 100 : 0;
    const angle = (cost / total) * 360;
    const startAngle = currentAngle;
    currentAngle += angle;
    return { model, cost, percentage, startAngle, color: PIE_COLORS[idx % PIE_COLORS.length] };
  });
}

function describeArc(x: number, y: number, radius: number, startAngle: number, endAngle: number) {
  const start = polarToCartesian(x, y, radius, endAngle);
  const end = polarToCartesian(x, y, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return `M ${x} ${y} L ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 0 ${end.x} ${end.y} Z`;
}

function polarToCartesian(x: number, y: number, radius: number, angleInDegrees: number) {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180;
  return { x: x + radius * Math.cos(angleInRadians), y: y + radius * Math.sin(angleInRadians) };
}

export function CostDashboard({ data, loading, error }: Props) {
  if (loading) return <div className="rounded-md border p-4 text-sm text-muted-foreground">Loading cost analytics…</div>;
  if (error) return <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>;
  if (data.series.length === 0) return <div className="rounded-md border p-4 text-sm text-muted-foreground">No cost data in selected timeframe.</div>;

  const maxCost = Math.max(...data.series.map((item) => item.total_cost), 0.01);
  const slices = calculatePieSlices(data.series);

  return (
    <section className="space-y-3 rounded-md border p-4">
      <h2 className="text-lg font-semibold">Cost Dashboard</h2>
      <div className="grid gap-3 md:grid-cols-3 text-sm">
        <div>Total Cost: <strong>${data.summary.total_cost.toFixed(4)}</strong></div>
        <div>Total Tokens: <strong>{data.summary.total_tokens.toLocaleString()}</strong></div>
        <div>Total Requests: <strong>{data.summary.total_requests.toLocaleString()}</strong></div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
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
        {slices.length > 0 && (
          <div className="flex flex-col items-center">
            <svg viewBox="0 0 100 100" className="w-40 h-40">
              {slices.map((slice, idx) => {
                const radius = 40;
                const center = 50;
                const endAngle = slice.startAngle + (slice.percentage / 100) * 360;
                const path = slice.percentage === 100
                  ? `M ${center} ${center - radius} A ${radius} ${radius} 0 1 1 ${center - 0.001} ${center - radius} Z`
                  : describeArc(center, center, radius, slice.startAngle, endAngle);
                return <path key={idx} d={path} fill={slice.color} />;
              })}
            </svg>
            <div className="flex flex-wrap gap-2 justify-center mt-2 text-xs">
              {slices.map((slice, idx) => (
                <div key={idx} className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded-full" style={{ backgroundColor: slice.color }} />
                  <span>{slice.model} ({slice.percentage.toFixed(1)}%)</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
