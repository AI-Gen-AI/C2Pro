import { useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api/client";
import type { ProjectDetailResponse } from "@/lib/api/types";

const fetchProject = async (projectId: string) => {
  const response = await apiClient.get<ProjectDetailResponse>(
    `/projects/${projectId}`
  );
  return response.data;
};

export const useProject = (projectId?: string | null) =>
  useQuery({
    queryKey: ["project", projectId],
    queryFn: () => fetchProject(projectId as string),
    enabled: Boolean(projectId),
  });
