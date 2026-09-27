import Link from "next/link";
import { cn } from "@/lib/utils";
import type { DashboardSummary } from "@/lib/api/contracts";

/**
 * #714 trusted vs projected Coherence Score.
 *
 * The trusted score is the canonical score (approved state only) and is
 * rendered solid. The projected score is a provisional scenario -- "what if
 * every pending proposal is accepted unchanged" -- rendered translucent with
 * a dashed outline and never replaces the trusted score. ADR-009 §18: a null
 * score renders as "—", never as 0.
 */

const REASON_COPY: Record<string, string> = {
  score_version_mismatch: "pending proposals were scored with a different score version",
  pending_without_engine_score: "the pending proposal has no engine score yet",
  pending_without_score_version: "the pending proposal has no score version",
  unknown_score_version: "the pending proposal has an unsupported score version",
  projection_read_failed: "pending proposals could not be read",
  pending_candidate_payload_missing: "a pending proposal could not be loaded",
  projection_evaluation_failed: "the projected evaluation could not be computed",
  insufficient_evidence: "the pending proposals do not provide enough evidence to score",
};

function formatScore(value: number | null | undefined): string {
  return typeof value === "number" ? String(Math.round(value)) : "—";
}

function formatDelta(value: number): string {
  const rounded = Math.round(value);
  if (rounded > 0) return `+${rounded} pts`;
  if (rounded < 0) return `−${Math.abs(rounded)} pts`;
  return "±0 pts";
}

interface ProjectedCoherencePanelProps {
  readonly summary: DashboardSummary;
}

function numberOrNull(value: number | null | undefined): number | null {
  return typeof value === "number" ? value : null;
}

interface PanelView {
  pending: number;
  trusted: number | null;
  projected: number | null;
  delta: number | null;
  baseline: number | null;
  unavailable: boolean;
  reason: string | null;
  proposalLabel: string;
}

function panelView(summary: DashboardSummary): PanelView {
  const pending =
    typeof summary.pending_review_count === "number" ? summary.pending_review_count : 0;
  const projected = numberOrNull(summary.projected_score);
  const code = summary.projection_reason;
  return {
    pending,
    trusted: numberOrNull(summary.trusted_score) ?? numberOrNull(summary.coherence_score),
    projected,
    delta: numberOrNull(summary.projected_delta),
    baseline: numberOrNull(summary.projection_baseline_score),
    unavailable: summary.projection_status === "unavailable" || projected === null,
    reason: code ? (REASON_COPY[code] ?? code) : null,
    proposalLabel: pending === 1 ? "proposal" : "proposals",
  };
}

export function ProjectedCoherencePanel({ summary }: Readonly<ProjectedCoherencePanelProps>) {
  const { pending, trusted, projected, delta, baseline, unavailable, reason, proposalLabel } =
    panelView(summary);
  if (pending <= 0) {
    return null;
  }

  return (
    <section
      aria-label="Trusted and projected coherence"
      className="rounded-md border bg-card p-4 shadow-sm"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-stretch">
        <div
          data-testid="coherence-trusted-score"
          data-variant="trusted"
          className="flex min-w-[140px] flex-col rounded-md border border-border bg-background px-4 py-3"
        >
          <span className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Trusted score
          </span>
          <span className="mt-1 font-mono text-3xl font-bold text-foreground">
            {formatScore(trusted)}
          </span>
          <span className="text-xs text-muted-foreground">
            {typeof trusted === "number" ? "Approved state only" : "Pending first approval"}
          </span>
        </div>

        <div
          data-testid="coherence-projected-score"
          data-variant="provisional"
          className="flex min-w-[140px] flex-col rounded-md border border-dashed border-primary/50 bg-primary/5 px-4 py-3 opacity-80"
        >
          <span className="text-[10px] font-medium uppercase tracking-widest text-muted-foreground">
            Projected · provisional
          </span>
          <span className="mt-1 font-mono text-3xl font-semibold text-primary/80">
            {formatScore(projected)}
          </span>
          <span className="text-xs text-muted-foreground">
            Projected if all pending proposals are accepted unchanged
          </span>
        </div>

        <div className="flex flex-1 flex-col justify-between gap-2 text-sm">
          {delta !== null && !unavailable ? (
            <p>
              <span className="text-muted-foreground">Change vs trusted: </span>
              <span
                data-testid="coherence-projected-delta"
                className={cn(
                  "font-semibold",
                  delta < 0 ? "text-destructive" : "text-emerald-700",
                )}
              >
                {formatDelta(delta)}
              </span>
              {baseline !== null ? (
                <span className="text-xs text-muted-foreground" data-testid="coherence-projection-baseline">
                  {" "}
                  (vs trusted project evaluation {formatScore(baseline)})
                </span>
              ) : null}
            </p>
          ) : null}
          {unavailable ? (
            <p className="text-xs text-muted-foreground">
              Projection unavailable{reason ? `: ${reason}` : ""}. The trusted score is unaffected.
            </p>
          ) : null}
          <p>
            <span data-testid="coherence-pending-count" className="font-semibold">
              {pending}
            </span>{" "}
            <span className="text-muted-foreground">{proposalLabel} awaiting human review</span>
          </p>
          <Link
            href={`/projects/${summary.project_id}/review`}
            className="inline-flex h-8 w-fit items-center rounded-md border border-primary/30 px-3 text-xs font-medium text-primary transition-colors hover:bg-primary/10"
          >
            Review {pending} pending {proposalLabel}
          </Link>
        </div>
      </div>
    </section>
  );
}
