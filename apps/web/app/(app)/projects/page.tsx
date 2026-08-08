"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useProjects } from "@/hooks/useProjects";
import { useProjectQuickViewSummary } from "@/hooks/useProjectQuickViewSummary";
import { useUpdateProject } from "@/hooks/useUpdateProject";
import { useSearchParams } from "next/navigation";
import { CreateProjectWizard } from "@/components/features/projects/CreateProjectWizard";
import {
  PROJECT_TABLE_OPTIONAL_COLUMNS,
  ProjectListTable,
  type ProjectTableOptionalColumn,
} from "@/components/features/projects/ProjectListTable";
import { ProjectKanbanBoard } from "@/components/features/projects/ProjectKanbanBoard";
import { useAuthStore } from "@/stores/auth";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Loader2, Plus, Settings2 } from "lucide-react";
import type { ProjectListItem, ProjectQuickViewAlert } from "@/lib/api/contracts";



type ProjectFilterPreset = {
  id: string;
  name: string;
  searchQuery: string;
  visibleColumns: ProjectTableOptionalColumn[];
};

type ProjectStatusFilter =
  | "all"
  | "draft"
  | "active"
  | "completed"
  | "archived"
  | "on_hold";

type ProjectTypeFilter =
  | "all"
  | "epc"
  | "civil"
  | "building"
  | "maritime"
  | "chemical"
  | "energy"
  | "municipal"
  | "oil_gas"
  | "mining";



type SavePresetDraft = {
  name: string;
};


const PROJECT_COLUMN_LABELS: Record<ProjectTableOptionalColumn, string> = {
  description: "Description",
  code: "Code",
};

const PROJECT_FILTER_PRESETS_STORAGE_KEY = "projects:list:filter-presets";
const PROJECT_STATUS_FILTER_OPTIONS: Array<{
  value: ProjectStatusFilter;
  label: string;
}> = [
  { value: "all", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "completed", label: "Completed" },
  { value: "archived", label: "Archived" },
  { value: "on_hold", label: "On Hold" },
];
const PROJECT_TYPE_FILTER_OPTIONS: Array<{
  value: ProjectTypeFilter;
  label: string;
}> = [
  { value: "all", label: "All types" },
  { value: "epc", label: "EPC" },
  { value: "civil", label: "Civil" },
  { value: "building", label: "Building" },
  { value: "maritime", label: "Maritime" },
  { value: "chemical", label: "Chemical" },
  { value: "energy", label: "Energy" },
  { value: "municipal", label: "Municipal" },
  { value: "oil_gas", label: "Oil & Gas" },
  { value: "mining", label: "Mining" },
];


const DEFAULT_SAVE_PRESET_DRAFT: SavePresetDraft = {
  name: "",
};


function matchesProjectFilters(
  project: ProjectListItem,
  statusFilter: ProjectStatusFilter,
  typeFilter: ProjectTypeFilter,
): boolean {
  const matchesStatus = statusFilter === "all" || project.status === statusFilter;
  const matchesType = typeFilter === "all" || project.project_type === typeFilter;
  return matchesStatus && matchesType;
}

function sanitizeFilename(value: string): string {
  return value
    .trim()
    .replace(/[^a-z0-9_.-]+/gi, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "")
    .toLowerCase();
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function createProjectsWorkbook(projects: ProjectListItem[]): string {
  const rows = projects
    .map(
      (project) =>
        `<Row><Cell><Data ss:Type="String">${escapeXml(project.name)}</Data></Cell><Cell><Data ss:Type="String">${escapeXml(project.description ?? "")}</Data></Cell><Cell><Data ss:Type="String">${escapeXml(project.code ?? "")}</Data></Cell></Row>`,
    )
    .join("");

  return `<?xml version="1.0"?>
<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet"
 xmlns:o="urn:schemas-microsoft-com:office:office"
 xmlns:x="urn:schemas-microsoft-com:office:excel"
 xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">
  <Worksheet ss:Name="Projects">
    <Table>
      <Row><Cell><Data ss:Type="String">Project</Data></Cell><Cell><Data ss:Type="String">Description</Data></Cell><Cell><Data ss:Type="String">Code</Data></Cell></Row>
      ${rows}
    </Table>
  </Worksheet>
</Workbook>`;
}

function downloadBlob(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function sanitizePresetId(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

function loadProjectFilterPresets(): ProjectFilterPreset[] {
  const rawValue = window.localStorage.getItem(PROJECT_FILTER_PRESETS_STORAGE_KEY);
  if (!rawValue) {
    return [];
  }

  try {
    const parsedValue = JSON.parse(rawValue) as ProjectFilterPreset[];
    if (!Array.isArray(parsedValue)) {
      return [];
    }

    return parsedValue.filter(
      (preset) =>
        typeof preset?.id === "string" &&
        typeof preset?.name === "string" &&
        typeof preset?.searchQuery === "string" &&
        Array.isArray(preset?.visibleColumns),
    );
  } catch {
    return [];
  }
}

function persistProjectFilterPresets(presets: ProjectFilterPreset[]) {
  window.localStorage.setItem(
    PROJECT_FILTER_PRESETS_STORAGE_KEY,
    JSON.stringify(presets),
  );
}

export default function ProjectsPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const createParam = searchParams.get("create");
  const [isCreateWizardOpen, setIsCreateWizardOpenState] = useState(createParam === "1");

  useEffect(() => {
    setIsCreateWizardOpenState(createParam === "1");
  }, [createParam]);

  const setIsCreateWizardOpen = (open: boolean) => {
    setIsCreateWizardOpenState(open);
    if (!open) {
      router.replace("/projects");
    } else {
      router.replace("/projects?create=1");
    }
  };
  const token = useAuthStore((s) => s.token);
  const { data, isLoading, error } = useProjects(!!token);
  const {
    mutateAsync: updateProject,
    isPending: isSavingProject,
    error: updateProjectError,
  } = useUpdateProject();
  const [searchQuery, setSearchQuery] = useState("");
  const [visibleColumns, setVisibleColumns] = useState<
    ProjectTableOptionalColumn[]
  >([...PROJECT_TABLE_OPTIONAL_COLUMNS]);
  const [savedPresets, setSavedPresets] = useState<ProjectFilterPreset[]>([]);
  const [projectRows, setProjectRows] = useState<ProjectListItem[]>([]);
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "kanban">("table");
  const [statusFilter, setStatusFilter] = useState<ProjectStatusFilter>("all");
  const [typeFilter, setTypeFilter] = useState<ProjectTypeFilter>("all");
  const [isSavePresetOpen, setIsSavePresetOpen] = useState(false);
  const [savePresetDraft, setSavePresetDraft] = useState<SavePresetDraft>(
    DEFAULT_SAVE_PRESET_DRAFT,
  );
  const [savePresetError, setSavePresetError] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState({
    name: "",
    description: "",
    code: "",
  });
  const [editError, setEditError] = useState<string | null>(null);
  const [quickViewProject, setQuickViewProject] = useState<ProjectListItem | null>(
    null,
  );

  const projects = useMemo(() => data ?? [], [data]);
  const filteredProjects = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    return projectRows.filter((project) => {
      if (!matchesProjectFilters(project, statusFilter, typeFilter)) return false;
      if (!normalizedQuery) return true;
      const haystack = [project.name, project.description ?? "", project.code ?? ""]
        .join(" ")
        .toLowerCase();
      return haystack.includes(normalizedQuery);
    });
  }, [projectRows, searchQuery, statusFilter, typeFilter]);
  const inlineEditErrorMessage =
    editError ??
    (updateProjectError instanceof Error ? updateProjectError.message : null);
  const loadError =
    error instanceof Error ? error.message : error ? String(error) : null;
  const {
    data: quickViewSummary,
    isLoading: isQuickViewLoading,
    error: quickViewError,
  } = useProjectQuickViewSummary(quickViewProject?.id ?? null);

  useEffect(() => {
    setSavedPresets(loadProjectFilterPresets());
  }, []);

  useEffect(() => {
    setProjectRows(projects);
  }, [projects]);

  function exportProjectsPdf() {
    if (projectRows.length === 0) {
      return;
    }

    const popup = window.open("", "_blank", "noopener,noreferrer,width=960,height=720");
    if (!popup) {
      return;
    }

    const rows = projectRows
      .map(
        (project) =>
          `<tr><td>${escapeXml(project.name)}</td><td>${escapeXml(project.description ?? "—")}</td><td>${escapeXml(project.code ?? "—")}</td></tr>`,
      )
      .join("");

    popup.document.write(`<!DOCTYPE html>
<html lang="en">
  <head>
    <title>Projects Export</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 32px; color: #111827; }
      h1 { margin-bottom: 8px; font-size: 28px; }
      p { margin: 0 0 12px; color: #4b5563; }
      table { width: 100%; border-collapse: collapse; margin-top: 24px; }
      th, td { border: 1px solid #d1d5db; padding: 10px 12px; text-align: left; }
      th { background: #f3f4f6; }
    </style>
  </head>
  <body>
    <h1>Projects Export</h1>
    <p>${projectRows.length} projects included in this report.</p>
    <table>
      <thead>
        <tr><th>Project</th><th>Description</th><th>Code</th></tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
  </body>
</html>`);
    popup.document.close();
    popup.focus();
    popup.print();
  }

  function exportProjectsExcel() {
    if (projectRows.length === 0) {
      return;
    }

    downloadBlob(
      `${sanitizeFilename("projects_export")}.xls`,
      createProjectsWorkbook(projectRows),
      "application/vnd.ms-excel",
    );
  }

  function exportProjectsJson() {
    if (projectRows.length === 0) {
      return;
    }

    downloadBlob(
      `${sanitizeFilename("projects_export")}.json`,
      JSON.stringify(
        {
          exportedAt: new Date().toISOString(),
          totalProjects: projectRows.length,
          projects: projectRows,
        },
        null,
        2,
      ),
      "application/json",
    );
  }

  function updateVisibleColumn(
    column: ProjectTableOptionalColumn,
    nextChecked: boolean,
  ) {
    setVisibleColumns((currentColumns) => {
      if (nextChecked) {
        return currentColumns.includes(column)
          ? currentColumns
          : [...currentColumns, column];
      }

      return currentColumns.filter((currentColumn) => currentColumn !== column);
    });
  }

  function applyFilterPreset(preset: ProjectFilterPreset) {
    setSearchQuery(preset.searchQuery);
    setVisibleColumns(preset.visibleColumns);
  }

  function openSavePresetDialog() {
    setSavePresetDraft({
      name:
        searchQuery.trim().length > 0
          ? `${searchQuery.trim()} preset`
          : "",
    });
    setSavePresetError(null);
    setIsSavePresetOpen(true);
  }

  function saveCurrentPreset() {
    const trimmedName = savePresetDraft.name.trim();
    if (!trimmedName) {
      setSavePresetError("Preset name is required.");
      return;
    }

    const nextPreset: ProjectFilterPreset = {
      id: sanitizePresetId(trimmedName) || `preset-${Date.now()}`,
      name: trimmedName,
      searchQuery,
      visibleColumns,
    };

    setSavedPresets((currentPresets) => {
      const nextPresets = [
        ...currentPresets.filter((preset) => preset.id !== nextPreset.id),
        nextPreset,
      ];
      persistProjectFilterPresets(nextPresets);
      return nextPresets;
    });
    setIsSavePresetOpen(false);
    setSavePresetDraft(DEFAULT_SAVE_PRESET_DRAFT);
    setSavePresetError(null);
  }

  function startEditingProject(project: ProjectListItem) {
    setEditingProjectId(project.id);
    setEditDraft({
      name: project.name,
      description: project.description ?? "",
      code: project.code ?? "",
    });
    setEditError(null);
  }

  function updateEditDraft(
    field: "name" | "description" | "code",
    value: string,
  ) {
    setEditDraft((currentDraft) => ({
      ...currentDraft,
      [field]: value,
    }));
  }

  function cancelEditingProject() {
    setEditingProjectId(null);
    setEditError(null);
  }

  function resetFilters() {
    setSearchQuery("");
    setStatusFilter("all");
    setTypeFilter("all");
  }


  async function saveProjectEdits() {
    if (!editingProjectId) {
      return;
    }

    const trimmedName = editDraft.name.trim();
    if (!trimmedName) {
      setEditError("Project name is required.");
      return;
    }

    try {
      const updatedProject = await updateProject({
        projectId: editingProjectId,
        data: {
          name: trimmedName,
          description: editDraft.description.trim() || null,
          code: editDraft.code.trim() || null,
        },
      });

      setProjectRows((currentProjects) =>
        currentProjects.map((project) =>
          project.id === editingProjectId
            ? {
                ...project,
                ...updatedProject,
              }
            : project,
        ),
      );
      setEditingProjectId(null);
      setEditError(null);
    } catch (mutationError) {
      const message =
        mutationError instanceof Error
          ? mutationError.message
          : "Project update failed.";
      setEditError(message);
    }
  }

  // Show loading while waiting for auth token
  if (!token) {
    return (
      <div className="flex items-center justify-center min-h-[200px]">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        <span className="ml-2 text-sm text-muted-foreground">
          Authenticating...
        </span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight text-foreground">
            Projects
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage and monitor all your projects
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3 xl:justify-end">
          <Button type="button" onClick={() => setIsCreateWizardOpen(true)}>
            <Plus className="mr-2 h-4 w-4" />
            New Project
          </Button>
        </div>
      </div>

      <section className="rounded-2xl border bg-card/80 p-4 shadow-sm">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div className="flex flex-1 flex-wrap items-center gap-3">
            <div className="w-full max-w-sm">
              <Input
                type="search"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                placeholder="Search projects..."
                aria-label="Search projects"
                className="h-11 rounded-xl"
              />
            </div>
            <label className="flex flex-col gap-1 text-sm text-foreground">
              <span className="sr-only">Status Filter</span>
              <select
                aria-label="Status filter"
                className="h-11 min-w-[150px] rounded-xl border border-input bg-background px-3 py-2 text-sm"
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value as ProjectStatusFilter)
                }
              >
                {PROJECT_STATUS_FILTER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm text-foreground">
              <span className="sr-only">Type Filter</span>
              <select
                aria-label="Type filter"
                className="h-11 min-w-[150px] rounded-xl border border-input bg-background px-3 py-2 text-sm"
                value={typeFilter}
                onChange={(event) =>
                  setTypeFilter(event.target.value as ProjectTypeFilter)
                }
              >
                {PROJECT_TYPE_FILTER_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <Button
              type="button"
              variant="outline"
              onClick={resetFilters}
              className="h-11 rounded-xl"
            >
              Reset Filters
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant={viewMode === "table" ? "default" : "outline"}
              onClick={() => setViewMode("table")}
              className="h-11 rounded-xl"
            >
              Table View
            </Button>
            <Button
              type="button"
              variant={viewMode === "kanban" ? "default" : "outline"}
              onClick={() => setViewMode("kanban")}
              className="h-11 rounded-xl"
            >
              Kanban View
            </Button>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-2">
            {statusFilter !== "all" ? (
              <span className="rounded-full border bg-background/95 px-3 py-1 text-xs text-foreground shadow-sm">
                Status: {statusFilter}
              </span>
            ) : null}
            {typeFilter !== "all" ? (
              <span className="rounded-full border bg-background/95 px-3 py-1 text-xs text-foreground shadow-sm">
                Type: {typeFilter}
              </span>
            ) : null}
            {savedPresets.length > 0
              ? savedPresets.map((preset) => (
                  <Button
                    key={preset.id}
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => applyFilterPreset(preset)}
                    className="rounded-full border border-border/70 bg-background/95 shadow-sm hover:bg-muted/60"
                  >
                    {preset.name}
                  </Button>
                ))
              : null}
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-muted-foreground">
              {isLoading
                ? "Loading..."
                : searchQuery.trim().length > 0
                  ? `${filteredProjects.length} of ${projectRows.length} projects`
                  : `${projectRows.length} projects`}
            </span>
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="outline" className="rounded-xl">
                  <Settings2 className="mr-2 h-4 w-4" />
                  Columns
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                sideOffset={10}
                className="w-64 rounded-2xl border-border/80 bg-background/95 p-2 shadow-2xl backdrop-blur-md"
              >
                <DropdownMenuLabel className="rounded-xl border bg-muted/35 px-3 py-3">
                  <div className="flex flex-col">
                    <span className="font-semibold text-foreground">Visible Columns</span>
                    <span className="text-xs font-normal text-muted-foreground">
                      Show or hide optional project metadata.
                    </span>
                  </div>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                {PROJECT_TABLE_OPTIONAL_COLUMNS.map((column) => (
                  <DropdownMenuCheckboxItem
                    key={column}
                    className="rounded-xl px-3 py-2.5"
                    checked={visibleColumns.includes(column)}
                    onCheckedChange={(checked) =>
                      updateVisibleColumn(column, checked === true)
                    }
                  >
                    {PROJECT_COLUMN_LABELS[column]}
                  </DropdownMenuCheckboxItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>
            <Button
              variant="outline"
              onClick={exportProjectsPdf}
              disabled={projectRows.length === 0 || isLoading}
              className="rounded-xl bg-background/95 shadow-sm"
            >
              Export PDF
            </Button>
            <Button
              variant="outline"
              onClick={exportProjectsExcel}
              disabled={projectRows.length === 0 || isLoading}
              className="rounded-xl bg-background/95 shadow-sm"
            >
              Export Excel
            </Button>
            <Button
              variant="outline"
              onClick={exportProjectsJson}
              disabled={projectRows.length === 0 || isLoading}
              className="rounded-xl bg-background/95 shadow-sm"
            >
              Export JSON
            </Button>
            <Button
              type="button"
              variant="outline"
              onClick={openSavePresetDialog}
              className="rounded-xl bg-background/95 shadow-sm"
            >
              Save Preset
            </Button>
          </div>
        </div>
      </section>

      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          API request failed ({loadError}). Verify the backend service is available and try again.
        </div>
      ) : null}

      {inlineEditErrorMessage ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          {inlineEditErrorMessage}
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex items-center justify-center min-h-[200px]">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : viewMode === "kanban" ? (
        <ProjectKanbanBoard projects={filteredProjects} />
      ) : (
        <ProjectListTable
          projects={filteredProjects}
          visibleColumns={visibleColumns}
          editingProjectId={editingProjectId}
          editDraft={editDraft}
          isSaving={isSavingProject}
          onQuickView={setQuickViewProject}
          onStartEdit={startEditingProject}
          onEditDraftChange={updateEditDraft}
          onSaveEdit={saveProjectEdits}
          onCancelEdit={cancelEditingProject}
        />
      )}

      <CreateProjectWizard
        open={isCreateWizardOpen}
        onOpenChange={setIsCreateWizardOpen}
      />

      <Dialog
        open={isSavePresetOpen}
        onOpenChange={(open) => {
          setIsSavePresetOpen(open);
          if (!open) {
            setSavePresetError(null);
          }
        }}
      >
        <DialogContent
          aria-describedby="save-preset-description"
          className="border-border/80 bg-background/95 p-6 shadow-2xl backdrop-blur-md sm:max-w-lg sm:rounded-2xl"
        >
          <DialogHeader className="rounded-2xl border bg-muted/35 px-4 py-4">
            <DialogTitle>Save current preset</DialogTitle>
            <DialogDescription id="save-preset-description">
              Store the current search and visible column layout for quick reuse.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 rounded-2xl border bg-background/90 p-4 shadow-sm">
            <label className="grid gap-2 text-sm text-foreground">
              <span>Preset Name</span>
              <Input
                aria-label="Preset name"
                value={savePresetDraft.name}
                onChange={(event) =>
                  setSavePresetDraft({ name: event.target.value })
                }
                className="rounded-xl border-border/80 bg-background/95"
                placeholder="Executive review"
              />
            </label>
            <div className="rounded-xl border bg-muted/25 p-4 shadow-sm">
              <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Current selection
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {searchQuery.trim() ? (
                  <span className="rounded-full border bg-background/95 px-3 py-1 text-xs text-muted-foreground shadow-sm">
                    Search: {searchQuery.trim()}
                  </span>
                ) : null}
                <span className="rounded-full border bg-background/95 px-3 py-1 text-xs text-muted-foreground shadow-sm">
                  Columns: {visibleColumns.map((column) => PROJECT_COLUMN_LABELS[column]).join(", ")}
                </span>
              </div>
            </div>
          </div>

          {savePresetError ? (
            <div className="rounded-xl border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive shadow-sm">
              {savePresetError}
            </div>
          ) : null}

          <DialogFooter className="flex flex-wrap gap-2 rounded-2xl border bg-background/80 px-4 py-4">
            <Button
              type="button"
              variant="outline"
              className="rounded-xl"
              onClick={() => setIsSavePresetOpen(false)}
            >
              Cancel
            </Button>
            <Button type="button" className="rounded-xl" onClick={saveCurrentPreset}>
              Save preset
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      
      <Sheet
        open={quickViewProject !== null}
        onOpenChange={(open) => {
          if (!open) {
            setQuickViewProject(null);
          }
        }}
      >
        <SheetContent
          side="right"
          className="w-full overflow-y-auto border-l-border/80 bg-background/95 px-5 pb-6 pt-6 shadow-2xl backdrop-blur-md sm:max-w-xl"
        >
          <SheetHeader className="rounded-2xl border bg-muted/35 px-4 py-4 text-left">
            <SheetTitle>Project quick view</SheetTitle>
            <SheetDescription>
              Review the selected project context without leaving the projects list.
            </SheetDescription>
          </SheetHeader>

          {quickViewProject ? (
            <div className="mt-6 space-y-6">
              <section className="rounded-2xl border bg-muted/20 p-5 shadow-sm">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold tracking-tight">
                      {quickViewSummary?.name ?? quickViewProject.name}
                    </h2>
                    <p className="mt-2 text-sm text-muted-foreground">
                      {quickViewSummary?.description ??
                        quickViewProject.description ??
                        "No description available."}
                    </p>
                  </div>
                  <div className="rounded-full border bg-background/90 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground shadow-sm">
                    {(quickViewSummary?.status ?? quickViewProject.status ?? "draft").toString()}
                  </div>
                </div>

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border bg-background/90 p-4 shadow-sm">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Client
                    </div>
                    <div className="mt-2 text-sm font-medium">
                      {quickViewSummary?.client_name ?? "Not assigned"}
                    </div>
                  </div>
                  <div className="rounded-xl border bg-background/90 p-4 shadow-sm">
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                      Code
                    </div>
                    <div className="mt-2 font-mono text-sm">
                      {quickViewSummary?.code ?? quickViewProject.code ?? "—"}
                    </div>
                  </div>
                </div>
              </section>

              {isQuickViewLoading ? (
                <div className="flex items-center gap-2 rounded-xl border bg-background/90 p-4 text-sm text-muted-foreground shadow-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Loading project summary...
                </div>
              ) : quickViewError ? (
                <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive shadow-sm">
                  {quickViewError instanceof Error
                    ? quickViewError.message
                    : "Failed to load project summary."}
                </div>
              ) : (
                <>
                  <section className="grid gap-4 sm:grid-cols-2">
                    <div className="rounded-2xl border bg-background/90 p-5 shadow-sm">
                      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        Coherence score
                      </div>
                      <div className="mt-3 text-4xl font-semibold tracking-tight">
                        {Math.round(quickViewSummary?.coherence_score ?? 0)}
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">
                        Current project health based on the latest backend analysis.
                      </p>
                    </div>
                    <div className="rounded-2xl border bg-background/90 p-5 shadow-sm">
                      <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                        Alert pressure
                      </div>
                      <div className="mt-3 text-sm font-medium text-foreground">
                        {quickViewSummary?.open_alert_count ?? 0} open alerts
                      </div>
                      <p className="mt-2 text-sm text-muted-foreground">
                        {quickViewSummary?.critical_alert_count ?? 0} critical alert
                        {(quickViewSummary?.critical_alert_count ?? 0) === 1 ? "" : "s"}
                      </p>
                    </div>
                  </section>

                  <section className="rounded-2xl border bg-background/90 p-5 shadow-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                          Top alerts
                        </h3>
                        <p className="mt-1 text-sm text-muted-foreground">
                          Ranked unresolved issues from the backend summary endpoint.
                        </p>
                      </div>
                    </div>
                    {quickViewSummary && quickViewSummary.top_alerts.length > 0 ? (
                      <div className="mt-4 space-y-3">
                        {quickViewSummary.top_alerts.map((alert: ProjectQuickViewAlert) => (
                          <div
                            key={alert.id}
                            className="rounded-xl border bg-muted/20 p-4 shadow-sm"
                          >
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <p className="text-sm font-medium text-foreground">
                                  {alert.title}
                                </p>
                                <p className="mt-1 text-xs uppercase tracking-[0.14em] text-muted-foreground">
                                  {alert.severity} severity
                                </p>
                              </div>
                              <span className="rounded-full border bg-background/90 px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground shadow-sm">
                                {alert.status}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="mt-4 rounded-xl border border-dashed bg-muted/20 p-4 text-sm text-muted-foreground shadow-sm">
                        No open alerts in the current quick-view summary.
                      </div>
                    )}
                  </section>
                </>
              )}

              <section className="space-y-3 rounded-2xl border bg-background/90 p-5 shadow-sm">
                <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Quick actions
                </h3>
                <Button asChild className="w-full justify-between">
                  <Link href={`/projects/${quickViewProject.id}`}>
                    Open Full View
                    <span aria-hidden="true">→</span>
                  </Link>
                </Button>
                <Button asChild variant="outline" className="w-full justify-between">
                  <Link href={`/projects/${quickViewProject.id}/evidence`}>
                    View Evidence
                    <span aria-hidden="true">→</span>
                  </Link>
                </Button>
              </section>
            </div>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  );
}
