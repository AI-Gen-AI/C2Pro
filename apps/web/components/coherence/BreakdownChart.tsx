'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  ResponsiveContainer,
} from 'recharts';

const CHART_COLORS: Record<string, string> = {
  Scope: '#00ACC1',
  Budget: '#6929C4',
  Quality: '#1192E8',
  Technical: '#005D5D',
  Legal: '#9F1853',
  Time: '#FA4D56',
};

interface BreakdownChartProps {
  data: { name: string; score: number }[];
}

export function BreakdownChart({ data }: BreakdownChartProps) {
  const sorted = [...data].sort((a, b) => a.score - b.score);

  return (
    <div>
      <h3 className="mb-4 text-sm font-semibold">
        Category Scores (sorted by priority)
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart
          data={sorted}
          layout="vertical"
          margin={{ left: 10, right: 30 }}
          barSize={18}
        >
          <XAxis
            type="number"
            domain={[0, 100]}
            tick={{ fontSize: 11, fill: 'hsl(240, 4%, 46%)' }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            type="category"
            dataKey="name"
            tick={{ fontSize: 12, fill: 'hsl(240, 6%, 30%)' }}
            axisLine={false}
            tickLine={false}
            width={80}
          />
          <Tooltip
            contentStyle={{
              borderRadius: '6px',
              border: '1px solid hsl(240, 6%, 90%)',
              fontSize: 12,
            }}
            formatter={(v: number) => [`${v}/100`, 'Score']}
          />
          <Bar dataKey="score" radius={[0, 4, 4, 0]} animationDuration={1200}>
            {sorted.map((d, i) => (
              <Cell key={i} fill={CHART_COLORS[d.name] || '#00ACC1'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
