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
  summary: DashboardSummary;
}

export function ProjectedCoherencePanel({ summary }: ProjectedCoherencePanelProps) {
  const pending =
    typeof summary.pending_review_count === "number" ? summary.pending_review_count : 0;
  if (pending <= 0) {
    return null;
  }

  const trusted =
    typeof summary.trusted_score === "number" ? summary.trusted_score : summary.coherence_score;
  const projected =
    typeof summary.projected_score === "number" ? summary.projected_score : null;
  const delta = typeof summary.projected_delta === "number" ? summary.projected_delta : null;
  const unavailable = summary.projection_status === "unavailable" || projected === null;
  const reason = summary.projection_reason
    ? REASON_COPY[summary.projection_reason] ?? summary.projection_reason
    : null;
  const proposalLabel = pending === 1 ? "proposal" : "proposals";

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
