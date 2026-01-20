import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowRight } from 'lucide-react';
import type { Alert, Severity } from '@/types/project';
import { formatDistanceToNow } from 'date-fns';
import Link from 'next/link';

interface TopAlertsCardProps {
  alerts: Alert[];
  className?: string;
}

const severityConfig: Record<
  Severity,
  { label: string; className: string; dotClass: string }
> = {
  critical: {
    label: 'Critical',
    className: 'severity-critical',
    dotClass: 'bg-red-500 animate-pulse-critical',
  },
  high: {
    label: 'High',
    className: 'severity-high',
    dotClass: 'bg-orange-500',
  },
  medium: {
    label: 'Medium',
    className: 'severity-medium',
    dotClass: 'bg-amber-500',
  },
  low: {
    label: 'Low',
    className: 'severity-low',
    dotClass: 'bg-slate-400',
  },
};

export function TopAlertsCard({ alerts, className }: TopAlertsCardProps) {
  const topAlerts = alerts
    .filter((a) => a.status === 'open' || a.status === 'in_progress')
    .slice(0, 5);

  return (
    <Card className={cn('card-interactive', className)}>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base font-semibold">Top Alerts</CardTitle>
        <Link href="/alerts">
          <Button variant="ghost" size="sm" className="gap-1 text-xs">
            View All
            <ArrowRight className="h-3 w-3" />
          </Button>
        </Link>
      </CardHeader>
      <CardContent>
        <div className="space-y-3">
          {topAlerts.map((alert) => {
            const config = severityConfig[alert.severity];

            return (
              <div
                key={alert.id}
                className="flex items-start gap-3 rounded-lg border p-3 transition-colors hover:bg-muted/50"
              >
                {/* Severity Dot */}
                <div className={cn('mt-1.5 h-2 w-2 rounded-full', config.dotClass)} />

                {/* Content */}
                <div className="flex-1 space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-muted-foreground">
                      {alert.id}
                    </span>
                    <Badge
                      variant="outline"
                      className={cn('text-xs', config.className)}
                    >
                      {config.label}
                    </Badge>
                  </div>
                  <p className="text-sm font-medium leading-snug">{alert.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {alert.project_name} •{' '}
                    {formatDistanceToNow(new Date(alert.created_at), {
                      addSuffix: true,
                    })}
                  </p>
                </div>
              </div>
            );
          })}

          {topAlerts.length === 0 && (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <p className="text-sm text-muted-foreground">No open alerts</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
