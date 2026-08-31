"use client";

/**
 * P0b-L4-5 — the user-visible single-document Health surface.
 *
 * Answers four questions for one uploaded contract: what do I know, what evidence
 * supports it, what is missing, what should I do next. It reads the Health contract
 * published by #581 through the GENERATED client only — there is no second Health API
 * and no parallel data shape.
 *
 * Two product invariants are enforced here, in the render, not merely documented:
 *
 * INV-1 (honest null): a category without qualifying evidence renders
 * "Unknown / Insufficient evidence". It is never 0, never 0%, and never a red zero
 * dressed up as a measured failure — "we did not look" and "we looked and found
 * nothing" are different claims, and neither is a score.
 *
 * INV-COH: Coherence requires enough reconcilable evidence to evaluate consistency.
 * Eligibility is a property of the EVIDENCE, not of the file count -- one document can
 * carry several independently reconcilable claims, and two unrelated documents can
 * carry none. While no subscore has been incorporated this surface shows NO Coherence
 * score and says only that it is unavailable: the contract records whether a subscore
 * was incorporated, not why one was not, so anything more would over-claim.
 *
 * Evidence granularity is disclosed rather than inferred: clause-granular evidence and
 * a degraded whole-document fallback are different product claims, so the surface says
 * which one it is holding and never implies clause-level precision it does not have.
 */

import { AlertTriangle, FileQuestion, Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  CategoryCoverageState,
  CoherenceCategory,
  EvidenceGranularity,
  HealthDimension,
  type CategoryAssessment,
  type FindingSignal,
  type HealthVector,
} from "@/lib/api/generated/models";
import { useGetProjectHealthApiV1ProjectsProjectIdHealthGet } from "@/lib/api/generated/project-health/project-health";

const CATEGORY_ORDER: CoherenceCategory[] = [
  CoherenceCategory.SCOPE,
  CoherenceCategory.BUDGET,
  CoherenceCategory.TIME,
  CoherenceCategory.TECHNICAL,
  CoherenceCategory.LEGAL,
  CoherenceCategory.QUALITY,
];

const UNKNOWN_LABEL = "Unknown / Insufficient evidence";

/** Emitted by the contract scorer only when a coherence subscore was available. */
export const COHERENCE_SUBSCORE_EVIDENCE_REF = "project-coherence-subscore";

/** A category the payload omits is unknown, never quietly absent (INV-1). */
function assessmentFor(
  category: CoherenceCategory,
  assessments: CategoryAssessment[],
): CategoryAssessment {
  return (
    assessments.find((a) => a.category === category) ?? {
      category,
      state: CategoryCoverageState.insufficient_evidence,
    }
  );
}

/**
 * Whether a relational Coherence subscore was actually folded into this vector.
 *
 * ``coherence_subscore`` is deliberately NOT a field on the HealthVector contract — it
 * is an input to the contract scorer, which records the outcome structurally: the
 * ``project-coherence-subscore`` evidence ref is attached to the CONTRACT dimension
 * ONLY when a subscore existed. So this asks for positive evidence rather than
 * inferring from an absent field, which keeps it on the right side of INV-1: no
 * Coherence claim without something backing it.
 */
export function coherenceSubscoreIsIncorporated(
  vector: HealthVector | undefined,
): boolean {
  const contract = vector?.dimensions?.find(
    (signal) => signal.dimension === HealthDimension.contract,
  );
  return (contract?.evidence ?? []).some(
    (ref) => ref.ref_id === COHERENCE_SUBSCORE_EVIDENCE_REF,
  );
}

function statusOf(error: unknown): number | undefined {
  if (typeof error !== "object" || error === null) return undefined;
  const response = (error as { response?: { status?: unknown } }).response;
  return typeof response?.status === "number" ? response.status : undefined;
}

function GranularityDisclosure({
  granularity,
}: {
  granularity?: EvidenceGranularity | null;
}) {
  const text =
    granularity === EvidenceGranularity.clause
      ? "Evidence is clause-level: each reference below points at a specific clause of the document."
      : granularity === EvidenceGranularity.document
        ? "Evidence is whole-document only: this document was not segmented into clauses, so references identify the document rather than a specific clause."
        : "Evidence granularity was not reported for this analysis.";

  return (
    <p data-testid="health-granularity" className="text-sm text-muted-foreground">
      {text}
    </p>
  );
}

function CategoryTile({ assessment }: { assessment: CategoryAssessment }) {
  const isPresent = assessment.state === CategoryCoverageState.present;
  const evidenceIds = assessment.evidence_clause_ids ?? [];
  const missingData = assessment.missing_data ?? [];
  const findings = assessment.findings ?? [];

  return (
    <div
      data-testid={`health-category-${assessment.category}`}
      className="rounded-lg border bg-card p-4"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-foreground">{assessment.category}</h3>
        {/* Textual state, never colour alone (a11y). */}
        <span
          data-testid="health-state"
          className={
            isPresent
              ? "text-xs font-medium text-emerald-700 dark:text-emerald-400"
              : "text-xs font-medium text-amber-700 dark:text-amber-400"
          }
        >
          {isPresent ? "Evidence found" : UNKNOWN_LABEL}
        </span>
      </div>

      <p className="mt-2 text-xs text-muted-foreground">
        Supporting clauses:{" "}
        <span data-testid="health-evidence-count" className="font-mono text-foreground">
          {evidenceIds.length || assessment.evidence_count || 0}
        </span>
      </p>

      {evidenceIds.length > 0 && (
        <ul data-testid="health-evidence-ids" className="mt-1 space-y-0.5">
          {evidenceIds.map((id) => (
            <li key={id} className="truncate font-mono text-[11px] text-muted-foreground">
              {id}
            </li>
          ))}
        </ul>
      )}

      {findings.length > 0 && (
        <ul data-testid="health-findings" className="mt-2 space-y-1">
          {findings.map((finding, index) => (
            <li key={finding.rule_id ?? index} className="text-xs text-foreground">
              {finding.evidence_summary ?? finding.rule_id}
            </li>
          ))}
        </ul>
      )}

      {missingData.length > 0 && (
        <p data-testid="health-missing-data" className="mt-2 text-xs text-muted-foreground">
          Missing: {missingData.join(", ")}
        </p>
      )}

      {assessment.gap && (
        <p
          data-testid="health-gap"
          className="mt-2 rounded-md bg-muted px-2 py-1 text-xs text-foreground"
        >
          {assessment.gap.action}
        </p>
      )}
    </div>
  );
}

function CrossFindings({ findings }: { findings: FindingSignal[] }) {
  if (findings.length === 0) return null;
  return (
    <div data-testid="health-cross-findings" className="rounded-lg border bg-card p-4">
      <h3 className="text-sm font-semibold text-foreground">
        Cross-dimensional findings
      </h3>
      <p className="mt-1 text-xs text-muted-foreground">
        These span two dimensions, so they are reported separately rather than attributed
        to a single category.
      </p>
      <ul className="mt-2 space-y-1">
        {findings.map((finding, index) => (
          <li key={finding.rule_id ?? index} className="text-xs text-foreground">
            {finding.evidence_summary ?? finding.rule_id}
          </li>
        ))}
      </ul>
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <Card role="region" aria-label="Document health">
      <CardHeader>
        <CardTitle className="text-sm font-semibold">Document health</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">{children}</CardContent>
    </Card>
  );
}

export function SingleDocumentHealth({ projectId }: { projectId: string }) {
  const { data, isLoading, isError, error } =
    useGetProjectHealthApiV1ProjectsProjectIdHealthGet(projectId);

  if (isLoading) {
    return (
      <Shell>
        <p data-testid="health-loading" className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          Loading document health…
        </p>
      </Shell>
    );
  }

  if (isError) {
    // A project the caller cannot see is a 404 (#581) and reads differently from a
    // backend failure: one is "not yours / not there", the other is "try again".
    if (statusOf(error) === 404) {
      return (
        <Shell>
          <p data-testid="health-not-found" className="flex items-center gap-2 text-sm text-muted-foreground">
            <FileQuestion className="h-4 w-4" aria-hidden="true" />
            This project was not found, or it belongs to another organisation.
          </p>
        </Shell>
      );
    }
    return (
      <Shell>
        <p data-testid="health-error" className="flex items-center gap-2 text-sm text-muted-foreground">
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          Document health could not be loaded. This is a loading failure, not a finding —
          no conclusion should be drawn from it.
        </p>
      </Shell>
    );
  }

  const coverage = data?.single_document_coverage;
  if (!coverage) {
    // Not evaluated is not the same as evaluated-and-empty; say so rather than
    // rendering six confident "unknown" tiles for an analysis that never ran.
    return (
      <Shell>
        <p data-testid="health-unavailable" className="text-sm text-muted-foreground">
          No document assessment is available for this project yet. Upload and analyse a
          contract to see per-category coverage.
        </p>
      </Shell>
    );
  }

  const assessments = coverage.assessments ?? [];
  const crossFindings = coverage.cross_findings ?? [];

  return (
    <Shell>
      <GranularityDisclosure
        granularity={data?.single_document_evidence_granularity}
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CATEGORY_ORDER.map((category) => (
          <CategoryTile
            key={category}
            assessment={assessmentFor(category, assessments)}
          />
        ))}
      </div>

      <CrossFindings findings={crossFindings} />

      {!coherenceSubscoreIsIncorporated(data) && (
        <p data-testid="health-coherence-note" className="text-xs text-muted-foreground">
          Coherence is not available for this analysis yet. Availability depends on
          having enough reconcilable evidence to evaluate consistency.
        </p>
      )}
    </Shell>
  );
}
