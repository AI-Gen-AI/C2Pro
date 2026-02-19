import type { ProjectListItemResponse } from "@/lib/api/generated/models";
import Link from "next/link";

interface ProjectListTableProps {
  projects: ProjectListItemResponse[];
}

export function ProjectListTable({ projects }: ProjectListTableProps) {
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
            {projects.length === 0 ? (
              <tr>
                <td
                  className="px-4 py-6 text-center text-sm text-muted-foreground"
                  colSpan={3}
                >
                  No projects found.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
