import { useQueryClient } from "@tanstack/react-query";
import {
  useEvaluateProjectCoherenceApiV1CoherenceEvaluatePost,
} from "@/lib/api/generated/coherence-engine/coherence-engine";
import { useAnalyzeDocumentApiV1AnalysisAnalyzePost } from "@/lib/api/generated/analysis/analysis";
import { getGetCoherenceDashboardApiCoherenceDashboardProjectIdGetQueryKey } from "@/lib/api/generated/coherence-dashboard/coherence-dashboard";
import { getListProjectAlertsApiV1AlertsProjectsProjectIdGetQueryKey } from "@/lib/api/generated/alerts/alerts";
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
  const evaluateMutation = useEvaluateProjectCoherenceApiV1CoherenceEvaluatePost();
  const analyzeMutation = useAnalyzeDocumentApiV1AnalysisAnalyzePost();

  const invalidateProjectCoherence = async () => {
    await queryClient.invalidateQueries({
      queryKey: getGetCoherenceDashboardApiCoherenceDashboardProjectIdGetQueryKey(projectId),
    });
    await queryClient.invalidateQueries({
      queryKey: getListProjectAlertsApiV1AlertsProjectsProjectIdGetQueryKey(projectId),
    });
    await queryClient.invalidateQueries({
      queryKey: ["project-documents", projectId],
    });
  };

  const evaluateCoherence = async () => {
    const result = await evaluateMutation.mutateAsync({
      data: { project_id: projectId },
    });
    await invalidateProjectCoherence();
    showToast(evaluatedToastMessage(result));
  };

  const rerunAnalysis = async () => {
    await analyzeMutation.mutateAsync({
      data: { project_id: projectId },
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
