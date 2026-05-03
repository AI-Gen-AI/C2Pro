"use client";

import { useState, useMemo } from "react";
import type { AIUsageMetric } from "@/lib/api/contracts";

type Props = {
  metrics: AIUsageMetric[];
  loading: boolean;
  error: string | null;
};

type SortKey = "timestamp" | "model" | "total_tokens" | "cost" | "latency_ms" | "trace_url";
type SortDirection = "asc" | "desc";

function sortMetrics(data: AIUsageMetric[], key: SortKey, direction: SortDirection): AIUsageMetric[] {
  return [...data].sort((a, b) => {
    let aVal: string | number | null;
    let bVal: string | number | null;

    switch (key) {
      case "timestamp":
        aVal = a.timestamp;
        bVal = b.timestamp;
        break;
      case "model":
        aVal = a.model;
        bVal = b.model;
        break;
      case "total_tokens":
        aVal = a.total_tokens;
        bVal = b.total_tokens;
        break;
      case "cost":
        aVal = a.cost;
        bVal = b.cost;
        break;
      case "latency_ms":
        aVal = a.latency_ms;
        bVal = b.latency_ms;
        break;
      case "trace_url":
        aVal = a.trace_url ?? "";
        bVal = b.trace_url ?? "";
        break;
      default:
        return 0;
    }

    if (aVal === null || aVal === undefined) return 1;
    if (bVal === null || bVal === undefined) return -1;

    if (typeof aVal === "string" && typeof bVal === "string") {
      return direction === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    }

    const numA = Number(aVal);
    const numB = Number(bVal);
    return direction === "asc" ? numA - numB : numB - numA;
  });
}

function convertToCSV(metrics: AIUsageMetric[]): string {
  const headers = ["Timestamp", "Model", "Prompt Version", "Input Tokens", "Output Tokens", "Total Tokens", "Cost ($)", "Latency (ms)", "Trace URL"];
  const rows = metrics.map((m) => [
    m.timestamp,
    m.model,
    m.prompt_version,
    m.input_tokens.toString(),
    m.output_tokens.toString(),
    m.total_tokens.toString(),
    m.cost.toFixed(4),
    m.latency_ms.toFixed(0),
    m.trace_url ?? "",
  ]);

  const escapeCSV = (val: string) => {
    if (val.includes(",") || val.includes('"') || val.includes("\n")) {
      return `"${val.replace(/"/g, '""')}"`;
    }
    return val;
  };

  return [headers.join(","), ...rows.map((row) => row.map(escapeCSV).join(","))].join("\n");
}

export function UsageMetricsTable({ metrics, loading, error }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>("timestamp");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");

  const sortedMetrics = useMemo(
    () => sortMetrics(metrics, sortKey, sortDirection),
    [metrics, sortKey, sortDirection],
  );

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDirection((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDirection("asc");
    }
  };

  const handleExportCSV = () => {
    const csv = convertToCSV(sortedMetrics);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `ai-usage-metrics-${new Date().toISOString().split("T")[0]}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const getSortIndicator = (key: SortKey) => {
    if (sortKey !== key) return null;
    return sortDirection === "asc" ? " ↑" : " ↓";
  };

  if (loading) return <div className="rounded-md border p-4 text-sm text-muted-foreground">Loading usage metrics…</div>;
  if (error) return <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">{error}</div>;
  if (metrics.length === 0) return <div className="rounded-md border p-4 text-sm text-muted-foreground">No usage metrics available.</div>;

  return (
    <section className="space-y-3 rounded-md border p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Usage Metrics</h2>
        <button
          onClick={handleExportCSV}
          className="rounded bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/90"
        >
          Export CSV
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead>
            <tr className="text-left text-muted-foreground">
              <th
                className="cursor-pointer hover:text-foreground"
                onClick={() => handleSort("timestamp")}
              >
                Timestamp{getSortIndicator("timestamp")}
              </th>
              <th
                className="cursor-pointer hover:text-foreground"
                onClick={() => handleSort("model")}
              >
                Model{getSortIndicator("model")}
              </th>
              <th>Version</th>
              <th
                className="cursor-pointer hover:text-foreground"
                onClick={() => handleSort("total_tokens")}
              >
                Tokens{getSortIndicator("total_tokens")}
              </th>
              <th
                className="cursor-pointer hover:text-foreground"
                onClick={() => handleSort("cost")}
              >
                Cost{getSortIndicator("cost")}
              </th>
              <th
                className="cursor-pointer hover:text-foreground"
                onClick={() => handleSort("latency_ms")}
              >
                Latency{getSortIndicator("latency_ms")}
              </th>
              <th
                className="cursor-pointer hover:text-foreground"
                onClick={() => handleSort("trace_url")}
              >
                Trace{getSortIndicator("trace_url")}
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedMetrics.map((row) => (
              <tr key={row.id} className="border-t">
                <td className="py-2">{row.timestamp ? new Date(row.timestamp).toLocaleString() : "—"}</td>
                <td className="py-2">{row.model}</td>
                <td className="py-2">{row.prompt_version}</td>
                <td className="py-2">{row.total_tokens.toLocaleString()}</td>
                <td className="py-2">${row.cost.toFixed(4)}</td>
                <td className="py-2">{row.latency_ms.toFixed(0)} ms</td>
                <td className="py-2">
                  {row.trace_url ? (
                    <a
                      href={row.trace_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      View Trace
                    </a>
                  ) : (
                    "—"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}