import type { ProjectListItemResponse } from "@/lib/api/generated/models";
import Link from "next/link";
import { FolderOpen } from "lucide-react";

interface ProjectListTableProps {
  projects: ProjectListItemResponse[];
}

export function ProjectListTable({ projects }: ProjectListTableProps) {
  if (projects.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed bg-card py-16 text-center">
        <FolderOpen className="mb-3 h-10 w-10 text-muted-foreground/50" />
        <h3 className="text-sm font-medium text-foreground">No projects yet</h3>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">
          Create your first project to start tracking coherence, documents, and
          alerts.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border bg-card">
      <div className="overflow-x-auto">
        <table className="w-full" aria-label="Project list">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                Project
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                Description
              </th>
              <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                Code
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {projects.map((project) => (
              <tr key={project.id} className="transition-colors hover:bg-muted/30">
                <td className="px-4 py-3">
                  <Link
                    href={`/projects/${project.id}`}
                    className="text-sm font-medium text-primary-text hover:underline"
                  >
                    {project.name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-sm text-muted-foreground">
                  {project.description ?? "—"}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                  {project.code ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
