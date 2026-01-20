import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import type { CategoryBreakdown } from '@/types/coherence';
import {
  CATEGORY_COLORS,
  CATEGORY_BG_COLORS,
  CATEGORY_BORDER_COLORS,
  CATEGORY_TEXT_COLORS,
} from '@/lib/constants/categories';
import { cn } from '@/lib/utils';
import { Scale, DollarSign, Wrench, Calendar, Target, ShieldCheck } from 'lucide-react';

interface CategoryBreakdownCardProps {
  breakdown: CategoryBreakdown;
  className?: string;
}

const CATEGORY_ICONS = {
  Legal: Scale,
  Financial: DollarSign,
  Technical: Wrench,
  Schedule: Calendar,
  Scope: Target,
  Quality: ShieldCheck,
};

export function CategoryBreakdownCard({ breakdown, className }: CategoryBreakdownCardProps) {
  const { category, score, alert_count, severity_breakdown, impact_percentage } = breakdown;

  const Icon = CATEGORY_ICONS[category];
  const color = CATEGORY_COLORS[category];
  const bgColor = CATEGORY_BG_COLORS[category];
  const borderColor = CATEGORY_BORDER_COLORS[category];
  const textColor = CATEGORY_TEXT_COLORS[category];

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'text-green-600';
    if (score >= 60) return 'text-amber-600';
    return 'text-red-600';
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'bg-red-100 text-red-700 border-red-200';
      case 'high':
        return 'bg-orange-100 text-orange-700 border-orange-200';
      case 'medium':
        return 'bg-yellow-100 text-yellow-700 border-yellow-200';
      case 'low':
        return 'bg-gray-100 text-gray-700 border-gray-200';
      default:
        return 'bg-gray-100 text-gray-700 border-gray-200';
    }
  };

  return (
    <Card
      className={cn('transition-all hover:shadow-md', className)}
      style={{
        backgroundColor: bgColor,
        borderColor: borderColor,
      }}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className="rounded-lg p-2"
              style={{ backgroundColor: color + '20' }}
            >
              <Icon className="h-5 w-5" style={{ color }} />
            </div>
            <h3
              className="font-semibold"
              style={{ color: textColor }}
            >
              {category}
            </h3>
          </div>
          <span className={cn('text-2xl font-bold', getScoreColor(score))}>
            {score}
          </span>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Progress Bar */}
        <div className="space-y-1">
          <Progress value={score} className="h-2" />
          <p className="text-xs text-muted-foreground">
            Score: {score}/100
          </p>
        </div>

        {/* Alert Count */}
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">Total Alerts:</span>
          <span className="font-semibold">{alert_count}</span>
        </div>

        {/* Severity Breakdown */}
        <div className="space-y-2">
          <p className="text-xs font-medium text-muted-foreground">By Severity:</p>
          <div className="flex flex-wrap gap-2">
            {severity_breakdown.critical > 0 && (
              <Badge variant="outline" className={getSeverityColor('critical')}>
                {severity_breakdown.critical} Critical
              </Badge>
            )}
            {severity_breakdown.high > 0 && (
              <Badge variant="outline" className={getSeverityColor('high')}>
                {severity_breakdown.high} High
              </Badge>
            )}
            {severity_breakdown.medium > 0 && (
              <Badge variant="outline" className={getSeverityColor('medium')}>
                {severity_breakdown.medium} Medium
              </Badge>
            )}
            {severity_breakdown.low > 0 && (
              <Badge variant="outline" className={getSeverityColor('low')}>
                {severity_breakdown.low} Low
              </Badge>
            )}
          </div>
        </div>

        {/* Impact Percentage */}
        <div className="pt-2 border-t">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Impact on Score:</span>
            <span className="font-semibold" style={{ color: textColor }}>
              {impact_percentage}%
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
