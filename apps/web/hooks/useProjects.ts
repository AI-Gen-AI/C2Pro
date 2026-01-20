import { useQuery } from "@tanstack/react-query";
import { ProjectsService } from "@/lib/api/generated";

export const useProjects = () =>
  useQuery({
    queryKey: ["projects"],
    queryFn: () => ProjectsService.getProjects(),
  });
