"use client";

import type { AIVersionPerformance } from "@/lib/api/contracts";

type Props = {
  data: AIVersionPerformance;
  loading: boolean;
  error: string | null;
};

export function VersionMonitor({ data, loading, error }: Props) {
  if (loading) return <div className="rounded-md border p-4 text-sm text-muted-foreground">Loading version performance…</div>;
  if (error) return <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>;
  if (data.versions.length === 0) return <div className="rounded-md border p-4 text-sm text-muted-foreground">No prompt versions found.</div>;

  return (
    <section className="space-y-3 rounded-md border p-4">
      <h2 className="text-lg font-semibold">Version Monitor</h2>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th>Tag</th><th>Version</th><th>Runs</th><th>Success</th><th>Feedback</th><th>Latency</th><th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {data.versions.map((row) => (
              <tr key={`${row.prompt_tag}-${row.prompt_version}`} className="border-t">
                <td>{row.prompt_tag}</td>
                <td>{row.prompt_version}</td>
                <td>{row.total_runs}</td>
                <td>{(row.success_rate * 100).toFixed(1)}%</td>
                <td>{row.feedback_count > 0 ? row.avg_feedback_score.toFixed(2) : "—"}</td>
                <td>{row.avg_latency_ms.toFixed(0)} ms</td>
                <td>${row.total_cost.toFixed(4)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
