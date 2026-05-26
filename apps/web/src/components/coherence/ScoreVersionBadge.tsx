/**
 * Canonical score version type — Phase F (ADR-009 §F).
 * Only "coherence-v1" and "coherence-v2" are canonical.
 * Legacy values are accepted at the prop boundary and mapped to "(v1)" gracefully
 * until the DB migration (20260526_0001) finishes deployment.
 */
export type ScoreVersion = "coherence-v1" | "coherence-v2";

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
  "coherence-v1": {
    label: "(v1)",
    ariaLabel: "v1 coherence score",
    className: "border-emerald-300 bg-emerald-50 text-emerald-800",
    tooltip:
      "v1 uses weighted finding severity, confidence, and project scope to produce a defensible coherence score.",
  },
  "coherence-v2": {
    label: "(v2)",
    ariaLabel: "v2 evidence-aware coherence score",
    className: "border-sky-300 bg-sky-50 text-sky-800",
    tooltip:
      "v2 is the evidence-aware, tri-axis score (coherence + completeness + technical reliability) from ADR-009.",
  },
};

/** Resolve any input (including legacy or unknown) to a canonical ScoreVersion. */
function resolveVersion(scoreVersion: string | null | undefined): ScoreVersion {
  if (scoreVersion === "coherence-v2") return "coherence-v2";
  // All other values (including "coherence-v1", legacy "v0_flag_based",
  // "v1_exponential_decay", null, undefined, unknown) resolve to v1.
  return "coherence-v1";
}

export function ScoreVersionBadge({ scoreVersion }: ScoreVersionBadgeProps) {
  const resolved = resolveVersion(scoreVersion);
  const copy = BADGE_COPY[resolved];

  return (
    <TooltipProvider delayDuration={0}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            aria-label={copy.ariaLabel}
            className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold tracking-normal ${copy.className}`}
            data-score-version={resolved}
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
