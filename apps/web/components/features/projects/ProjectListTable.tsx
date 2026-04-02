import type { ProjectListItem } from "@/lib/api/contracts";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import Link from "next/link";
import { FolderOpen } from "lucide-react";

export const PROJECT_TABLE_OPTIONAL_COLUMNS = ["description", "code"] as const;

export type ProjectTableOptionalColumn =
  (typeof PROJECT_TABLE_OPTIONAL_COLUMNS)[number];

interface ProjectListTableProps {
  projects: ProjectListItem[];
  visibleColumns?: readonly ProjectTableOptionalColumn[];
  editingProjectId?: string | null;
  editDraft?: {
    name: string;
    description: string;
    code: string;
  };
  isSaving?: boolean;
  onStartEdit?: (project: ProjectListItem) => void;
  onEditDraftChange?: (
    field: "name" | "description" | "code",
    value: string,
  ) => void;
  onSaveEdit?: () => void;
  onCancelEdit?: () => void;
  onQuickView?: (project: ProjectListItem) => void;
}

export function ProjectListTable({
  projects,
  visibleColumns = PROJECT_TABLE_OPTIONAL_COLUMNS,
  editingProjectId = null,
  editDraft,
  isSaving = false,
  onStartEdit,
  onEditDraftChange,
  onSaveEdit,
  onCancelEdit,
  onQuickView,
}: ProjectListTableProps) {
  const showDescription = visibleColumns.includes("description");
  const showCode = visibleColumns.includes("code");

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
              {showDescription ? (
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  Description
                </th>
              ) : null}
              {showCode ? (
                <th className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">
                  Code
                </th>
              ) : null}
              <th className="px-4 py-3 text-right text-xs font-medium text-muted-foreground">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {projects.map((project) => (
              <tr
                key={project.id}
                className="transition-colors hover:bg-muted/30"
              >
                <td className="px-4 py-3">
                  {editingProjectId === project.id ? (
                    <Input
                      aria-label="Project name"
                      value={editDraft?.name ?? project.name}
                      onChange={(event) =>
                        onEditDraftChange?.("name", event.target.value)
                      }
                    />
                  ) : (
                    <Link
                      href={`/projects/${project.id}`}
                      className="text-sm font-medium text-primary-text hover:underline"
                    >
                      {project.name}
                    </Link>
                  )}
                </td>
                {showDescription ? (
                  <td className="px-4 py-3 text-sm text-muted-foreground">
                    {editingProjectId === project.id ? (
                      <Input
                        aria-label="Project description"
                        value={editDraft?.description ?? (project.description ?? "")}
                        onChange={(event) =>
                          onEditDraftChange?.("description", event.target.value)
                        }
                      />
                    ) : (
                      project.description ?? "—"
                    )}
                  </td>
                ) : null}
                {showCode ? (
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {editingProjectId === project.id ? (
                      <Input
                        aria-label="Project code"
                        value={editDraft?.code ?? (project.code ?? "")}
                        onChange={(event) =>
                          onEditDraftChange?.("code", event.target.value)
                        }
                      />
                    ) : (
                      project.code ?? "—"
                    )}
                  </td>
                ) : null}
                <td className="px-4 py-3">
                  <div className="flex justify-end gap-2">
                    {editingProjectId === project.id ? (
                      <>
                        <Button
                          type="button"
                          size="sm"
                          onClick={onSaveEdit}
                          disabled={isSaving}
                          aria-label="Save project changes"
                        >
                          Save
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={onCancelEdit}
                          disabled={isSaving}
                          aria-label={`Cancel editing ${project.name}`}
                        >
                          Cancel
                        </Button>
                      </>
                    ) : (
                      <>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => onQuickView?.(project)}
                          aria-label={`Quick view ${project.name}`}
                        >
                          Quick View
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          onClick={() => onStartEdit?.(project)}
                          aria-label={`Edit ${project.name}`}
                        >
                          Edit
                        </Button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
