import { ProjectsService } from "@/lib/api/generated/services/ProjectsService";
import type { ProjectListItemResponse } from "@/lib/api/generated/models";
import { ProjectListTable } from "@/components/features/projects/ProjectListTable";

export default async function ProjectsPage() {
  let projects: ProjectListItemResponse[] = [];
  let loadError: string | null = null;

  try {
    const response = await ProjectsService.getProjects();
    projects = response.items ?? [];
  } catch (error) {
    loadError =
      error instanceof Error
        ? error.message
        : "Could not load projects right now.";
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Projects
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage and monitor all your projects
          </p>
        </div>
        <span className="text-xs text-muted-foreground">
          {projects.length} projects
        </span>
      </div>

      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {loadError}. Verify backend API is running at{" "}
          <code>http://localhost:8000/api/v1</code>.
        </div>
      ) : null}

      <ProjectListTable projects={projects} />
    </div>
  );
}
