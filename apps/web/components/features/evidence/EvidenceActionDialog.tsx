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
import type { PendingEvidenceAction } from "./evidence-page-utils";

interface EvidenceActionDialogProps {
  pendingAction: PendingEvidenceAction | null;
  pendingActionDescription: string;
  requiresValidationNote: boolean;
  validationNote: string;
  onValidationNoteChange: (value: string) => void;
  onCancel: () => void;
  onConfirm: () => void;
}

export function EvidenceActionDialog({
  pendingAction,
  pendingActionDescription,
  requiresValidationNote,
  validationNote,
  onValidationNoteChange,
  onCancel,
  onConfirm,
}: EvidenceActionDialogProps) {
  return (
    <Dialog
      open={pendingAction !== null}
      onOpenChange={(open) => {
        if (!open) {
          onCancel();
        }
      }}
    >
      <DialogContent className="border-border/80 bg-background/95 p-6 shadow-2xl backdrop-blur-md sm:rounded-2xl">
        <DialogHeader className="rounded-2xl border border-border/70 bg-muted/35 px-4 py-4">
          <DialogTitle>Confirm evidence action</DialogTitle>
          <DialogDescription>{pendingActionDescription}</DialogDescription>
        </DialogHeader>
        {requiresValidationNote ? (
          <div className="space-y-2">
            <p className="text-sm text-amber-700">
              Confidence below 90% requires a validation note before approval.
            </p>
            <Label htmlFor="evidence-validation-note">Validation note</Label>
            <Textarea
              id="evidence-validation-note"
              value={validationNote}
              onChange={(event) => onValidationNoteChange(event.target.value)}
              placeholder="Document why this low-confidence extraction is still acceptable."
              rows={3}
            />
          </div>
        ) : null}
        <DialogFooter className="rounded-2xl border border-border/70 bg-muted/20 px-4 py-3">
          <Button
            type="button"
            variant="outline"
            className="rounded-xl bg-background/95 shadow-sm"
            onClick={onCancel}
          >
            Cancel Action
          </Button>
          <Button
            type="button"
            className="rounded-xl shadow-sm"
            onClick={onConfirm}
            disabled={requiresValidationNote && !validationNote.trim()}
          >
            Confirm Action
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
