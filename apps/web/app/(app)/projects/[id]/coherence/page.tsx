import type { DashboardSummary } from "@/lib/api/contracts";
import { getDashboardSummary } from "@/lib/api/services/dashboard";
import { CoherenceClient } from "@/components/coherence/CoherenceClient";
import { BarChart3 } from "lucide-react";

export default async function ProjectCoherencePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let summary: DashboardSummary | null = null;
  let loadError: string | null = null;

  try {
    summary = await getDashboardSummary(id);
  } catch (error) {
    loadError =
      error instanceof Error
        ? error.message
        : "Could not load coherence data right now.";
  }

  return (
    <div className="space-y-5">
      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {loadError}. Verify backend API is running at{" "}
          <code>http://localhost:8000</code>.
        </div>
      ) : null}

      {!loadError && !summary ? (
        <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-card py-16 text-center">
          <BarChart3 className="mb-3 h-10 w-10 text-muted-foreground/50" />
          <h3 className="text-sm font-medium text-foreground">
            No coherence data yet
          </h3>
          <p className="mt-1 max-w-sm text-sm text-muted-foreground">
            Upload and analyze documents for this project to generate coherence
            scores.
          </p>
        </div>
      ) : null}

      {summary ? <CoherenceClient summary={summary} /> : null}
    </div>
  );
}
