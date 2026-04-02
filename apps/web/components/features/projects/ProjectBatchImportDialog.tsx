/**
 * Backlog Task: TASK-023
 * Route Coverage: Projects dialog chunk
 */
"use client";

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

export type BatchImportRow = {
  name: string;
  type: string;
  code: string;
};

interface ProjectBatchImportDialogProps {
  open: boolean;
  importDraft: string;
  importPreview: BatchImportRow[];
  onImportDraftChange: (value: string) => void;
  onOpenChange: (open: boolean) => void;
}

export function ProjectBatchImportDialog({
  open,
  importDraft,
  importPreview,
  onImportDraftChange,
  onOpenChange,
}: ProjectBatchImportDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import projects in bulk</DialogTitle>
          <DialogDescription>
            Paste one CSV-style row per project using the format{" "}
            <span className="font-mono text-xs">name,type,code</span>.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="project-import-rows">Project rows</Label>
            <Textarea
              id="project-import-rows"
              value={importDraft}
              onChange={(event) => onImportDraftChange(event.target.value)}
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
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button disabled={importPreview.length === 0}>Queue Import</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
