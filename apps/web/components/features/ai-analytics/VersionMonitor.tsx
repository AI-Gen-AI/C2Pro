"use client";

import { useState } from "react";
import type { AIVersionPerformance } from "@/lib/api/contracts";

type Props = {
  data: AIVersionPerformance;
  loading: boolean;
  error: string | null;
};

export function VersionMonitor({ data, loading, error }: Props) {
  const [dateRange, setDateRange] = useState<{ start: string; end: string } | null>(null);

  if (loading) return <div className="rounded-md border p-4 text-sm text-muted-foreground">Loading version performance…</div>;
  if (error) return <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>;
  if (data.versions.length === 0) return <div className="rounded-md border p-4 text-sm text-muted-foreground">No prompt versions found.</div>;

  const windowStart = data.window_start ? new Date(data.window_start) : null;
  const filteredVersions = dateRange
    ? data.versions.filter(() => {
        if (!windowStart) return true;
        const versionDate = windowStart;
        return versionDate >= new Date(dateRange.start) && versionDate <= new Date(dateRange.end);
      })
    : data.versions;

  const handleDateRangeChange = (field: "start" | "end", value: string) => {
    setDateRange((prev) => ({
      start: prev?.start ?? "",
      end: prev?.end ?? "",
      [field]: value,
    }));
  };

  return (
    <section className="space-y-3 rounded-md border p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Version Monitor</h2>
        <div className="flex items-center gap-2 text-sm">
          <label htmlFor="version-date-start" className="text-muted-foreground">From:</label>
          <input
            id="version-date-start"
            type="date"
            value={dateRange?.start ?? ""}
            onChange={(e) => handleDateRangeChange("start", e.target.value)}
            className="rounded border bg-background px-2 py-1"
          />
          <label htmlFor="version-date-end" className="text-muted-foreground">To:</label>
          <input
            id="version-date-end"
            type="date"
            value={dateRange?.end ?? ""}
            onChange={(e) => handleDateRangeChange("end", e.target.value)}
            className="rounded border bg-background px-2 py-1"
          />
          {dateRange && (
            <button
              onClick={() => setDateRange(null)}
              className="text-muted-foreground hover:text-foreground"
            >
              Clear
            </button>
          )}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th>Tag</th><th>Version</th><th>Runs</th><th>Success</th><th>Feedback</th><th>Latency</th><th>Cost</th>
            </tr>
          </thead>
          <tbody>
            {filteredVersions.map((row) => (
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
