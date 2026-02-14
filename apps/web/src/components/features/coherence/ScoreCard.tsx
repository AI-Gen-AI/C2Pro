"use client";

import { cn } from "@/lib/utils";

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
  selected = false,
  onClick,
}: ScoreCardProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex w-full flex-col gap-2 rounded-md border bg-card p-4 text-left transition-colors hover:border-primary/40 hover:bg-accent",
        selected && "border-primary/60 bg-primary/5",
      )}
      aria-pressed={selected}
      aria-label={category}
    >
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {category}
        </span>
        <span className="font-mono text-lg font-bold text-foreground">
          {score}
        </span>
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{alertCount} alerts</span>
        <span>{Math.round(weight * 100)}% weight</span>
      </div>
    </button>
  );
}
