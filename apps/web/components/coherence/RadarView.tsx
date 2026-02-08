'use client';

import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
} from 'recharts';

interface RadarViewProps {
  data: { category: string; score: number; target: number }[];
}

export function RadarView({ data }: RadarViewProps) {
  return (
    <div>
      <h3 className="mb-3 text-sm font-semibold">Score vs Target (80)</h3>
      <ResponsiveContainer width="100%" height={240}>
        <RadarChart data={data}>
          <PolarGrid stroke="hsl(240, 6%, 90%)" />
          <PolarAngleAxis
            dataKey="category"
            tick={{ fontSize: 11, fill: 'hsl(240, 6%, 30%)' }}
          />
          <PolarRadiusAxis
            angle={30}
            domain={[0, 100]}
            tick={{ fontSize: 10 }}
          />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#00ACC1"
            fill="#00ACC1"
            fillOpacity={0.25}
            strokeWidth={2}
            animationDuration={1000}
          />
          <Radar
            name="Target"
            dataKey="target"
            stroke="hsl(240, 4%, 46%)"
            fill="none"
            strokeDasharray="5 5"
            strokeWidth={1.5}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  );
}
