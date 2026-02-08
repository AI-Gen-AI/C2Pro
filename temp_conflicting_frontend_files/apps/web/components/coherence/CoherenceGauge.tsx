'use client';

import { useMemo } from 'react';
import { RadialBarChart, RadialBar, ResponsiveContainer } from 'recharts';
import { useCountUp } from '@/hooks/useCountUp';
import { cn } from '@/lib/utils';

function getScoreColor(score: number) {
  if (score >= 70) return 'hsl(152, 60%, 30%)';
  if (score >= 40) return 'hsl(36, 80%, 40%)';
  return 'hsl(0, 72%, 42%)';
}

function getScoreLabel(score: number) {
  if (score >= 85) return 'Excellent';
  if (score >= 70) return 'Good';
  if (score >= 55) return 'Acceptable';
  if (score >= 40) return 'At Risk';
  return 'Critical';
}

interface CoherenceGaugeProps {
  score: number;
  documentsAnalyzed: number;
  dataPointsChecked: number;
  calculatedAt?: string;
  className?: string;
}

export function CoherenceGauge({
  score,
  documentsAnalyzed,
  dataPointsChecked,
  calculatedAt,
  className,
}: CoherenceGaugeProps) {
  const animatedScore = useCountUp(score);
  const color = getScoreColor(score);
  const label = getScoreLabel(score);

  const gaugeData = useMemo(
    () => [{ name: 'score', value: score, fill: color }],
    [score, color]
  );

  return (
    <div
      className={cn(
        'flex flex-col items-center gap-2 rounded-md border bg-card p-6 shadow-sm',
        className
      )}
      role="img"
      aria-label={`Coherence Score: ${score}/100, ${label}`}
    >
      <div className="relative h-[180px] w-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <RadialBarChart
            cx="50%"
            cy="50%"
            innerRadius="72%"
            outerRadius="100%"
            startAngle={90}
            endAngle={-270}
            data={gaugeData}
            barSize={14}
          >
            <RadialBar
              dataKey="value"
              cornerRadius={7}
              background={{ fill: 'hsl(220, 10%, 96%)' }}
              animationDuration={1500}
              animationEasing="ease-out"
            />
          </RadialBarChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span
            className="font-mono text-[40px] font-bold leading-none tabular-nums"
            style={{ color }}
          >
            {animatedScore}
          </span>
          <span className="text-[13px] text-muted-foreground">/100</span>
        </div>
      </div>

      <span
        className="rounded-full px-3.5 py-1 text-xs font-semibold"
        style={{ color, backgroundColor: `${color}1a` }}
      >
        {label}
      </span>

      <p className="text-center text-[11px] leading-relaxed text-muted-foreground">
        Based on{' '}
        <span className="font-mono font-semibold">{documentsAnalyzed}</span>{' '}
        documents and{' '}
        <span className="font-mono font-semibold">
          {dataPointsChecked.toLocaleString()}
        </span>{' '}
        data points
      </p>

      {calculatedAt && (
        <div className="font-mono text-[10px] text-muted-foreground">
          v3.2 engine &middot; {calculatedAt}
        </div>
      )}
    </div>
  );
}
