"use client";

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { fetchApiJson } from "@/lib/api/services/http";

type SourceRow = {
  document_id: string;
  revision_id: string;
  source_locator: string;
  unit_sha256: string;
  kind?: string | null;
  fields: Record<string, unknown>;
};

type SourceFamily = {
  observed_rows: number;
  preview_rows: SourceRow[];
  truncated: boolean;
  state: string;
  coverage: string;
  baseline_approved: boolean;
};

type ProjectSourceEvidence = {
  state: string;
  baseline_approved: boolean;
  budget: SourceFamily;
  schedule: SourceFamily;
};

const DISPLAY_FIELDS = [
  "item", "description", "quantity", "qty", "unit",
  "unit_price", "total", "currency", "task", "activity",
  "start_date", "end_date", "planned_start", "planned_finish",
  "predecessors",
];

export function displaySourceFields(fields: Record<string, unknown>): string {
  const parts = DISPLAY_FIELDS.filter((name) => fields[name] != null)
    .slice(0, 6)
    .map((name) => {
      const value = fields[name];
      const text = typeof value === "string" || typeof value === "number"
        ? String(value) : "unavailable";
      return `${name}: ${text}`;
    });
  return parts.join(" · ") || "Source row recorded (no displayable fields)";
}

function SourceFamilyPanel({
  title,
  family,
}: {
  title: string;
  family: SourceFamily;
}) {
  return (
    <section className="space-y-2" aria-label={title}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-sm font-semibold">{title}</h4>
        <span className="text-xs text-muted-foreground">
          {family.observed_rows} source rows · Coverage not assessed
        </span>
      </div>
      {family.observed_rows === 0 ? (
        <p className="text-xs text-muted-foreground">
          No current original source rows verified. This does not mean zero budget or no schedule.
        </p>
      ) : (
        <ul className="space-y-2">
          {family.preview_rows.map((row) => (
            <li key={`${row.document_id}:${row.revision_id}:${row.source_locator}`}
              className="rounded-md border p-2 text-xs">
              <div className="font-medium">{row.source_locator}</div>
              <div className="mt-1 text-muted-foreground">{displaySourceFields(row.fields)}</div>
              <div className="mt-1 text-muted-foreground">
                Document {row.document_id.slice(0, 8)} · Revision {row.revision_id.slice(0, 8)}
              </div>
            </li>
          ))}
        </ul>
      )}
      {family.truncated ? (
        <p className="text-xs text-muted-foreground">
          Preview only. Additional rows exist in the source register.
        </p>
      ) : null}
    </section>
  );
}

export function ProjectSourceEvidenceCard({ projectId }: { projectId: string }) {
  const query = useQuery({
    queryKey: ["core-original-source-observations", projectId],
    queryFn: () => fetchApiJson<ProjectSourceEvidence>(
      `projects/${projectId}/reports/source-evidence`,
      { cache: "no-store" },
    ),
    enabled: Boolean(projectId),
    retry: false,
  });

  return (
    <Card data-testid="core-source-evidence">
      <CardHeader>
        <CardTitle className="text-sm">Original budget and schedule evidence</CardTitle>
        <p className="text-xs text-muted-foreground">
          Observed source rows are not an approved budget or programme baseline.
          Quantities and dates are shown as recorded, without inferred calculations.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {query.isPending ? (
          <p className="text-sm text-muted-foreground">Checking original source observations…</p>
        ) : query.isError ? (
          <p role="status" className="text-sm text-muted-foreground">
            Source observations are unavailable. This is not evidence of a zero budget or empty schedule.
          </p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              {query.data.state === "SOURCE_OBSERVED_NOT_APPROVED"
                ? "Original rows found. Human review and baseline approval remain pending."
                : "No canonical source rows available. Coverage and completeness not assessed."}
            </p>
            <div className="grid gap-5 lg:grid-cols-2">
              <SourceFamilyPanel title="Budget line items" family={query.data.budget} />
              <SourceFamilyPanel title="Schedule activities" family={query.data.schedule} />
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
