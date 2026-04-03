import type { ProjectListItem } from "@/lib/api/contracts";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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

  function formatStatus(status?: string | null): string {
    if (!status) {
      return "Draft";
    }

    return status
      .split("_")
      .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
      .join(" ");
  }

  function formatUpdatedAt(value?: string | null): string {
    if (!value) {
      return "—";
    }

    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "—";
    }

    return date.toLocaleDateString();
  }

  function renderTrendDelta(
    value?: number | null,
    palette: "score" | "alerts" = "score",
  ) {
    if (value == null || value === 0) {
      return null;
    }

    const isPositive = value > 0;
    const arrow = isPositive ? "▲" : "▼";
    const signedValue = `${isPositive ? "+" : ""}${value}`;
    const tone =
      palette === "score"
        ? isPositive
          ? "text-emerald-600"
          : "text-rose-600"
        : isPositive
          ? "text-rose-600"
          : "text-emerald-600";

    return (
      <span className={`text-xs font-semibold ${tone}`}>
        {arrow} {signedValue}
      </span>
    );
  }

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
    <div className="overflow-hidden rounded-2xl border bg-card shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full" aria-label="Project list">
          <thead className="border-b bg-muted/30">
            <tr>
              <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                ID
              </th>
              <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Project
              </th>
              {showDescription ? (
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Description
                </th>
              ) : null}
              {showCode ? (
                <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  Code
                </th>
              ) : null}
              <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Status
              </th>
              <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Coherence Score
              </th>
              <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Alerts
              </th>
              <th className="px-4 py-4 text-left text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Updated
              </th>
              <th className="px-4 py-4 text-right text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {projects.map((project) => (
              <tr
                key={project.id}
                className="transition-colors hover:bg-muted/20"
              >
                <td className="px-4 py-4 font-mono text-xs text-muted-foreground">
                  {project.id}
                </td>
                <td className="px-4 py-4">
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
                      className="text-sm font-semibold text-foreground hover:text-primary"
                    >
                      {project.name}
                    </Link>
                  )}
                </td>
                {showDescription ? (
                  <td className="px-4 py-4 text-sm text-muted-foreground">
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
                  <td className="px-4 py-4 font-mono text-xs text-muted-foreground">
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
                <td className="px-4 py-4">
                  <Badge className="rounded-full bg-slate-900 px-2.5 py-1 text-white hover:bg-slate-900">
                    {formatStatus(project.status)}
                  </Badge>
                </td>
                <td className="px-4 py-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">
                      {project.coherence_score ?? "—"}
                    </span>
                    {renderTrendDelta(project.coherence_score_delta, "score")}
                  </div>
                </td>
                <td className="px-4 py-4">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-foreground">
                      {project.alert_count ?? "—"}
                    </span>
                    {renderTrendDelta(project.alert_count_delta, "alerts")}
                  </div>
                </td>
                <td className="px-4 py-4 text-sm text-muted-foreground">
                  {formatUpdatedAt(project.updated_at)}
                </td>
                <td className="px-4 py-4">
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
