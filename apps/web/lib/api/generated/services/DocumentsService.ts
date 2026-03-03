import type {
  DocumentListItem,
  DocumentListResponse,
  ProjectDocumentsGroup,
} from "@/lib/api/generated/models";
import { request } from "@/lib/api/generated/core/request";
import { ProjectsService } from "./ProjectsService";

export class DocumentsService {
  /**
   * List documents for a single project.
   */
  public static getProjectDocuments(
    projectId: string
  ): Promise<DocumentListResponse> {
    return request<DocumentListResponse>({
      method: "GET",
      url: `/projects/${projectId}/documents`,
    });
  }

  /**
   * List all documents across every project, grouped by project.
   *
   * 1. Fetches the project list via ProjectsService.
   * 2. Fetches documents for each project in parallel.
   * 3. Returns an array of ProjectDocumentsGroup (only projects with ≥1 doc).
   */
  public static async list(): Promise<ProjectDocumentsGroup[]> {
    const { items: projects } = await ProjectsService.getProjects();

    const settled = await Promise.allSettled(
      projects.map(async (project): Promise<ProjectDocumentsGroup> => {
        const response = await DocumentsService.getProjectDocuments(project.id);
        const docs: DocumentListItem[] = (response.items ?? response as unknown as DocumentListItem[]).map(
          (d) => ({ ...d, project_id: project.id })
        );
        return {
          projectId: project.id,
          projectName: project.name,
          documents: docs,
        };
      })
    );

    return settled
      .filter(
        (r): r is PromiseFulfilledResult<ProjectDocumentsGroup> =>
          r.status === "fulfilled"
      )
      .map((r) => r.value)
      .filter((g) => g.documents.length > 0);
  }
}
