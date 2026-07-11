import { useQueryClient } from "@tanstack/react-query";
import {
  useEvaluateProjectCoherenceV0CoherenceEvaluatePost,
} from "@/lib/api/generated/coherence-engine/coherence-engine";
import { useAnalyzeDocumentApiV1AnalyzePost } from "@/lib/api/generated/analysis/analysis";
import type { AnalyzeRequest, ProjectContext } from "@/lib/api/generated/models";
import { getGetCoherenceDashboardApiCoherenceDashboardProjectIdGetQueryKey } from "@/lib/api/generated/coherence-dashboard/coherence-dashboard";
import { getListProjectAlertsApiV1ProjectsProjectIdAlertsGetQueryKey } from "@/lib/api/generated/alerts/alerts";
import { showToast } from "@/lib/ui/toast";

type CoherenceResultSummary = {
  alerts?: unknown[];
  diagnostics?: {
    total_clauses?: unknown;
    clauses_count?: unknown;
  };
};

function evaluatedToastMessage(result: unknown): string {
  const summary = result as CoherenceResultSummary;
  const rawClauseCount =
    summary.diagnostics?.total_clauses ?? summary.diagnostics?.clauses_count;
  const clauseCount =
    typeof rawClauseCount === "number" && Number.isFinite(rawClauseCount)
      ? rawClauseCount
      : 0;
  const findingsCount = Array.isArray(summary.alerts) ? summary.alerts.length : 0;

  return `Evaluated ${clauseCount} clauses, ${findingsCount} findings.`;
}

export function useProjectCoherenceActions(projectId: string) {
  const queryClient = useQueryClient();
  const evaluateMutation = useEvaluateProjectCoherenceV0CoherenceEvaluatePost();
  const analyzeMutation = useAnalyzeDocumentApiV1AnalyzePost();

  const invalidateProjectCoherence = async () => {
    await queryClient.invalidateQueries({
      queryKey: getGetCoherenceDashboardApiCoherenceDashboardProjectIdGetQueryKey(projectId),
    });
    await queryClient.invalidateQueries({
      queryKey: getListProjectAlertsApiV1ProjectsProjectIdAlertsGetQueryKey(projectId),
    });
    await queryClient.invalidateQueries({
      queryKey: ["project-documents", projectId],
    });
  };

  const evaluateCoherence = async () => {
    const result = await evaluateMutation.mutateAsync({
      data: { project_id: projectId } as unknown as ProjectContext,
    });
    await invalidateProjectCoherence();
    showToast(evaluatedToastMessage(result));
  };

  const rerunAnalysis = async () => {
    await analyzeMutation.mutateAsync({
      data: { project_id: projectId } as unknown as AnalyzeRequest,
    });
    await invalidateProjectCoherence();
    showToast("Analysis preview completed.");
  };

  return {
    evaluateCoherence,
    rerunAnalysis,
    isEvaluating: evaluateMutation.isPending,
    isRerunningAnalysis: analyzeMutation.isPending,
  };
}
