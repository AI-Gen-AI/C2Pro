"use client";

import { useParams } from "next/navigation";
import { AlertTriangle, Gauge, RadioTower, Wallet } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { AnalysisProgressTracker } from "@/components/features/analysis/AnalysisProgressTracker";
import {
  SingleDocumentHealth,
  coherenceSubscoreIsIncorporated,
} from "@/components/features/health/SingleDocumentHealth";
import { deriveTripletChecklist } from "@/components/features/documents/TripletChecklist";
import { useProjectCoherenceActions } from "@/hooks/useProjectCoherenceActions";
import { useProjectDocuments } from "@/hooks/useProjectDocuments";
import { useListProjectAlertsApiV1AlertsProjectsProjectIdGet } from "@/lib/api/generated/alerts/alerts";
import { useGetCoherenceDashboardApiCoherenceDashboardProjectIdGet } from "@/lib/api/generated/coherence-dashboard/coherence-dashboard";
import { useGetProjectHealthApiV1ProjectsProjectIdHealthGet } from "@/lib/api/generated/project-health/project-health";
import type { AlertResponse } from "@/lib/api/generated/models";

type DashboardExtras = {
  score_version?: unknown;
  score_missing_dimensions?: unknown;
};

function numberValue(value: unknown) {
  return typeof value === "number" ? value : Number(value ?? 0);
}

function objectValue(value: unknown) {
  return value && typeof value === "object"
    ? (value as Record<string, number | null | undefined>)
    : {};
}

function stringArrayValue(value: unknown) {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function errorMessage(
  dashboardError: unknown,
  alertsError: unknown,
) {
  if (dashboardError instanceof Error && dashboardError.message) {
    return dashboardError.message;
  }

  if (alertsError instanceof Error && alertsError.message) {
    return alertsError.message;
  }

  return "Failed to load analysis summary";
}

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
  // INV-COH: a Coherence number may be shown ONLY on positive evidence that a subscore
  // was actually incorporated. Absence of that evidence — for ANY reason — is not
  // permission to show one, so loading and error suppress the readouts too rather than
  // falling through to the legacy dashboard number.
  const {
    data: healthVector,
    isLoading: healthLoading,
    isError: healthErrored,
  } = useGetProjectHealthApiV1ProjectsProjectIdHealthGet(id);
  const showCoherence = coherenceSubscoreIsIncorporated(healthVector);
  // Why it is suppressed. Only a LOADED vector lacking the evidence licenses the
  // "needs a second document" claim; loading or an error means we simply do not know,
  // and inferring "single document" from a failed request would fabricate a finding.
  // "insufficient_evidence", not "single_document": eligibility is a property of
  // the evidence, not the file count. One document can carry several reconcilable
  // claims; two unrelated documents can carry none.
  const coherenceSuppressionReason: "loading" | "unverified" | "insufficient_evidence" =
    healthLoading
      ? "loading"
      : !healthErrored && healthVector != null
        ? "insufficient_evidence"
        : "unverified";
  const {
    data: alertsResponse,
    isLoading: alertsLoading,
    error: alertsError,
  } = useListProjectAlertsApiV1AlertsProjectsProjectIdGet(id, undefined);
  const { documents } = useProjectDocuments(id);
  const { rerunAnalysis, isRerunningAnalysis } = useProjectCoherenceActions(id);
  const triplet = deriveTripletChecklist(documents);

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
        {errorMessage(dashboardError, alertsError)}
      </div>
    );
  }

  const alerts = alertsResponse?.items ?? [];
  const openAlerts = alerts.filter((alert: AlertResponse) => alert.status === "open");
  const coherenceScore = numberValue(dashboard.coherence_score);
  const documentCount = numberValue(dashboard.document_count);
  const subScores = objectValue(dashboard.sub_scores);
  const dashboardExtras = dashboard as DashboardExtras;
  const scoreVersion =
    typeof dashboardExtras.score_version === "string"
      ? dashboardExtras.score_version
      : null;
  const missingDimensions = stringArrayValue(
    dashboardExtras.score_missing_dimensions,
  );
  const budgetScore =
    typeof subScores["BUDGET"] === "number" ? subScores["BUDGET"] : null;
  const budgetValue = budgetScore === null ? "—" : String(budgetScore);
  const budgetTitle =
    budgetScore === null ? "Requires budget document" : undefined;
  const recentAlerts = openAlerts.slice(0, 3).map((alert: AlertResponse) => ({
    severity: alert.severity,
    title: alert.message.split(" — ")[0],
  }));
  const formattedScoreVersion = scoreVersion?.replaceAll("_", " ");

  const statCards = [
    ...(showCoherence
      ? [
          {
            label: "Coherence Score",
            value: String(coherenceScore),
            icon: Gauge,
            tone: "text-primary",
          },
        ]
      : []),
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
        <div className="space-y-2">
          <Button
            type="button"
            className="rounded-xl"
            disabled={!triplet.complete || isRerunningAnalysis}
            title={
              triplet.complete
                ? undefined
                : "Upload contract, budget, and schedule before re-running analysis."
            }
            onClick={() => void rerunAnalysis()}
          >
            {isRerunningAnalysis ? "Re-running..." : "Re-run analysis"}
          </Button>
          {!triplet.complete ? (
            <p className="max-w-xs text-xs text-muted-foreground">
              Upload contract, budget, and schedule before re-running analysis.
            </p>
          ) : null}
        </div>
      </div>

      <AnalysisProgressTracker projectId={id} />

      <SingleDocumentHealth projectId={id} />

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
            {showCoherence ? (
              <div className="flex items-center justify-between rounded-md border bg-muted/30 px-3 py-2">
                <span>Current coherence</span>
                <span
                  data-testid="analysis-coherence-score"
                  className="font-mono font-semibold text-foreground"
                >
                  {coherenceScore}
                </span>
              </div>
            ) : (
              <p
                data-testid="analysis-coherence-unavailable"
                data-reason={coherenceSuppressionReason}
                className="rounded-md border bg-muted/30 px-3 py-2 text-xs"
              >
                {coherenceSuppressionReason === "loading"
                  ? "Checking whether Coherence is available for this project…"
                  : coherenceSuppressionReason === "unverified"
                    ? "Coherence availability could not be verified."
                    : "Coherence becomes available when there is enough reconcilable evidence to evaluate consistency. This analysis has not produced enough yet."}
              </p>
            )}
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
