'use client';

import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import {
  Target,
  DollarSign,
  CheckCircle,
  Settings,
  Scale,
  Clock,
  type LucideIcon,
} from 'lucide-react';
import { useCountUp } from '@/hooks/useCountUp';

const CATEGORY_CONFIG: Record<
  string,
  { icon: LucideIcon; color: string; label: string }
> = {
  SCOPE: { icon: Target, color: '#00ACC1', label: 'Scope' },
  BUDGET: { icon: DollarSign, color: '#6929C4', label: 'Budget' },
  QUALITY: { icon: CheckCircle, color: '#1192E8', label: 'Quality' },
  TECHNICAL: { icon: Settings, color: '#005D5D', label: 'Technical' },
  LEGAL: { icon: Scale, color: '#9F1853', label: 'Legal' },
  TIME: { icon: Clock, color: '#FA4D56', label: 'Time' },
};

function getSeverity(score: number) {
  if (score >= 80) return { label: 'Good', variant: 'success' as const, shape: '\u25CF' };
  if (score >= 60) return { label: 'Warning', variant: 'warning' as const, shape: '\u25C6' };
  return { label: 'Critical', variant: 'destructive' as const, shape: '\u25B2' };
}

interface ScoreCardProps {
  category: string;
  score: number;
  weight: number;
  alertCount: number;
  selected?: boolean;
  onClick?: () => void;
}

export function ScoreCard({
  category,
  score,
  weight,
  alertCount,
  selected,
  onClick,
}: ScoreCardProps) {
  const config = CATEGORY_CONFIG[category] ?? CATEGORY_CONFIG.SCOPE;
  const severity = getSeverity(score);
  const animated = useCountUp(score);
  const Icon = config.icon;

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all duration-200 hover:shadow-md',
        'focus-visible:ring-ring focus-visible:ring-2 focus-visible:ring-offset-2',
        selected && 'ring-1'
      )}
      style={{
        borderColor: selected ? config.color : undefined,
        backgroundColor: selected ? `${config.color}08` : undefined,
        ...(selected ? { boxShadow: `0 0 0 1px ${config.color}40` } : {}),
      }}
      onClick={onClick}
      tabIndex={0}
      role="button"
      aria-label={`${config.label} score ${score}/100, ${alertCount} alerts, ${severity.label}`}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onClick?.();
        }
      }}
    >
      <CardContent className="flex items-center gap-3 p-3.5">
        <div
          className="flex h-[38px] w-[38px] shrink-0 items-center justify-center rounded-md"
          style={{ backgroundColor: `${config.color}15` }}
        >
          <Icon
            className="h-[18px] w-[18px]"
            style={{ color: config.color }}
            strokeWidth={1.75}
            aria-hidden
          />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-1">
            <span className="font-mono text-[22px] font-bold leading-none tabular-nums">
              {animated}
            </span>
            <span className="text-[11px] text-muted-foreground">/100</span>
          </div>
          <div className="flex items-center gap-1 text-xs text-muted-foreground">
            <span>{config.label}</span>
            <span className="text-muted-foreground/50">&middot;</span>
            <span className="font-mono text-[11px]">
              {Math.round(weight * 100)}%
            </span>
          </div>
        </div>

        <Badge variant={severity.variant} className="shrink-0 gap-1 text-[11px]">
          <span aria-hidden>{severity.shape}</span>
          {severity.label}
        </Badge>

        {alertCount > 0 && (
          <span
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-destructive/10 font-mono text-[11px] font-semibold text-destructive"
            aria-label={`${alertCount} alerts`}
          >
            {alertCount}
          </span>
        )}
      </CardContent>
    </Card>
  );
}
