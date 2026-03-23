import { useQuery } from "@tanstack/react-query";
import { listProjects } from "@/lib/api/services/dashboard";

export const useProjects = (enabled: boolean = true) =>
  useQuery({
    queryKey: ["projects"],
    queryFn: () => listProjects(),
    enabled,
  });
