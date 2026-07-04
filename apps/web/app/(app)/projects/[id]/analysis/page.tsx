"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertTriangle, Gauge, RadioTower, Wallet } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useListProjectAlertsApiV1ProjectsProjectIdAlertsGet } from "@/lib/api/generated/alerts/alerts";
import { useGetCoherenceDashboardApiCoherenceDashboardProjectIdGet } from "@/lib/api/generated/coherence-dashboard/coherence-dashboard";
import { getStreamProjectProcessingUrl } from "@/lib/api/analysis-stream";

/**
 * Test Suite ID: TASK-1347, TASK-OPS-DOCFLOW-010
 * Route Coverage: Project analysis route uses generated backend queries.
 */
export default function AnalysisPage() {
  const params = useParams<{ id: string }>();
  const id = params.id;

  const {
    data: dashboard,
    isLoading: dashboardLoading,
    error: dashboardError,
  } = useGetCoherenceDashboardApiCoherenceDashboardProjectIdGet(id);
  const {
    data: alertsResponse,
    isLoading: alertsLoading,
    error: alertsError,
  } = useListProjectAlertsApiV1ProjectsProjectIdAlertsGet(id, undefined);

  if (dashboardLoading || alertsLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        Loading analysis summary...
      </div>
    );
  }

  if (dashboardError || alertsError || !dashboard) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive">
        {(dashboardError instanceof Error && dashboardError.message) ||
          (alertsError instanceof Error && alertsError.message) ||
          "Failed to load analysis summary"}
      </div>
    );
  }

  const alerts = alertsResponse?.items ?? [];
  const openAlerts = alerts.filter((alert) => alert.status === "open");
  const coherenceScore =
    typeof dashboard.coherence_score === "number"
      ? dashboard.coherence_score
      : Number(dashboard.coherence_score ?? 0);
  const documentCount =
    typeof dashboard.document_count === "number"
      ? dashboard.document_count
      : Number(dashboard.document_count ?? 0);
  const subScores =
    dashboard.sub_scores && typeof dashboard.sub_scores === "object"
      ? (dashboard.sub_scores as Record<string, number | null | undefined>)
      : {};
  const scoreVersion =
    typeof (dashboard as { score_version?: unknown }).score_version === "string"
      ? (dashboard as { score_version: string }).score_version
      : null;
  const missingDimensions = Array.isArray(
    (dashboard as { score_missing_dimensions?: unknown })
      .score_missing_dimensions,
  )
    ? (dashboard as { score_missing_dimensions: unknown[] })
        .score_missing_dimensions.filter(
          (dimension): dimension is string => typeof dimension === "string",
        )
    : [];
  const budgetScore =
    typeof subScores["BUDGET"] === "number" ? subScores["BUDGET"] : null;
  const budgetValue = budgetScore === null ? "—" : String(budgetScore);
  const budgetTitle =
    budgetScore === null ? "Requires budget document" : undefined;
  const recentAlerts = openAlerts.slice(0, 3).map((alert) => ({
    severity: alert.severity,
    title: alert.message.split(" — ")[0],
  }));
  const formattedScoreVersion = scoreVersion?.replace(/_/g, " ");

  const statCards = [
    {
      label: "Coherence Score",
      value: String(coherenceScore),
      icon: Gauge,
      tone: "text-primary",
    },
    {
      label: "Open Alerts",
      value: String(openAlerts.length),
      icon: AlertTriangle,
      tone: "text-warning",
    },
    {
      label: "Documents Analyzed",
      value: String(documentCount),
      icon: RadioTower,
      tone: "text-chart-quality",
    },
    {
      label: "Budget coherence",
      value: budgetValue,
      title: budgetTitle,
      icon: Wallet,
      tone: "text-chart-budget",
    },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Analysis Summary
          </h1>
          <p className="text-sm text-muted-foreground">
            Live backend-backed view of coherence, alerts, and analysis entry
            points for this project.
          </p>
        </div>
        <Button asChild variant="outline">
          <Link href={getStreamProjectProcessingUrl(id)}>
            Open Processing Stream
          </Link>
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {statCards.map((stat) => {
          const Icon = stat.icon;

          return (
            <Card key={stat.label}>
              <CardContent className="flex items-center gap-4 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                  <Icon className={`h-5 w-5 ${stat.tone}`} strokeWidth={1.5} />
                </div>
                <div>
                  <div className="text-xs font-medium text-muted-foreground">
                    {stat.label}
                  </div>
                  <div className="font-mono text-2xl font-bold">
                    <span title={stat.title}>{stat.value}</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-5 lg:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">
              Analysis Posture
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2">
              <span>Current coherence</span>
              <span className="font-mono font-semibold text-foreground">
                {coherenceScore}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2">
              <span>Open remediation items</span>
              <span className="font-mono font-semibold text-foreground">
                {openAlerts.length}
              </span>
            </div>
            <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2">
              <span>Document coverage</span>
              <span className="font-mono font-semibold text-foreground">
                {documentCount}
              </span>
            </div>
            {formattedScoreVersion ? (
              <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2">
                <span>Score version</span>
                <Badge variant="outline" className="capitalize">
                  {formattedScoreVersion}
                </Badge>
              </div>
            ) : null}
            {missingDimensions.length > 0 ? (
              <p className="rounded-md border border-warning/30 bg-warning/10 px-3 py-2 text-warning-foreground">
                Missing evidence: {missingDimensions.join(", ")}
              </p>
            ) : null}
            <p>
              Use the processing stream link to watch the project pipeline emit
              live analysis state from the backend.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">
              Recent Alert Signals
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {recentAlerts.length > 0 ? (
              recentAlerts.map((alert) => (
                <div
                  key={`${alert.severity}-${alert.title}`}
                  className="flex items-center justify-between rounded-md border px-3 py-2"
                >
                  <span className="text-sm text-foreground">{alert.title}</span>
                  <Badge variant="outline" className="capitalize">
                    {alert.severity}
                  </Badge>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">
                No active alert signals for this project.
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
