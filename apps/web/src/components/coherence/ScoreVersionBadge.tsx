export type ScoreVersion =
  | "v0_flag_based"
  | "v1_exponential_decay"
  | "v2_evidence_aware";

import Link from "next/link";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

type ScoreVersionBadgeProps = {
  scoreVersion?: ScoreVersion | string | null;
};

const BADGE_COPY: Record<
  ScoreVersion,
  { label: string; ariaLabel: string; className: string; tooltip: string }
> = {
  v0_flag_based: {
    label: "(v0)",
    ariaLabel: "Legacy flag-based coherence score",
    className: "border-stone-300 bg-stone-100 text-stone-700",
    tooltip:
      "v0 is the historical flag-based score. It remains immutable for audits before the v1 cut-off.",
  },
  v1_exponential_decay: {
    label: "(v1)",
    ariaLabel: "v1 exponential-decay coherence score",
    className: "border-emerald-300 bg-emerald-50 text-emerald-800",
    tooltip:
      "v1 uses weighted finding severity, confidence, and project scope to produce a defensible coherence score.",
  },
  v2_evidence_aware: {
    label: "(v2)",
    ariaLabel: "v2 evidence-aware coherence score",
    className: "border-sky-300 bg-sky-50 text-sky-800",
    tooltip:
      "v2 is the evidence-aware, tri-axis score (coherence + completeness + technical reliability) from ADR-009.",
  },
};

export function ScoreVersionBadge({ scoreVersion }: ScoreVersionBadgeProps) {
  const resolvedVersion: ScoreVersion =
    scoreVersion === "v2_evidence_aware"
      ? "v2_evidence_aware"
      : scoreVersion === "v1_exponential_decay"
        ? "v1_exponential_decay"
        : "v0_flag_based";
  const copy = BADGE_COPY[resolvedVersion];

  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={copy.ariaLabel}
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold tracking-normal ${copy.className}`}
            data-score-version={resolvedVersion}
          >
            {copy.label}
          </button>
        </TooltipTrigger>
        <TooltipContent forceMount className="max-w-[300px] space-y-2 p-3 text-xs leading-relaxed">
          <p>{copy.tooltip}</p>
          <Link
            className="font-semibold text-primary underline-offset-4 hover:underline"
            href="/docs/customer/COHERENCE_V1_FAQ.md"
          >
            What changed
          </Link>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
