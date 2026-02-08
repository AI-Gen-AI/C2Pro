import Link from 'next/link';
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

const stats = [
  { label: 'Coherence Score', value: '78', icon: Gauge, color: 'text-primary' },
  { label: 'Open Alerts', value: '7', icon: AlertTriangle, color: 'text-warning' },
  { label: 'Documents', value: '12', icon: FileText, color: 'text-chart-quality' },
  { label: 'Budget Used', value: '62%', icon: DollarSign, color: 'text-chart-budget' },
];

export default async function ProjectOverviewPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="space-y-5">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
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
              <span className="font-mono font-medium text-foreground">62%</span>
            </div>
            <Progress value={62} className="h-1.5" />
            <div className="flex justify-between">
              <span>Completion</span>
              <span className="font-mono font-medium text-foreground">45%</span>
            </div>
            <Progress value={45} className="h-1.5" />
            <div className="flex justify-between">
              <span>Timeline</span>
              <span className="text-foreground">Jan 2025 - Dec 2026</span>
            </div>
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
            {[
              { severity: 'critical', title: 'Contract Penalty Clause Violation Risk' },
              { severity: 'high', title: 'Critical Path Delay - Foundation Work' },
              { severity: 'medium', title: 'Material Cost Variance' },
            ].map((alert, i) => (
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
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
