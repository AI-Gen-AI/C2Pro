"use client";

import type { AIQualityDrift } from "@/lib/api/contracts";

type Props = {
  data: AIQualityDrift;
  loading: boolean;
  error: string | null;
};

export function DriftDetector({ data, loading, error }: Props) {
  if (loading) return <div className="rounded-md border p-4 text-sm text-muted-foreground">Loading drift signals…</div>;
  if (error) return <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>;
  if (data.series.length === 0) return <div className="rounded-md border p-4 text-sm text-muted-foreground">No drift telemetry available.</div>;

  return (
    <section className="space-y-3 rounded-md border p-4">
      <h2 className="text-lg font-semibold">Drift Detector</h2>
      {data.alerts.length === 0 ? (
        <p className="text-sm text-muted-foreground">No active drift alerts.</p>
      ) : (
        <ul className="space-y-2">
          {data.alerts.map((alert, idx) => (
            <li key={`${alert.operation}-${alert.type}-${idx}`} className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-sm">
              <strong>{alert.operation}</strong>: {alert.message}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
