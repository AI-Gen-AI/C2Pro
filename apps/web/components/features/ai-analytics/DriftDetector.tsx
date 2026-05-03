"use client";

import type { AIQualityDrift, AIQualityDriftPoint } from "@/lib/api/contracts";

type Props = {
  data: AIQualityDrift;
  loading: boolean;
  error: string | null;
};

function detectAnomalies(points: AIQualityDriftPoint[]): Set<number> {
  if (points.length < 3) return new Set();

  const feedbackScores = points.map((p) => p.avg_feedback_score).filter((s) => s !== null && !isNaN(s));
  const latencies = points.map((p) => p.avg_latency_ms).filter((l) => l !== null && !isNaN(l));

  const mean = (arr: number[]) => arr.reduce((a, b) => a + b, 0) / arr.length;
  const stdDev = (arr: number[]) => {
    const avg = mean(arr);
    return Math.sqrt(arr.reduce((sum, v) => sum + Math.pow(v - avg, 2), 0) / arr.length);
  };

  const feedbackMean = feedbackScores.length > 0 ? mean(feedbackScores) : 0;
  const feedbackStd = feedbackScores.length > 0 ? stdDev(feedbackScores) : 0;
  const latencyMean = latencies.length > 0 ? mean(latencies) : 0;
  const latencyStd = latencies.length > 0 ? stdDev(latencies) : 0;

  const anomalies = new Set<number>();
  points.forEach((point, idx) => {
    if (feedbackStd > 0 && point.avg_feedback_score !== null && Math.abs(point.avg_feedback_score - feedbackMean) > 1.5 * feedbackStd) {
      anomalies.add(idx);
    }
    if (latencyStd > 0 && point.avg_latency_ms !== null && Math.abs(point.avg_latency_ms - latencyMean) > 1.5 * latencyStd) {
      anomalies.add(idx);
    }
  });

  return anomalies;
}

export function DriftDetector({ data, loading, error }: Props) {
  if (loading) return <div className="rounded-md border p-4 text-sm text-muted-foreground">Loading drift signals…</div>;
  if (error) return <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>;
  if (data.series.length === 0) return <div className="rounded-md border p-4 text-sm text-muted-foreground">No drift telemetry available.</div>;

  const anomalyIndices = detectAnomalies(data.series);
  const hasAnomalies = anomalyIndices.size > 0;

  return (
    <section className="space-y-3 rounded-md border p-4">
      <h2 className="text-lg font-semibold">Drift Detector</h2>
      <div className="space-y-2">
        {data.series.map((point, idx) => {
          const isAnomaly = anomalyIndices.has(idx);
          return (
            <div
              key={`${point.bucket}-${point.operation}-${idx}`}
              className={`flex items-center justify-between rounded border p-2 text-sm ${
                isAnomaly ? "border-red-500/50 bg-red-500/5" : "border-muted"
              }`}
            >
              <div className="flex items-center gap-2">
                {isAnomaly && (
                  <span className="flex h-5 w-5 items-center justify-center rounded-full bg-red-500 text-xs text-white" title="Anomaly detected">
                    !
                  </span>
                )}
                <span className="font-medium">{point.operation}</span>
                <span className="text-muted-foreground">
                  {point.bucket ? new Date(point.bucket).toLocaleDateString() : "Unknown"}
                </span>
              </div>
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span>Score: {point.avg_feedback_score?.toFixed(2) ?? "—"}</span>
                <span>Latency: {point.avg_latency_ms?.toFixed(0) ?? "—"} ms</span>
                <span>Runs: {point.run_count}</span>
              </div>
            </div>
          );
        })}
      </div>
      {data.alerts.length > 0 && (
        <div className="mt-4">
          <h3 className="text-sm font-semibold">Alerts</h3>
          <ul className="mt-2 space-y-2">
            {data.alerts.map((alert, idx) => (
              <li key={`${alert.operation}-${alert.type}-${idx}`} className="rounded border border-amber-500/40 bg-amber-500/10 p-2 text-sm">
                <strong>{alert.operation}</strong>: {alert.message}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
