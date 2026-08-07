"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { env } from "@/config/env";
import {
  useGetRecentAnalysesApiV1ObservabilityAnalysesGet,
  useGetSystemStatusApiV1ObservabilityStatusGet,
} from "@/lib/api/generated/observability/observability";

export default function ObservabilityPage() {
  const router = useRouter();

  useEffect(() => {
    if (!env.FEATURE_INTERNAL_DASHBOARDS) {
      router.replace("/dashboard");
    }
  }, [router]);

  const {
    data: systemStatus,
    isLoading: systemStatusLoading,
    error: systemStatusError,
  } = useGetSystemStatusApiV1ObservabilityStatusGet({
    query: {
      refetchInterval: 30_000,
    },
  });
  const {
    data: recentAnalyses,
    isLoading: recentAnalysesLoading,
    error: recentAnalysesError,
  } = useGetRecentAnalysesApiV1ObservabilityAnalysesGet(undefined, {
    query: {
      refetchInterval: 30_000,
    },
  });

  const isLoading = systemStatusLoading || recentAnalysesLoading;
  const error = systemStatusError ?? recentAnalysesError;

  if (!env.FEATURE_INTERNAL_DASHBOARDS) return null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        Loading observability data...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive">
        {error instanceof Error ? error.message : "Failed to load observability data"}
      </div>
    );
  }

  const analyses = recentAnalyses?.analyses ?? [];

  return (
    <div className="mx-auto max-w-6xl space-y-8 rounded-lg border bg-card p-8 shadow-sm">
      <div className="border-b pb-3">
        <h1 className="text-3xl font-bold text-foreground">
          Observability Dashboard
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Live backend health and recent coherence execution telemetry.
        </p>
      </div>

      {systemStatus ? (
        <div className="rounded-md border bg-muted/30 p-6">
          <h2 className="mb-4 text-2xl font-semibold text-foreground">
            System Status
          </h2>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>
                <strong className="font-medium text-foreground">API Status:</strong>{" "}
                <span
                  className={
                    systemStatus.api_status === "OK"
                      ? "font-bold text-green-600"
                      : "font-bold text-red-600"
                  }
                >
                  {systemStatus.api_status}
                </span>
              </p>
              <p>
                <strong className="font-medium text-foreground">
                  Database Status:
                </strong>{" "}
                <span
                  className={
                    systemStatus.database_status === "OK"
                      ? "font-bold text-green-600"
                      : "font-bold text-red-600"
                  }
                >
                  {systemStatus.database_status}
                </span>
              </p>
            </div>
            <div className="text-sm text-muted-foreground">
              <strong className="font-medium text-foreground">Last Checked:</strong>{" "}
              {new Date(systemStatus.timestamp).toLocaleString()}
            </div>
          </div>
        </div>
      ) : null}

      {analyses.length > 0 ? (
        <div className="rounded-md border bg-muted/30 p-6">
          <h2 className="mb-4 text-2xl font-semibold text-foreground">
            Recent Coherence Analyses
          </h2>
          <div className="overflow-x-auto">
            <table className="min-w-full rounded-md border bg-background">
              <thead>
                <tr className="border-b bg-muted/50 text-left text-sm uppercase tracking-wide text-muted-foreground">
                  <th className="px-6 py-3">Analysis ID</th>
                  <th className="px-6 py-3">Project ID</th>
                  <th className="px-6 py-3">Status</th>
                  <th className="px-6 py-3">Score</th>
                  <th className="px-6 py-3">Alerts</th>
                  <th className="px-6 py-3">Started At</th>
                  <th className="px-6 py-3">Completed At</th>
                </tr>
              </thead>
              <tbody className="text-sm text-foreground">
                {analyses.map((analysis) => (
                  <tr key={analysis.id} className="border-b last:border-b-0">
                    <td className="px-6 py-3">{analysis.id}</td>
                    <td className="px-6 py-3">{analysis.project_id}</td>
                    <td className="px-6 py-3">{analysis.status}</td>
                    <td className="px-6 py-3">
                      {analysis.coherence_score ?? "N/A"}
                    </td>
                    <td className="px-6 py-3">{analysis.alerts_count}</td>
                    <td className="px-6 py-3">
                      {new Date(analysis.started_at).toLocaleString()}
                    </td>
                    <td className="px-6 py-3">
                      {analysis.completed_at
                        ? new Date(analysis.completed_at).toLocaleString()
                        : "N/A"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <p className="py-8 text-center text-lg text-muted-foreground">
          No observability data available.
        </p>
      )}
    </div>
  );
}
