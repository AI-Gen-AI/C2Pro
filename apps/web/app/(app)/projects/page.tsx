"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useProjects } from "@/hooks/useProjects";
import { ProjectListTable } from "@/components/features/projects/ProjectListTable";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Loader2, Plus, Upload } from "lucide-react";
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
    .replace(/[^a-z0-9_\-\.]+/gi, "_")
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

export default function ProjectsPage() {
  const token = useAuthStore((s) => s.token);
  const { data, isLoading, error } = useProjects(!!token);
  const [importDraft, setImportDraft] = useState("");
  const [isImportOpen, setIsImportOpen] = useState(false);
  const [isTemplatesOpen, setIsTemplatesOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>(
    PROJECT_TEMPLATES[0]?.id ?? "",
  );

  const projects = data ?? [];
  const loadError =
    error instanceof Error ? error.message : error ? String(error) : null;
  const importPreview = useMemo(
    () => parseBatchImportRows(importDraft),
    [importDraft],
  );
  const selectedTemplate =
    PROJECT_TEMPLATES.find((template) => template.id === selectedTemplateId) ??
    PROJECT_TEMPLATES[0];

  function exportProjectsPdf() {
    if (projects.length === 0) {
      return;
    }

    const popup = window.open("", "_blank", "noopener,noreferrer,width=960,height=720");
    if (!popup) {
      return;
    }

    const rows = projects
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
    <p>${projects.length} projects included in this report.</p>
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
    if (projects.length === 0) {
      return;
    }

    downloadBlob(
      `${sanitizeFilename("projects_export")}.xls`,
      createProjectsWorkbook(projects),
      "application/vnd.ms-excel",
    );
  }

  function exportProjectsJson() {
    if (projects.length === 0) {
      return;
    }

    downloadBlob(
      `${sanitizeFilename("projects_export")}.json`,
      JSON.stringify(
        {
          exportedAt: new Date().toISOString(),
          totalProjects: projects.length,
          projects,
        },
        null,
        2,
      ),
      "application/json",
    );
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">
            Projects
          </h1>
          <p className="text-sm text-muted-foreground">
            Manage and monitor all your projects
          </p>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-xs text-muted-foreground">
            {isLoading ? "Loading..." : `${projects.length} projects`}
          </span>
          <Button
            variant="outline"
            onClick={exportProjectsPdf}
            disabled={projects.length === 0 || isLoading}
          >
            Export PDF
          </Button>
          <Button
            variant="outline"
            onClick={exportProjectsExcel}
            disabled={projects.length === 0 || isLoading}
          >
            Export Excel
          </Button>
          <Button
            variant="outline"
            onClick={exportProjectsJson}
            disabled={projects.length === 0 || isLoading}
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
          <Button asChild>
            <Link href="/projects/new">
              <Plus className="mr-2 h-4 w-4" />
              New Project
            </Link>
          </Button>
        </div>
      </div>

      {loadError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          API request failed ({loadError}). Verify backend API is running at{" "}
          <code>http://localhost:8000/api/v1</code>.
        </div>
      ) : null}

      {isLoading ? (
        <div className="flex items-center justify-center min-h-[200px]">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <ProjectListTable projects={projects} />
      )}

      <Dialog open={isImportOpen} onOpenChange={setIsImportOpen}>
        <DialogContent className="sm:max-w-2xl">
          <DialogHeader>
            <DialogTitle>Import projects in bulk</DialogTitle>
            <DialogDescription>
              Paste one CSV-style row per project using the format
              {" "}
              <span className="font-mono text-xs">
                name,type,code
              </span>
              .
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="project-import-rows">Project rows</Label>
              <Textarea
                id="project-import-rows"
                value={importDraft}
                onChange={(event) => setImportDraft(event.target.value)}
                placeholder="Hospital Central,EPC,HC-001&#10;Port Expansion,Maritime,PE-002"
                className="min-h-[140px]"
              />
            </div>

            <div className="rounded-md border bg-muted/30 p-4">
              <div className="text-sm font-medium text-foreground">
                {importPreview.length} project row
                {importPreview.length === 1 ? "" : "s"} ready to import
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Review the parsed rows before connecting this flow to backend
                import execution.
              </p>

              {importPreview.length > 0 ? (
                <ul className="mt-4 space-y-2">
                  {importPreview.map((row, index) => (
                    <li
                      key={`${row.name}-${row.code}-${index}`}
                      className="rounded-md border bg-background px-3 py-2 text-sm"
                    >
                      <div className="font-medium text-foreground">{row.name}</div>
                      <div className="text-xs text-muted-foreground">
                        {row.type || "Type pending"} · {row.code || "Code pending"}
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="mt-4 text-sm text-muted-foreground">
                  Add at least one valid row to generate an import preview.
                </p>
              )}
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsImportOpen(false)}>
              Close
            </Button>
            <Button disabled={importPreview.length === 0}>
              Queue Import
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isTemplatesOpen} onOpenChange={setIsTemplatesOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Start from a project template</DialogTitle>
            <DialogDescription>
              Use a proven project setup pattern before creating the final project record.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
            <div className="space-y-2">
              {PROJECT_TEMPLATES.map((template) => (
                <Button
                  key={template.id}
                  type="button"
                  variant={selectedTemplate?.id === template.id ? "default" : "outline"}
                  className="w-full justify-start"
                  onClick={() => setSelectedTemplateId(template.id)}
                >
                  {template.name}
                </Button>
              ))}
            </div>

            {selectedTemplate ? (
              <div className="rounded-md border bg-muted/20 p-5">
                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Template Summary
                  </div>
                  <h3 className="text-lg font-semibold text-foreground">
                    {selectedTemplate.summary}
                  </h3>
                </div>

                <div className="mt-5 grid gap-5 md:grid-cols-2">
                  <div>
                    <div className="text-sm font-medium text-foreground">
                      Phase focus
                    </div>
                    <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                      {selectedTemplate.phaseFocus.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-foreground">Tags</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedTemplate.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsTemplatesOpen(false)}>
              Close
            </Button>
            <Button asChild>
              <Link href="/projects/new">Use Template</Link>
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
