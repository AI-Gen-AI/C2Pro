import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  AlertTriangle,
  FileText,
  TrendingUp,
  UserPlus,
  CheckCircle,
} from 'lucide-react';
import type { Activity } from '@/types/project';
import { formatDistanceToNow } from 'date-fns';

interface ActivityTimelineProps {
  activities: Activity[];
  className?: string;
}

const activityIcons = {
  alert_created: AlertTriangle,
  alert_resolved: CheckCircle,
  document_uploaded: FileText,
  score_changed: TrendingUp,
  stakeholder_added: UserPlus,
};

const activityColors = {
  alert_created: 'text-red-600 bg-red-100',
  alert_resolved: 'text-emerald-600 bg-emerald-100',
  document_uploaded: 'text-blue-600 bg-blue-100',
  score_changed: 'text-amber-600 bg-amber-100',
  stakeholder_added: 'text-purple-600 bg-purple-100',
};

export function ActivityTimeline({ activities, className }: ActivityTimelineProps) {
  return (
    <Card className={cn('card-interactive', className)}>
      <CardHeader>
        <CardTitle className="text-base font-semibold">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="relative space-y-4">
          {/* Timeline line */}
          <div className="absolute left-[15px] top-0 h-full w-px bg-border" />

          {activities.map((activity, index) => {
            const Icon = activityIcons[activity.type];
            const colorClass = activityColors[activity.type];

            return (
              <div key={activity.id} className="relative flex gap-4">
                {/* Icon */}
                <div
                  className={cn(
                    'relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                    colorClass
                  )}
                >
                  <Icon className="h-4 w-4" />
                </div>

                {/* Content */}
                <div className="flex-1 space-y-1">
                  <p className="text-sm leading-snug">{activity.description}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(activity.timestamp), {
                      addSuffix: true,
                    })}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}
