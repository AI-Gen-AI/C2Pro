/**
 * Test Suite ID: TASK-013
 * Backlog Task: TASK-1477
 */
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, renderWithProviders, screen } from "@/src/tests/test-utils";
import { ProjectTemplatesDialog } from "./ProjectTemplatesDialog";

vi.mock("next/link", () => ({
  default: ({
    children,
    href,
  }: {
    children: ReactNode;
    href: string;
  }) => <a href={href}>{children}</a>,
}));

describe("ProjectTemplatesDialog", () => {
  it("renders the surfaced dialog treatment for project templates", () => {
    renderWithProviders(
      <ProjectTemplatesDialog
        open
        selectedTemplateId="epc-megaproject"
        selectedTemplate={{
          id: "epc-megaproject",
          name: "EPC Megaproject",
          summary: "Large-scale EPC delivery",
          phaseFocus: ["Contract baseline", "Risk alignment"],
          tags: ["greenfield", "epc"],
        }}
        templates={[
          {
            id: "epc-megaproject",
            name: "EPC Megaproject",
            summary: "Large-scale EPC delivery",
            phaseFocus: ["Contract baseline", "Risk alignment"],
            tags: ["greenfield", "epc"],
          },
        ]}
        onSelectTemplate={vi.fn()}
        onOpenChange={vi.fn()}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: /start from a project template/i });
    expect(dialog).toHaveClass("bg-background/95");
    expect(dialog).toHaveClass("shadow-2xl");
    expect(screen.getByText(/large-scale epc delivery/i)).toBeInTheDocument();
    expect(screen.getByText(/contract baseline/i)).toBeInTheDocument();
    expect(screen.getByText(/greenfield/i)).toBeInTheDocument();
  });

  it("switches templates when a new option is chosen", () => {
    const onSelectTemplate = vi.fn();

    renderWithProviders(
      <ProjectTemplatesDialog
        open
        selectedTemplateId="epc-megaproject"
        selectedTemplate={{
          id: "epc-megaproject",
          name: "EPC Megaproject",
          summary: "Large-scale EPC delivery",
          phaseFocus: ["Contract baseline"],
          tags: ["epc"],
        }}
        templates={[
          {
            id: "epc-megaproject",
            name: "EPC Megaproject",
            summary: "Large-scale EPC delivery",
            phaseFocus: ["Contract baseline"],
            tags: ["epc"],
          },
          {
            id: "industrial-retrofit",
            name: "Industrial Retrofit",
            summary: "Industrial retrofit recovery",
            phaseFocus: ["Shutdown planning"],
            tags: ["brownfield"],
          },
        ]}
        onSelectTemplate={onSelectTemplate}
        onOpenChange={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /industrial retrofit/i }));

    expect(onSelectTemplate).toHaveBeenCalledWith("industrial-retrofit");
  });
});
