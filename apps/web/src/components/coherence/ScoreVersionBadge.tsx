export type ScoreVersion = "v0_flag_based" | "v1_exponential_decay";

type ScoreVersionBadgeProps = {
  scoreVersion?: ScoreVersion | string | null;
};

const BADGE_COPY: Record<ScoreVersion, { label: string; ariaLabel: string; className: string }> = {
  v0_flag_based: {
    label: "(v0)",
    ariaLabel: "Legacy flag-based coherence score",
    className: "border-stone-300 bg-stone-100 text-stone-700",
  },
  v1_exponential_decay: {
    label: "(v1)",
    ariaLabel: "v1 exponential-decay coherence score",
    className: "border-emerald-300 bg-emerald-50 text-emerald-800",
  },
};

export function ScoreVersionBadge({ scoreVersion }: ScoreVersionBadgeProps) {
  const resolvedVersion: ScoreVersion =
    scoreVersion === "v1_exponential_decay" ? "v1_exponential_decay" : "v0_flag_based";
  const copy = BADGE_COPY[resolvedVersion];

  return (
    <span
      aria-label={copy.ariaLabel}
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold tracking-[0.14em] ${copy.className}`}
      data-score-version={resolvedVersion}
    >
      {copy.label}
    </span>
  );
}
