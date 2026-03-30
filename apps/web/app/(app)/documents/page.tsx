import type { ProjectDocumentsGroup } from "@/lib/api/contracts";
import { DocumentsListClient } from "@/components/features/documents/DocumentsListClient";
import { Button } from "@/components/ui/button";
import { listDocumentsForProjectApiV1ProjectsProjectIdDocumentsGet } from "@/lib/api/generated/documents/documents";
import { listProjectsApiV1ProjectsGet } from "@/lib/api/generated/projects/projects";
import { Upload } from "lucide-react";

export default async function DocumentsPage() {
  let groups: ProjectDocumentsGroup[] = [];
  let loadError: string | null = null;

  try {
    const projectsResponse = await listProjectsApiV1ProjectsGet();
    const projects = projectsResponse.items ?? [];

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

    groups = settled
      .filter(
        (result): result is PromiseFulfilledResult<ProjectDocumentsGroup> =>
          result.status === "fulfilled",
      )
      .map((result) => result.value)
      .filter((group) => group.documents.length > 0);
  } catch (error) {
    loadError =
      error instanceof Error
        ? error.message
        : "Could not load documents right now.";
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Documents
          </h1>
          <p className="text-sm text-muted-foreground">
            All project documents in one place
          </p>
        </div>
        <Button>
          <Upload className="mr-2 h-4 w-4" />
          Upload Document
        </Button>
      </div>

      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {loadError}. Verify backend API is running at{" "}
          <code>http://localhost:8000/api/v1</code>.
        </div>
      ) : null}

      <DocumentsListClient groups={groups} />
    </div>
  );
}
