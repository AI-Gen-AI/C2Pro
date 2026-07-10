/**
 * Test Suite ID: TASK-FRT-200
 * Backlog Task: TASK-FRT-200
 */
import type { LandingCopy } from "../copy";
import { cn } from "@/lib/utils";

type ConsoleMockProps = {
  copy: LandingCopy["console"];
};

const rowTone: Record<LandingCopy["console"]["rows"][number]["tone"], string> = {
  neutral: "border-brand-line-soft bg-brand-paper text-brand-slate",
  warning: "border-brand-warning-soft bg-brand-warning-soft text-brand-warning-ink",
  risk: "border-brand-risk-soft bg-brand-risk-soft text-brand-risk-ink",
  success: "border-brand-accent-soft bg-brand-accent-soft text-brand-accent-ink",
};

export function ConsoleMock({ copy }: ConsoleMockProps) {
  return (
    <div
      aria-hidden="true"
      className="rounded-[14px] border border-brand-line bg-brand-paper shadow-lg"
      data-testid="landing-console-mock"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-brand-line-soft px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-brand-risk-ink" />
          <span className="h-2.5 w-2.5 rounded-full bg-brand-warning-ink" />
          <span className="h-2.5 w-2.5 rounded-full bg-brand-accent" />
        </div>
        <div className="font-mono text-[0.72rem] text-brand-muted">
          {copy.barTitle}
        </div>
        <div className="flex flex-wrap gap-2">
          {copy.badges.map((badge) => (
            <span
              className="rounded-full border border-brand-line-soft px-2 py-1 font-mono text-[0.68rem] uppercase tracking-[0.12em] text-brand-accent-ink"
              key={badge}
            >
              {badge}
            </span>
          ))}
        </div>
      </div>
      <div className="space-y-3 p-4">
        {copy.rows.map((row) => (
          <div
            className="flex items-center justify-between gap-4 rounded-[10px] border border-brand-line-soft px-3 py-2"
            key={row.name}
          >
            <span className="font-mono text-xs text-brand-ink">{row.name}</span>
            <span
              className={cn(
                "rounded-full border px-2 py-1 text-right font-mono text-[0.68rem]",
                rowTone[row.tone],
              )}
            >
              {row.status}
            </span>
          </div>
        ))}
        <div className="rounded-[12px] border border-brand-line bg-brand-alabaster p-4">
          <div className="font-mono text-[0.7rem] uppercase tracking-[0.14em] text-brand-accent-ink">
            {copy.evidenceKey}
          </div>
          <p className="mt-3 text-sm leading-6 text-brand-ink">{copy.quote}</p>
          <div className="mt-4 flex flex-wrap gap-2">
            {copy.tags.map((tag) => (
              <span
                className="rounded-full border border-brand-line bg-brand-paper px-2 py-1 text-xs text-brand-slate"
                key={tag}
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </div>
      <div className="flex items-center justify-between gap-3 border-t border-brand-line-soft px-4 py-3">
        <span className="font-mono text-[0.72rem] text-brand-muted">
          {copy.foot}
        </span>
        <span className="rounded-full bg-brand-navy px-2.5 py-1 font-mono text-[0.68rem] uppercase tracking-[0.12em] text-brand-on-navy">
          {copy.footBadge}
        </span>
      </div>
    </div>
  );
}
