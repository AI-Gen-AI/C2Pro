/**
 * CoherenceEmptyState — ADR-009 §18 / §2.8 mandate.
 *
 * Rendered whenever `coherence_score === null`. NEVER renders a fallback "0"
 * or red destructive styling — those are reserved for validated incoherence.
 * Uses neutral/amber tokens to signal that evidence is pending.
 */
import Link from "next/link";

const REASON_COPY: Record<string, string> = {
  insufficient_active_weight:
    "Not enough categories have qualifying evidence to compute a reliable global score yet.",
  pending_documents:
    "Upload the project documents to begin the analysis.",
  no_v1_data:
    "No prior coherence run is available for this project yet.",
  scored_categories_only:
    "Coherence has been computed only on the categories that meet the evidence threshold.",
};

export interface CoherenceEmptyStateProps {
  reason?: string | null;
  projectId: string;
}

export function CoherenceEmptyState({ reason, projectId }: CoherenceEmptyStateProps) {
  const detail =
    (reason && REASON_COPY[reason]) ||
    "Upload the missing documents to compute the project's coherence.";

  return (
    <section
      data-testid="coherence-empty-state"
      className="flex flex-col items-start gap-3 rounded-md border border-amber-300/60 bg-amber-50/60 p-6 text-amber-900 dark:border-amber-700/40 dark:bg-amber-950/30 dark:text-amber-100"
      role="status"
      aria-live="polite"
    >
      <h2 className="text-lg font-semibold">Pending evidence</h2>
      <p className="text-sm leading-relaxed">{detail}</p>
      {reason ? (
        <p className="text-xs uppercase tracking-wider text-amber-800/70 dark:text-amber-200/70">
          Reason: <span data-testid="empty-state-reason">{reason}</span>
        </p>
      ) : null}
      <Link
        data-testid="empty-state-cta"
        href={`/projects/${projectId}/documents`}
        className="mt-2 inline-flex items-center rounded-md bg-amber-900 px-3 py-1.5 text-sm font-medium text-amber-50 transition-colors hover:bg-amber-800 dark:bg-amber-100 dark:text-amber-900 dark:hover:bg-amber-200"
      >
        Upload missing documents
      </Link>
    </section>
  );
}
