"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useProjects } from "@/hooks/useProjects";
import { useUpdateProject } from "@/hooks/useUpdateProject";
import {
  LazyProjectBatchImportDialog,
  LazyProjectTemplatesDialog,
} from "@/components/features/projects/LazyProjectDialogs";
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
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Loader2, Plus, Settings2, Upload } from "lucide-react";
import type { ProjectListItem } from "@/lib/api/contracts";

type BatchImportRow = {
  name: string;
  type: string;
  code: string;
};

type ProjectTemplate = {
  id: string;
  name: string;
  summary: string;
  phaseFocus: string[];
  tags: string[];
};

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

const PROJECT_TEMPLATES: ProjectTemplate[] = [
  {
    id: "epc-megaproject",
    name: "EPC Megaproject",
    summary: "Large-scale EPC delivery with multi-lot governance and long-lead procurement tracking.",
    phaseFocus: ["Contract baseline", "Procurement controls", "Risk alignment"],
    tags: ["greenfield", "epc", "multi-package"],
  },
  {
    id: "industrial-retrofit",
    name: "Industrial Retrofit",
    summary: "Industrial retrofit recovery",
    phaseFocus: ["Shutdown planning", "Interface control", "Commissioning readiness"],
    tags: ["brownfield", "turnaround", "fast-track"],
  },
  {
    id: "public-infrastructure",
    name: "Public Infrastructure",
    summary: "Public-sector delivery with milestone governance and stakeholder reporting cadence.",
    phaseFocus: ["Permitting", "Claims controls", "Public reporting"],
    tags: ["infrastructure", "public", "compliance"],
  },
];

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

function parseBatchImportRows(value: string): BatchImportRow[] {
  return value
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name = "", type = "", code = ""] = line
        .split(",")
        .map((segment) => segment.trim());

      return { name, type, code };
    })
    .filter((row) => row.name.length > 0);
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
  const token = useAuthStore((s) => s.token);
  const { data, isLoading, error } = useProjects(!!token);
  const {
    mutateAsync: updateProject,
    isPending: isSavingProject,
    error: updateProjectError,
  } = useUpdateProject();
  const [searchQuery, setSearchQuery] = useState("");
  const [importDraft, setImportDraft] = useState("");
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [isTemplatesOpen, setIsTemplatesOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>(
    PROJECT_TEMPLATES[0]?.id ?? "",
  );
  const [visibleColumns, setVisibleColumns] = useState<
    ProjectTableOptionalColumn[]
  >([...PROJECT_TABLE_OPTIONAL_COLUMNS]);
  const [savedPresets, setSavedPresets] = useState<ProjectFilterPreset[]>([]);
  const [projectRows, setProjectRows] = useState<ProjectListItem[]>([]);
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"table" | "kanban">("table");
  const [statusFilter, setStatusFilter] = useState<ProjectStatusFilter>("all");
  const [typeFilter, setTypeFilter] = useState<ProjectTypeFilter>("all");
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
    if (!normalizedQuery) {
      return projectRows.filter((project) => {
        const matchesStatus =
          statusFilter === "all" ? true : project.status === statusFilter;
        const matchesType =
          typeFilter === "all" ? true : project.project_type === typeFilter;

        return matchesStatus && matchesType;
      });
    }

    return projectRows.filter((project) => {
      const matchesStatus =
        statusFilter === "all" ? true : project.status === statusFilter;
      const matchesType =
        typeFilter === "all" ? true : project.project_type === typeFilter;
      const haystack = [project.name, project.description ?? "", project.code ?? ""]
        .join(" ")
        .toLowerCase();

      return matchesStatus && matchesType && haystack.includes(normalizedQuery);
    });
  }, [projectRows, searchQuery, statusFilter, typeFilter]);
  const inlineEditErrorMessage =
    editError ??
    (updateProjectError instanceof Error ? updateProjectError.message : null);
  const loadError =
    error instanceof Error ? error.message : error ? String(error) : null;
  const importPreview = useMemo(
    () => parseBatchImportRows(importDraft),
    [importDraft],
  );
  const selectedTemplate =
    PROJECT_TEMPLATES.find((template) => template.id === selectedTemplateId) ??
    PROJECT_TEMPLATES[0];

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

  function saveCurrentPreset() {
    const presetName = window.prompt("Preset name");
    if (!presetName) {
      return;
    }

    const trimmedName = presetName.trim();
    if (!trimmedName) {
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
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Projects
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage and monitor all your projects
          </p>
        </div>
        <div className="flex flex-1 flex-col gap-3 xl:items-end">
          <div className="w-full max-w-md">
            <Input
              type="search"
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              placeholder="Search projects..."
              aria-label="Search projects"
            />
          </div>
          <div className="flex w-full flex-wrap items-end gap-3 xl:justify-end">
            <label className="flex flex-col gap-1 text-sm text-foreground">
              <span>Status Filter</span>
              <select
                aria-label="Status filter"
                className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
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
              <span>Type Filter</span>
              <select
                aria-label="Type filter"
                className="h-10 rounded-md border border-input bg-background px-3 py-2 text-sm"
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
            >
              Reset Filters
            </Button>
          </div>
          {statusFilter !== "all" || typeFilter !== "all" ? (
            <div className="flex flex-wrap items-center gap-2 xl:justify-end">
              {statusFilter !== "all" ? (
                <span className="rounded-full border bg-muted px-3 py-1 text-xs text-foreground">
                  Status: {statusFilter}
                </span>
              ) : null}
              {typeFilter !== "all" ? (
                <span className="rounded-full border bg-muted px-3 py-1 text-xs text-foreground">
                  Type: {typeFilter}
                </span>
              ) : null}
            </div>
          ) : null}
          {savedPresets.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2">
              {savedPresets.map((preset) => (
                <Button
                  key={preset.id}
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => applyFilterPreset(preset)}
                >
                  {preset.name}
                </Button>
              ))}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-4">
          <span className="text-xs text-muted-foreground">
            {isLoading
              ? "Loading..."
              : searchQuery.trim().length > 0
                ? `${filteredProjects.length} of ${projectRows.length} projects`
                : `${projectRows.length} projects`}
          </span>
          <div className="flex items-center gap-2">
            <Button
              type="button"
              variant={viewMode === "table" ? "default" : "outline"}
              onClick={() => setViewMode("table")}
            >
              Table View
            </Button>
            <Button
              type="button"
              variant={viewMode === "kanban" ? "default" : "outline"}
              onClick={() => setViewMode("kanban")}
            >
              Kanban View
            </Button>
          </div>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline">
                <Settings2 className="mr-2 h-4 w-4" />
                Columns
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuLabel>Visible Columns</DropdownMenuLabel>
              <DropdownMenuSeparator />
              {PROJECT_TABLE_OPTIONAL_COLUMNS.map((column) => (
                <DropdownMenuCheckboxItem
                  key={column}
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
          >
            Export PDF
          </Button>
          <Button
            variant="outline"
            onClick={exportProjectsExcel}
            disabled={projectRows.length === 0 || isLoading}
          >
            Export Excel
          </Button>
          <Button
            variant="outline"
            onClick={exportProjectsJson}
            disabled={projectRows.length === 0 || isLoading}
          >
            Export JSON
          </Button>
          <Button variant="outline" onClick={() => setIsTemplatesOpen(true)}>
            Project Templates
          </Button>
          <Button variant="outline" onClick={() => setIsImportOpen(true)}>
            <Upload className="mr-2 h-4 w-4" />
            Batch Import
          </Button>
          <Button
            type="button"
            variant="outline"
            onClick={saveCurrentPreset}
          >
            Save Preset
          </Button>
          <Button asChild>
            <Link href="/projects/new">
              <Plus className="mr-2 h-4 w-4" />
              New Project
            </Link>
          </Button>
        </div>
        </div>
      </div>

      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          API request failed ({loadError}). Verify backend API is running at{" "}
          <code>http://localhost:8000/api/v1</code>.
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

      <LazyProjectBatchImportDialog
        open={isImportOpen}
        importDraft={importDraft}
        importPreview={importPreview}
        onImportDraftChange={setImportDraft}
        onOpenChange={setIsImportOpen}
      />

      <LazyProjectTemplatesDialog
        open={isTemplatesOpen}
        selectedTemplateId={selectedTemplateId}
        selectedTemplate={selectedTemplate}
        templates={PROJECT_TEMPLATES}
        onSelectTemplate={setSelectedTemplateId}
        onOpenChange={setIsTemplatesOpen}
      />

      <Dialog
        open={quickViewProject !== null}
        onOpenChange={(open) => {
          if (!open) {
            setQuickViewProject(null);
          }
        }}
      >
        <DialogContent className="sm:max-w-3xl sm:translate-x-[18%]">
          <DialogHeader>
            <DialogTitle>Project quick view</DialogTitle>
            <DialogDescription>
              Review the selected project context without leaving the projects list.
            </DialogDescription>
          </DialogHeader>

          {quickViewProject ? (
            <div className="grid gap-6 md:grid-cols-[1.2fr_0.8fr]">
              <section className="space-y-4">
                <div className="rounded-xl border bg-muted/20 p-5">
                  <h2 className="text-lg font-semibold tracking-tight">
                    {quickViewProject.name}
                  </h2>
                  <p className="mt-2 text-sm text-muted-foreground">
                    {quickViewProject.description ?? "No description available."}
                  </p>
                </div>
              </section>

              <aside className="rounded-xl border bg-background p-4">
                <div className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Status
                </div>
                <div className="mt-2 text-sm font-medium capitalize">
                  {quickViewProject.status ?? "Unknown"}
                </div>

                <div className="mt-5 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Type
                </div>
                <div className="mt-2 text-sm font-medium uppercase">
                  {quickViewProject.project_type ?? "N/A"}
                </div>

                <div className="mt-5 text-xs font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Code
                </div>
                <div className="mt-2 font-mono text-sm">
                  {quickViewProject.code ?? "—"}
                </div>
              </aside>
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="outline" onClick={() => setQuickViewProject(null)}>
              Close
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
