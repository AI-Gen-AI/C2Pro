'use client';

import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import {
  Gauge,
  AlertTriangle,
  FileText,
  DollarSign,
  ArrowRight,
} from 'lucide-react';
import { useGetCoherenceDashboardApiCoherenceDashboardProjectIdGet } from '@/lib/api/generated/coherence-dashboard/coherence-dashboard';
import { useListProjectAlertsApiV1ProjectsProjectIdAlertsGet } from '@/lib/api/generated/alerts/alerts';
import { useProject } from '@/hooks/useProject';
import { useProjectDocuments } from '@/hooks/useProjectDocuments';
import { TripletChecklist } from '@/components/features/documents/TripletChecklist';

type DashboardScoreSource = {
  sub_scores?: unknown;
};

function numberValue(value: unknown) {
  return typeof value === 'number' ? value : Number(value ?? 0);
}

function objectValue(value: unknown) {
  return value && typeof value === 'object'
    ? (value as Record<string, number | null | undefined>)
    : {};
}

function errorMessage(dashboardError: unknown, alertsError: unknown) {
  if (dashboardError instanceof Error && dashboardError.message) {
    return dashboardError.message;
  }

  if (alertsError instanceof Error && alertsError.message) {
    return alertsError.message;
  }

  return 'Failed to load project overview';
}

function alertDotClass(severity: string | null | undefined) {
  if (severity === 'critical') {
    return 'bg-destructive animate-pulse-critical';
  }

  if (severity === 'high') {
    return 'bg-warning';
  }

  return 'bg-warning/60';
}

function alertBadgeVariant(severity: string | null | undefined) {
  if (severity === 'critical') {
    return 'destructive';
  }

  if (severity === 'high') {
    return 'warning';
  }

  return 'secondary';
}

/**
 * Test Suite ID: TASK-1347
 * Route Coverage: Project overview route uses generated backend queries.
 */
export default function ProjectOverviewPage() {
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
  const { data: project } = useProject(id);
  const { documents } = useProjectDocuments(id);

  const isLoading = dashboardLoading || alertsLoading;
  const hasError = dashboardError || !dashboard;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        Loading project overview…
      </div>
    );
  }

  if (hasError) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive">
        {errorMessage(dashboardError, alertsError)}
      </div>
    );
  }

  const alerts = alertsResponse?.items ?? [];
  const openAlerts = alerts.filter((alert) => alert.status === 'open');
  const alertsUnavailable = Boolean(alertsError);
  
  const coherenceScore = numberValue(dashboard.coherence_score);
  const documentCount = numberValue(dashboard.document_count);
  const subScores = objectValue((dashboard as DashboardScoreSource).sub_scores);
  const budgetScore =
    typeof subScores['BUDGET'] === 'number' ? subScores['BUDGET'] : null;
  const budgetValue = budgetScore === null ? '—' : String(budgetScore);
  const budgetTitle =
    budgetScore === null ? 'Requires budget document' : undefined;

  const openAlertCount = alertsUnavailable
    ? Number(dashboard.alert_count ?? 0)
    : openAlerts.length;

  const recentAlerts = openAlerts.slice(0, 3).map((alert) => ({
    id: alert.id,
    severity: alert.severity,
    title: alert.message.split(' — ')[0],
  }));

  const statCards = [
    { label: 'Coherence Score', value: String(coherenceScore), icon: Gauge, color: 'text-primary' },
    { label: 'Open Alerts', value: String(openAlertCount), icon: AlertTriangle, color: 'text-warning' },
    { label: 'Documents', value: String(documentCount), icon: FileText, color: 'text-chart-quality' },
    { label: 'Budget coherence', value: budgetValue, title: budgetTitle, icon: DollarSign, color: 'text-chart-budget' },
  ];

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {statCards.map((stat) => {
          const Icon = stat.icon;
          return (
            <Card key={stat.label} className="card-interactive">
              <CardContent className="flex items-center gap-4 p-4">
                <div className="flex h-10 w-10 items-center justify-center rounded-md bg-muted">
                  <Icon className={`h-5 w-5 ${stat.color}`} strokeWidth={1.5} />
                </div>
                <div>
                  <p className="text-xs font-medium text-muted-foreground">{stat.label}</p>
                  <p className="font-mono text-2xl font-bold" title={stat.title}>
                    {stat.value}
                  </p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <TripletChecklist documents={documents} compact />

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">Project Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            {project?.status ? (
              <div className="flex justify-between">
                <span>Status</span>
                <Badge variant="default">{project.status}</Badge>
              </div>
            ) : null}
            <div className="flex justify-between">
              <span>Budget coherence</span>
              <span
                className="font-mono font-medium text-foreground"
                title={budgetTitle}
              >
                {budgetValue}
              </span>
            </div>
            {budgetScore === null ? null : (
              <Progress value={budgetScore} className="h-1.5" />
            )}
            <div className="flex justify-between">
              <span>Coherence Score</span>
              <span className="font-mono font-medium text-foreground">{coherenceScore}</span>
            </div>
            <Progress value={coherenceScore} className="h-1.5" />
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-semibold">Recent Alerts</CardTitle>
              <Link
                href={`/projects/${id}/alerts`}
                className="flex items-center gap-1 text-xs font-medium text-primary hover:underline"
              >
                View All <ArrowRight className="h-3 w-3" />
              </Link>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            {alertsUnavailable ? (
              <p className="text-sm text-muted-foreground">
                Recent alerts unavailable right now.
              </p>
            ) : null}
            {recentAlerts.map((alert) => (
              <div
                key={alert.id}
                className="flex items-center gap-3 rounded-md border p-2.5 text-sm"
              >
                <div
                  className={`h-2 w-2 shrink-0 rounded-full ${alertDotClass(
                    alert.severity,
                  )}`}
                />
                <span className="flex-1 text-sm">{alert.title}</span>
                <Badge
                  variant={alertBadgeVariant(alert.severity)}
                  className="text-[10px]"
                >
                  {alert.severity}
                </Badge>
              </div>
            ))}
            {!alertsUnavailable && recentAlerts.length === 0 ? (
              <p className="text-sm text-muted-foreground">No open alerts</p>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

