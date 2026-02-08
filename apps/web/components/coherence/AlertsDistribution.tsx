'use client';

import { AlertTriangle } from 'lucide-react';

interface AlertsDistributionProps {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

const SEVERITY_CONFIG = [
  { key: 'critical', label: 'Critical', color: 'hsl(0, 72%, 42%)' },
  { key: 'high', label: 'High', color: 'hsl(21, 90%, 41%)' },
  { key: 'medium', label: 'Medium', color: 'hsl(36, 80%, 40%)' },
  { key: 'low', label: 'Low', color: 'hsl(152, 60%, 30%)' },
] as const;

export function AlertsDistribution({
  critical,
  high,
  medium,
  low,
}: AlertsDistributionProps) {
  const counts: Record<string, number> = { critical, high, medium, low };
  const urgentCount = critical + high;

  return (
    <div>
      <h3 className="mb-4 text-sm font-semibold">Alert Distribution</h3>
      <div className="mb-4 grid grid-cols-4 gap-3">
        {SEVERITY_CONFIG.map((s) => (
          <div
            key={s.key}
            className="rounded-md border p-3 text-center"
            style={{
              backgroundColor: `${s.color}08`,
              borderColor: `${s.color}20`,
            }}
          >
            <div
              className="font-mono text-[28px] font-bold leading-none"
              style={{ color: s.color }}
            >
              {counts[s.key]}
            </div>
            <div className="mt-1 text-[11px] font-medium text-muted-foreground">
              {s.label}
            </div>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2 rounded-md border border-destructive/15 bg-destructive/5 px-3.5 py-2.5 text-xs text-muted-foreground">
        <AlertTriangle className="h-4 w-4 shrink-0 text-destructive" />
        <span>
          <strong className="text-foreground">{urgentCount}</strong> alerts
          require immediate review
        </span>
      </div>
    </div>
  );
}
