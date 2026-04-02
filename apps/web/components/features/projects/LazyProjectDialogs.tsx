/**
 * Backlog Task: TASK-023
 * Route Coverage: Projects dialog chunk lazy wrappers
 */
"use client";

import dynamic from "next/dynamic";
import type { BatchImportRow } from "./ProjectBatchImportDialog";
import type { ProjectTemplate } from "./ProjectTemplatesDialog";

interface LazyProjectBatchImportDialogProps {
  open: boolean;
  importDraft: string;
  importPreview: BatchImportRow[];
  onImportDraftChange: (value: string) => void;
  onOpenChange: (open: boolean) => void;
}

interface LazyProjectTemplatesDialogProps {
  open: boolean;
  selectedTemplateId: string;
  selectedTemplate: ProjectTemplate | null;
  templates: ProjectTemplate[];
  onSelectTemplate: (templateId: string) => void;
  onOpenChange: (open: boolean) => void;
}

const LazyProjectBatchImportDialog = dynamic<LazyProjectBatchImportDialogProps>(
  () =>
    import("./ProjectBatchImportDialog").then(
      (module) => module.ProjectBatchImportDialog,
    ),
  {
    loading: () => (
      <div data-testid="projects-batch-import-loading" className="hidden" />
    ),
  },
);

const LazyProjectTemplatesDialog = dynamic<LazyProjectTemplatesDialogProps>(
  () =>
    import("./ProjectTemplatesDialog").then(
      (module) => module.ProjectTemplatesDialog,
    ),
  {
    loading: () => (
      <div data-testid="projects-templates-loading" className="hidden" />
    ),
  },
);

export { LazyProjectBatchImportDialog, LazyProjectTemplatesDialog };
