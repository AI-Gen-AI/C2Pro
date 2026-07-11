import { CategoryStatusBadge } from "@/components/coherence/CategoryStatusBadge";
import type { CategoryV2, CoherenceV2Payload } from "@/lib/api/contracts";

const CATEGORY_LABELS: Record<string, string> = {
  SCOPE: "Scope",
  BUDGET: "Budget",
  QUALITY: "Quality",
  TECHNICAL: "Technical",
  TECH: "Technical",
  LEGAL: "Legal",
  TIME: "Time",
};

interface CategoryV2PanelProps {
  payload: CoherenceV2Payload;
}

export function CategoryV2Panel({ payload }: CategoryV2PanelProps) {
  if (payload.categories.length === 0) {
    return (
      <section className="rounded-md border border-dashed bg-card p-5 text-sm text-muted-foreground">
        Evidence-aware category detail is not available for this audit.
      </section>
    );
  }

  return (
    <section className="space-y-4" aria-labelledby="category-v2-heading">
      <div>
        <h3 id="category-v2-heading" className="text-sm font-semibold">
          Evidence-aware categories
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Each category reflects backend evidence coverage, missing inputs, conflicts, and the recommended next action.
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-2">
        {payload.categories.map((category) => (
          <CategoryV2Card key={category.category} category={category} />
        ))}
      </div>
    </section>
  );
}

function CategoryV2Card({ category }: { category: CategoryV2 }) {
  const score =
    typeof category.coherence_score === "number"
      ? Math.round(category.coherence_score)
      : null;
  const coverage =
    typeof category.evidence_coverage === "number"
      ? Math.round(category.evidence_coverage * 100)
      : null;
  const conflicts = Array.isArray(category.detected_conflicts)
    ? category.detected_conflicts
    : [];
  const missingEvidence = Array.isArray(category.missing_evidence)
    ? category.missing_evidence.filter((item) => item.trim().length > 0)
    : [];

  return (
    <article className="rounded-md border bg-card p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h4 className="text-sm font-semibold">
            {CATEGORY_LABELS[category.category] ?? titleCase(category.category)}
          </h4>
          <div className="mt-2">
            <CategoryStatusBadge status={category.status} />
          </div>
        </div>
        <div className="text-right">
          {score === null ? (
            <p className="text-xs font-medium text-muted-foreground">Score unavailable</p>
          ) : (
            <>
              <p className="font-mono text-2xl font-semibold leading-none">{score}</p>
              <p className="mt-1 text-[11px] text-muted-foreground">category score</p>
            </>
          )}
        </div>
      </div>

      {coverage === null ? null : (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="font-medium">Evidence coverage {coverage}%</span>
            {typeof category.evidence_count === "number" ? (
              <span className="text-muted-foreground">
                {category.evidence_count} evidence refs
              </span>
            ) : null}
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary"
              style={{ width: `${clampPercent(coverage)}%` }}
            />
          </div>
        </div>
      )}

      {missingEvidence.length > 0 ? (
        <div className="mt-4">
          <p className="text-xs font-semibold">Missing evidence</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
            {missingEvidence.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </div>
      ) : null}

      {conflicts.length > 0 ? (
        <details className="mt-4 rounded-md border bg-muted/20 p-3 text-xs">
          <summary className="cursor-pointer font-semibold">
            {conflicts.length === 1
              ? "1 detected conflict"
              : `${conflicts.length} detected conflicts`}
          </summary>
          <ul className="mt-2 space-y-2 text-muted-foreground">
            {conflicts.map((conflict, index) => (
              <li key={conflictKey(conflict, index)}>{describeConflict(conflict)}</li>
            ))}
          </ul>
        </details>
      ) : null}

      {category.recommendation ? (
        <p className="mt-4 rounded-md bg-muted/30 p-3 text-xs leading-relaxed">
          <span className="font-semibold">Recommendation: </span>
          {category.recommendation}
        </p>
      ) : null}
    </article>
  );
}

function clampPercent(value: number) {
  if (value < 0) return 0;
  if (value > 100) return 100;
  return value;
}

function titleCase(value: string) {
  return value
    .toLowerCase()
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

function conflictKey(conflict: Record<string, unknown>, index: number) {
  const id = conflict.id;
  return typeof id === "string" || typeof id === "number" ? String(id) : `conflict-${index}`;
}

function describeConflict(conflict: Record<string, unknown>) {
  for (const key of ["title", "message", "summary", "evidence", "description"]) {
    const value = conflict[key];
    if (typeof value === "string" && value.trim().length > 0) {
      return value;
    }
  }

  return JSON.stringify(conflict);
}
