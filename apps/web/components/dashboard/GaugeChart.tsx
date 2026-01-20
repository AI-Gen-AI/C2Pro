import { useMemo } from 'react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { TrendingUp, TrendingDown, ChevronRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface GaugeChartProps {
  value: number;
  max?: number;
  title?: string;
  trend?: number;
  className?: string;
  onClick?: () => void;
}

export function GaugeChart({
  value,
  max = 100,
  title = 'Coherence Score',
  trend,
  className,
  onClick,
}: GaugeChartProps) {
  const percentage = (value / max) * 100;

  const getColor = (score: number) => {
    if (score >= 80) return 'hsl(142, 76%, 36%)'; // Green
    if (score >= 60) return 'hsl(38, 92%, 50%)'; // Amber
    return 'hsl(0, 84%, 60%)'; // Red
  };

  const getColorClass = (score: number) => {
    if (score >= 80) return 'score-good';
    if (score >= 60) return 'score-fair';
    return 'score-poor';
  };

  const data = useMemo(
    () => [
      { name: 'score', value: percentage },
      { name: 'remaining', value: 100 - percentage },
    ],
    [percentage]
  );

  const color = getColor(value);

  return (
    <Card
      className={cn(
        'card-interactive',
        onClick && 'cursor-pointer transition-all hover:shadow-lg hover:scale-105',
        className
      )}
      onClick={onClick}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium text-muted-foreground">
            {title}
          </CardTitle>
          {onClick && (
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="relative mx-auto h-40 w-40">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                startAngle={180}
                endAngle={0}
                innerRadius={50}
                outerRadius={70}
                paddingAngle={0}
                dataKey="value"
                strokeWidth={0}
              >
                <Cell fill={color} />
                <Cell fill="hsl(210, 40%, 96%)" />
              </Pie>
            </PieChart>
          </ResponsiveContainer>
          <div className="absolute inset-0 flex flex-col items-center justify-center pt-4">
            <span className={cn('text-4xl font-bold', getColorClass(value))}>
              {value}
            </span>
            <span className="text-xs text-muted-foreground">/ {max}</span>
          </div>
        </div>
        {trend !== undefined && (
          <div className="mt-2 flex items-center justify-center gap-1">
            {trend > 0 ? (
              <>
                <TrendingUp className="h-4 w-4 text-emerald-600" />
                <span className="text-sm font-medium text-emerald-600">
                  +{trend} vs last week
                </span>
              </>
            ) : trend < 0 ? (
              <>
                <TrendingDown className="h-4 w-4 text-red-600" />
                <span className="text-sm font-medium text-red-600">
                  {trend} vs last week
                </span>
              </>
            ) : (
              <span className="text-sm text-muted-foreground">No change</span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
