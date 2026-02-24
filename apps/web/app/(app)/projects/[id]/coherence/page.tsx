import { CoherenceService } from '@/lib/api/generated/services/CoherenceService';
import type { DashboardSummary } from '@/lib/api/generated/models';
import { CoherenceClient } from '@/components/coherence/CoherenceClient';

export default async function ProjectCoherencePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let summary: DashboardSummary | null = null;
  let loadError: string | null = null;

  try {
    summary = await CoherenceService.getScore(id);
  } catch (error) {
    loadError =
      error instanceof Error
        ? error.message
        : 'Could not load coherence data right now.';
  }

  return (
    <div className="space-y-5">
      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {loadError}. Verify backend API is running at{' '}
          <code>http://localhost:8000</code>.
        </div>
      ) : null}

      {summary ? <CoherenceClient summary={summary} /> : null}
    </div>
  );
}
