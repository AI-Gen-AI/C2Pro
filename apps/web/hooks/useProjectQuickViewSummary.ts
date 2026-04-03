import { useQuery } from "@tanstack/react-query";
import { getProjectQuickViewSummary } from "@/lib/api/services/dashboard";

export function useProjectQuickViewSummary(projectId: string | null) {
  return useQuery({
    queryKey: ["projects", "quick-view", projectId],
    queryFn: () => getProjectQuickViewSummary(projectId ?? ""),
    enabled: projectId !== null,
  });
}
