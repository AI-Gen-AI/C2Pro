import { DashboardClient } from "@/components/coherence/DashboardClient";
import { ProjectsService } from "@/lib/api/generated/services/ProjectsService";
import { DashboardService } from "@/lib/api/generated/services/DashboardService";
import type { DashboardSummary } from "@/lib/api/generated/models";

export default async function DashboardPage() {
  let data: DashboardSummary | null = null;
  let projectName = "";
  let loadError: string | null = null;

  try {
    const projects = await ProjectsService.getProjects();
    const first = projects.items?.[0];

    if (first) {
      projectName = first.name;
      data = await DashboardService.getSummary(first.id);
    } else {
      loadError = "No projects found. Create a project to see coherence data.";
    }
  } catch (error) {
    loadError =
      error instanceof Error
        ? error.message
        : "Could not load dashboard data right now.";
  }

  if (loadError || !data) {
    return (
      <div className="space-y-5">
        <h1 className="text-[22px] font-semibold text-foreground">
          Coherence Dashboard
        </h1>
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {loadError ?? "No data available."} Verify backend API is running at{" "}
          <code className="rounded bg-destructive/10 px-1">
            {process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}
          </code>
          .
        </div>
      </div>
    );
  }

  return <DashboardClient data={data} projectName={projectName} />;
}
