import { listDocumentsForProjectApiV1ProjectsProjectIdDocumentsGet } from "@/lib/api/generated/documents/documents";
import type { ProjectDocumentsGroup } from "@/lib/api/contracts";
import { listProjects } from "@/lib/api/services/dashboard";

export async function listProjectDocumentGroups(): Promise<
  ProjectDocumentsGroup[]
> {
  const projects = await listProjects();

  const settled = await Promise.allSettled(
    projects.map(async (project): Promise<ProjectDocumentsGroup> => {
      const response =
        await listDocumentsForProjectApiV1ProjectsProjectIdDocumentsGet(
          project.id,
        );

      return {
        projectId: project.id,
        projectName: project.name,
        documents: (response.items ?? []).map((document) => ({
          ...document,
          project_id: project.id,
        })),
      };
    }),
  );

  return settled
    .filter(
      (result): result is PromiseFulfilledResult<ProjectDocumentsGroup> =>
        result.status === "fulfilled",
    )
    .map((result) => result.value)
    .filter((group) => group.documents.length > 0);
}
