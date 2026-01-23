import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import {
  AlertTriangle,
  FileText,
  TrendingUp,
  UserPlus,
  CheckCircle,
  FolderPlus,
  BarChart3,
  Edit,
} from 'lucide-react';
import type { Activity } from '@/types/project';
import { formatDistanceToNow } from 'date-fns';

interface ActivityTimelineProps {
  activities: Activity[];
  className?: string;
}

const activityIcons = {
  project_created: FolderPlus,
  document_uploaded: FileText,
  analysis_completed: BarChart3,
  alert_created: AlertTriangle,
  alert_resolved: CheckCircle,
  status_changed: Edit,
  score_changed: TrendingUp,
  stakeholder_added: UserPlus,
} as const;

const activityColors = {
  project_created: 'text-blue-600 bg-blue-100',
  document_uploaded: 'text-blue-600 bg-blue-100',
  analysis_completed: 'text-green-600 bg-green-100',
  alert_created: 'text-red-600 bg-red-100',
  alert_resolved: 'text-emerald-600 bg-emerald-100',
  status_changed: 'text-gray-600 bg-gray-100',
  score_changed: 'text-amber-600 bg-amber-100',
  stakeholder_added: 'text-purple-600 bg-purple-100',
} as const;

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
            const Icon = activityIcons[activity.type] || FileText;
            const colorClass = activityColors[activity.type] || 'text-gray-600 bg-gray-100';

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
                    {activity.created_at || activity.timestamp ? formatDistanceToNow(new Date(activity.created_at || activity.timestamp!), {
                      addSuffix: true,
                    }) : 'Recently'}
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
