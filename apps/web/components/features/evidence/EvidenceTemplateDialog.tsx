import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";
import type { EvidenceTemplate } from "./evidence-page-utils";

interface EvidenceTemplateDialogProps {
  open: boolean;
  templates: EvidenceTemplate[];
  selectedTemplate: EvidenceTemplate | undefined;
  onOpenChange: (open: boolean) => void;
  onSelectTemplate: (templateId: string) => void;
}

export function EvidenceTemplateDialog({
  open,
  templates,
  selectedTemplate,
  onOpenChange,
  onSelectTemplate,
}: EvidenceTemplateDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-border/80 bg-background/95 p-6 shadow-2xl backdrop-blur-md sm:max-w-3xl sm:rounded-2xl">
        <DialogHeader className="rounded-2xl border border-border/70 bg-muted/35 px-4 py-4">
          <DialogTitle>Start from an evidence template</DialogTitle>
          <DialogDescription>
            Use a guided review lens to focus the current evidence session.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
          <div className="space-y-2">
            {templates.map((template) => (
              <Button
                key={template.id}
                type="button"
                variant={selectedTemplate?.id === template.id ? "default" : "outline"}
                className={cn(
                  "w-full justify-start rounded-xl shadow-sm",
                  selectedTemplate?.id === template.id ? "" : "bg-background/95",
                )}
                onClick={() => onSelectTemplate(template.id)}
              >
                {template.name}
              </Button>
            ))}
          </div>

          {selectedTemplate ? (
            <div className="rounded-2xl border border-border/80 bg-muted/25 p-5 shadow-sm">
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
                    Review focus
                  </div>
                  <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                    {selectedTemplate.reviewFocus.map((item) => (
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
                        className="rounded-full border border-border/80 bg-background px-3 py-1 text-xs text-muted-foreground shadow-sm"
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

        <DialogFooter className="rounded-2xl border border-border/70 bg-muted/20 px-4 py-3">
          <Button variant="outline" className="rounded-xl bg-background/95 shadow-sm" onClick={() => onOpenChange(false)}>
            Close
          </Button>
          <Button className="rounded-xl shadow-sm" onClick={() => onOpenChange(false)}>
            Use Template
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
