"use client";

import { cn } from "@/lib/utils";

interface CoherenceGaugeProps {
  score: number;
  label: string;
  documentsAnalyzed: number;
  dataPointsChecked: number;
  className?: string;
}

export function CoherenceGauge({
  score,
  label,
  documentsAnalyzed,
  dataPointsChecked,
  className,
}: CoherenceGaugeProps) {
  const size = 180;
  const strokeWidth = 14;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = ((100 - score) / 100) * circumference;

  return (
    <div
      className={cn(
        "flex flex-col items-center gap-2 rounded-md border bg-card p-6 shadow-sm",
        className,
      )}
      role="img"
      aria-label={`Coherence Score: ${score}/100, ${label}`}
    >
      <figure className="flex flex-col items-center gap-2">
        <svg
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="img"
          aria-hidden="true"
        >
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--muted)"
            strokeWidth={strokeWidth}
          />
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="var(--primary)"
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={progress}
            strokeLinecap="round"
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            className="transition-[stroke-dashoffset] duration-[1500ms] ease-[cubic-bezier(0.16,1,0.3,1)]"
          />
          <text
            x="50%"
            y="50%"
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-foreground font-mono text-4xl font-bold tabular-nums"
          >
            {score}
          </text>
        </svg>
        <figcaption className="text-sm text-muted-foreground">{label}</figcaption>
      </figure>

      <p className="text-center text-[11px] leading-relaxed text-muted-foreground">
        Based on{" "}
        <span className="font-mono font-semibold">{documentsAnalyzed}</span>{" "}
        documents and{" "}
        <span className="font-mono font-semibold">
          {dataPointsChecked.toLocaleString()}
        </span>{" "}
        data points
      </p>
    </div>
  );
}
