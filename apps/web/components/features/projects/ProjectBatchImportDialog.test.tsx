/**
 * Test Suite ID: TASK-013
 * Backlog Task: TASK-1477
 */
import { describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import { ProjectBatchImportDialog } from "./ProjectBatchImportDialog";

describe("ProjectBatchImportDialog", () => {
  it("renders the surfaced dialog treatment for the batch import flow", () => {
    renderWithProviders(
      <ProjectBatchImportDialog
        open
        importDraft="Hospital Central,EPC,HC-001"
        importPreview={[{ name: "Hospital Central", type: "EPC", code: "HC-001" }]}
        onImportDraftChange={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: /import projects in bulk/i });
    expect(dialog).toHaveClass("bg-background/95");
    expect(dialog).toHaveClass("shadow-2xl");
    expect(screen.getByText(/1 project row ready to import/i)).toBeInTheDocument();
    expect(screen.getAllByText(/hospital central/i).length).toBeGreaterThan(0);
  });

  it("propagates textarea changes", () => {
    const onImportDraftChange = vi.fn();

    renderWithProviders(
      <ProjectBatchImportDialog
        open
        importDraft=""
        importPreview={[]}
        onImportDraftChange={onImportDraftChange}
        onOpenChange={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/project rows/i), {
      target: { value: "Port Expansion,Maritime,PE-002" },
    });

    expect(onImportDraftChange).toHaveBeenCalledWith("Port Expansion,Maritime,PE-002");
  });
});
