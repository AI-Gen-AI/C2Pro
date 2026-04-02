import { useQueryClient } from "@tanstack/react-query";
import {
  useUpdateProjectApiV1ProjectsProjectIdPatch,
  type UpdateProjectApiV1ProjectsProjectIdPatchMutationBody,
} from "@/lib/api/generated/projects/projects";

export function useUpdateProject() {
  const queryClient = useQueryClient();

  return useUpdateProjectApiV1ProjectsProjectIdPatch(
    {
      mutation: {
        onSettled: async () => {
          await queryClient.invalidateQueries({ queryKey: ["projects"] });
        },
      },
    },
    queryClient,
  );
}

export type UpdateProjectInput = UpdateProjectApiV1ProjectsProjectIdPatchMutationBody;
