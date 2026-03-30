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

  if (dashboardLoading || alertsLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        Loading project overview…
      </div>
    );
  }

  if (dashboardError || alertsError || !dashboard) {
    return (
      <div className="flex items-center justify-center py-24 text-destructive">
        {(dashboardError instanceof Error && dashboardError.message) ||
          (alertsError instanceof Error && alertsError.message) ||
          'Failed to load project overview'}
      </div>
    );
  }

  const alerts = alertsResponse?.items ?? [];
  const openAlerts = alerts.filter((alert) => alert.status === 'open');
  const budgetScore = dashboard.sub_scores?.BUDGET ?? 0;
  const recentAlerts = openAlerts.slice(0, 3).map((alert) => ({
    severity: alert.severity,
    title: alert.message.split(' — ')[0],
  }));

  const statCards = [
    { label: 'Coherence Score', value: String(dashboard.coherence_score), icon: Gauge, color: 'text-primary' },
    { label: 'Open Alerts', value: String(openAlerts.length), icon: AlertTriangle, color: 'text-warning' },
    { label: 'Documents', value: String(dashboard.document_count), icon: FileText, color: 'text-chart-quality' },
    { label: 'Budget Used', value: `${100 - budgetScore}%`, icon: DollarSign, color: 'text-chart-budget' },
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
                  <p className="font-mono text-2xl font-bold">{stat.value}</p>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-semibold">Project Summary</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm text-muted-foreground">
            <div className="flex justify-between">
              <span>Status</span>
              <Badge variant="default">Active</Badge>
            </div>
            <div className="flex justify-between">
              <span>Budget Utilization</span>
              <span className="font-mono font-medium text-foreground">{100 - budgetScore}%</span>
            </div>
            <Progress value={100 - budgetScore} className="h-1.5" />
            <div className="flex justify-between">
              <span>Coherence Score</span>
              <span className="font-mono font-medium text-foreground">{dashboard.coherence_score}</span>
            </div>
            <Progress value={dashboard.coherence_score} className="h-1.5" />
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
            {recentAlerts.map((alert, i) => (
              <div key={i} className="flex items-center gap-3 rounded-md border p-2.5 text-sm">
                <div className={`h-2 w-2 shrink-0 rounded-full ${
                  alert.severity === 'critical' ? 'bg-destructive animate-pulse-critical' :
                  alert.severity === 'high' ? 'bg-warning' : 'bg-warning/60'
                }`} />
                <span className="flex-1 text-sm">{alert.title}</span>
                <Badge variant={
                  alert.severity === 'critical' ? 'destructive' :
                  alert.severity === 'high' ? 'warning' : 'secondary'
                } className="text-[10px]">
                  {alert.severity}
                </Badge>
              </div>
            ))}
            {recentAlerts.length === 0 && (
              <p className="text-sm text-muted-foreground">No open alerts</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
