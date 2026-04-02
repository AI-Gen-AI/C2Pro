import type { ProjectListItem } from "@/lib/api/contracts";
import Link from "next/link";

const KANBAN_COLUMNS = [
  { id: "draft", label: "Draft" },
  { id: "active", label: "Active" },
  { id: "completed", label: "Completed" },
  { id: "archived", label: "Archived" },
  { id: "other", label: "Other" },
] as const;

function normalizeStatus(project: ProjectListItem): (typeof KANBAN_COLUMNS)[number]["id"] {
  const rawStatus = String(project.status ?? "").toLowerCase();

  if (rawStatus === "draft") {
    return "draft";
  }
  if (rawStatus === "active") {
    return "active";
  }
  if (rawStatus === "completed") {
    return "completed";
  }
  if (rawStatus === "archived") {
    return "archived";
  }

  return "other";
}

interface ProjectKanbanBoardProps {
  projects: ProjectListItem[];
}

export function ProjectKanbanBoard({ projects }: ProjectKanbanBoardProps) {
  const groupedProjects = KANBAN_COLUMNS.map((column) => ({
    ...column,
    projects: projects.filter((project) => normalizeStatus(project) === column.id),
  }));

  return (
    <div
      className="grid gap-4 lg:grid-cols-5"
      aria-label="Project kanban board"
    >
      {groupedProjects.map((column) => (
        <section
          key={column.id}
          className="rounded-md border bg-card p-4"
          aria-labelledby={`project-kanban-${column.id}`}
        >
          <div className="mb-3 flex items-center justify-between">
            <h2
              id={`project-kanban-${column.id}`}
              className="text-sm font-semibold text-foreground"
            >
              {column.label}
            </h2>
            <span className="text-xs text-muted-foreground">
              {column.projects.length}
            </span>
          </div>
          <div className="space-y-3">
            {column.projects.length > 0 ? (
              column.projects.map((project) => (
                <article
                  key={project.id}
                  className="rounded-md border bg-background p-3"
                >
                  <Link
                    href={`/projects/${project.id}`}
                    className="text-sm font-medium text-primary-text hover:underline"
                  >
                    {project.name}
                  </Link>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {project.description ?? "—"}
                  </p>
                  <p className="mt-2 font-mono text-xs text-muted-foreground">
                    {project.code ?? "—"}
                  </p>
                </article>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No projects</p>
            )}
          </div>
        </section>
      ))}
    </div>
  );
}
