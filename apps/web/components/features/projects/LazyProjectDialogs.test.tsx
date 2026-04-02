/**
 * Test Suite ID: TASK-013
 * Backlog Task: TASK-023
 */
import fs from "fs";
import path from "path";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@/src/tests/test-utils";

vi.mock("next/dynamic", () => ({
  default: (
    _loader: unknown,
    options?: {
      loading?: () => ReactElement;
    },
  ) => {
    return function DynamicProxy() {
      return (
        <div data-testid="dynamic-proxy">
          {options?.loading ? options.loading() : null}
        </div>
      );
    };
  },
}));

import {
  LazyProjectBatchImportDialog,
  LazyProjectTemplatesDialog,
} from "./LazyProjectDialogs";

describe("LazyProjectDialogs", () => {
  it("[TASK-023-PERF-01] exposes loading fallbacks while project dialog chunks are resolving", () => {
    render(
      <>
        <LazyProjectBatchImportDialog
          open
          importDraft=""
          importPreview={[]}
          onImportDraftChange={() => undefined}
          onOpenChange={() => undefined}
        />
        <LazyProjectTemplatesDialog
          open
          selectedTemplate={null}
          selectedTemplateId=""
          templates={[]}
          onSelectTemplate={() => undefined}
          onOpenChange={() => undefined}
        />
      </>,
    );

    expect(screen.getAllByTestId("dynamic-proxy")).toHaveLength(2);
    expect(screen.getByTestId("projects-batch-import-loading")).toBeInTheDocument();
    expect(screen.getByTestId("projects-templates-loading")).toBeInTheDocument();
  });

  it("[TASK-023-PERF-02] keeps the projects page pointed at lazy dialog wrappers instead of inline dialog content", () => {
    const pageSource = fs.readFileSync(
      path.resolve(process.cwd(), "app", "(app)", "projects", "page.tsx"),
      "utf8",
    );

    expect(pageSource).toContain("LazyProjectBatchImportDialog");
    expect(pageSource).toContain("LazyProjectTemplatesDialog");
    expect(pageSource).toContain('DialogContent');
    expect(pageSource).not.toContain('from "@/components/features/projects/ProjectBatchImportDialog"');
    expect(pageSource).not.toContain('from "@/components/features/projects/ProjectTemplatesDialog"');
    expect(pageSource).not.toContain("Import projects in bulk");
    expect(pageSource).not.toContain("Start from a project template");
  });
});
