import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
import {
  FolderKanban,
  AlertTriangle,
  DollarSign,
  LucideIcon,
} from 'lucide-react';

interface KPICardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  subtitleVariant?: 'default' | 'warning' | 'destructive';
  icon?: LucideIcon;
  progress?: number;
  link?: string;
  className?: string;
}

export function KPICard({
  title,
  value,
  subtitle,
  subtitleVariant = 'default',
  icon: Icon,
  progress,
  className,
}: KPICardProps) {
  const getProgressColor = (val: number) => {
    if (val >= 95) return 'bg-red-500';
    if (val >= 80) return 'bg-amber-500';
    return 'bg-emerald-500';
  };

  return (
    <Card className={cn('card-interactive', className)}>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </CardTitle>
        {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">{value}</div>
        {subtitle && (
          <div className="mt-1 flex items-center gap-2">
            <Badge
              variant={
                subtitleVariant === 'warning'
                  ? 'outline'
                  : subtitleVariant === 'destructive'
                  ? 'destructive'
                  : 'secondary'
              }
              className={cn(
                subtitleVariant === 'warning' &&
                  'border-amber-400 bg-amber-50 text-amber-700'
              )}
            >
              {subtitle}
            </Badge>
          </div>
        )}
        {progress !== undefined && (
          <div className="mt-3 space-y-1">
            <div className="flex items-center justify-between text-xs">
              <span className="text-muted-foreground">Used</span>
              <span className="font-medium">{progress}%</span>
            </div>
            <Progress
              value={progress}
              className="h-2"
            />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export function KPICardsGrid() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
      <KPICard
        title="Active Projects"
        value="12"
        subtitle="3 at risk"
        subtitleVariant="destructive"
        icon={FolderKanban}
      />
      <KPICard
        title="Open Alerts"
        value="7"
        subtitle="3 critical"
        subtitleVariant="destructive"
        icon={AlertTriangle}
      />
      <KPICard
        title="Budget Health"
        value="62%"
        progress={62}
        icon={DollarSign}
      />
      <KPICard
        title="Documents Processed"
        value="156"
        subtitle="12 pending review"
        subtitleVariant="warning"
      />
    </div>
  );
}
