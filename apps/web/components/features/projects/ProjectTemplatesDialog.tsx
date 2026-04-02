/**
 * Backlog Task: TASK-023
 * Route Coverage: Projects dialog chunk
 */
"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export type ProjectTemplate = {
  id: string;
  name: string;
  summary: string;
  phaseFocus: string[];
  tags: string[];
};

interface ProjectTemplatesDialogProps {
  open: boolean;
  selectedTemplateId: string;
  selectedTemplate: ProjectTemplate | null;
  templates: ProjectTemplate[];
  onSelectTemplate: (templateId: string) => void;
  onOpenChange: (open: boolean) => void;
}

export function ProjectTemplatesDialog({
  open,
  selectedTemplateId,
  selectedTemplate,
  templates,
  onSelectTemplate,
  onOpenChange,
}: ProjectTemplatesDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Start from a project template</DialogTitle>
          <DialogDescription>
            Use a proven project setup pattern before creating the final project record.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
          <div className="space-y-2">
            {templates.map((template) => (
              <Button
                key={template.id}
                type="button"
                variant={selectedTemplateId === template.id ? "default" : "outline"}
                className="w-full justify-start"
                onClick={() => onSelectTemplate(template.id)}
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
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button asChild>
            <Link href="/projects/new">Use Template</Link>
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
