"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileText,
  Link as LinkIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";

// Types for extracted entities
export interface ExtractedEntity {
  id: string;
  type: string;
  text: string;
  approvalResourceType?: string | null;
  originalText?: string;
  confidence: number | null;
  page: number | null;
  validated?: boolean;
  validationStatus?: "pending" | "approved" | "rejected";
  rejectionReason?: string;
  linkedWbs?: string[];
  linkedAlerts?: string[];
  technicalSourceSection?: string | null;
  technicalSourceUnverified?: boolean;
}

interface EntityValidationCardProps {
  entity: ExtractedEntity;
  /** Must resolve only once the SERVER has persisted the decision; reject to keep the dialog open with the error. */
  onApprove: (entityId: string, note?: string) => void | Promise<void>;
  onReject: (entityId: string, reason: string) => void | Promise<void>;
  onEntityClick?: (entity: ExtractedEntity) => void;
  isActive?: boolean;
}

// Human-in-the-loop Gate 6 compliant component
export function EntityValidationCard({
  entity,
  onApprove,
  onReject,
  onEntityClick,
  isActive = false,
}: EntityValidationCardProps) {
  const [approveDialogOpen, setApproveDialogOpen] = useState(false);
  const [rejectDialogOpen, setRejectDialogOpen] = useState(false);
  const [rejectionReason, setRejectionReason] = useState("");
  const [approvalNote, setApprovalNote] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  // Only entity types the backend can persist a decision for are actionable. Everything else is inspection only:
  // no Approve/Reject, so no confirmation can appear to succeed when nothing is saved.
  const decisionSupported = Boolean(entity.approvalResourceType);
  const noteRequired = entity.confidence === null || entity.confidence < 90;

  const getConfidenceColor = (confidence: number | null) => {
    if (confidence === null) return "border-l-slate-400 bg-slate-50/50";
    if (confidence >= 80) return "border-l-green-500 bg-green-50/50";
    if (confidence >= 60) return "border-l-amber-500 bg-amber-50/50";
    return "border-l-red-500 bg-red-50/50";
  };

  const getConfidenceBadge = (confidence: number | null) => {
    if (confidence === null) return { label: "Not measured", variant: "outline" as const };
    if (confidence >= 80) return { label: "High", variant: "default" as const };
    if (confidence >= 60)
      return { label: "Medium", variant: "secondary" as const };
    return { label: "Low", variant: "destructive" as const };
  };

  const getStatusBadge = () => {
    if (!decisionSupported) {
      return (
        <Badge variant="outline" data-testid="entity-inspection-only">
          Inspection only
        </Badge>
      );
    }
    if (entity.validationStatus === "approved") {
      return (
        <Badge variant="default" className="bg-green-600">
          <CheckCircle className="mr-1 h-3 w-3" />
          Approved
        </Badge>
      );
    }
    if (entity.validationStatus === "rejected") {
      return (
        <Badge variant="destructive">
          <XCircle className="mr-1 h-3 w-3" />
          Rejected
        </Badge>
      );
    }
    return (
      <Badge variant="outline">
        <AlertTriangle className="mr-1 h-3 w-3" />
        Pending Review
      </Badge>
    );
  };

  const confidenceBadge = getConfidenceBadge(entity.confidence);

  const decisionFailure = (error: unknown) =>
    error instanceof Error && error.message ? error.message : "The decision could not be saved. Nothing was changed.";

  const handleApproveConfirm = async () => {
    setSubmitting(true);
    setDecisionError(null);
    try {
      await onApprove(entity.id, approvalNote.trim() || undefined);
      setApproveDialogOpen(false);
      setApprovalNote("");
    } catch (error) {
      setDecisionError(decisionFailure(error));
    } finally {
      setSubmitting(false);
    }
  };

  const handleRejectConfirm = async () => {
    setSubmitting(true);
    setDecisionError(null);
    try {
      await onReject(entity.id, rejectionReason);
      setRejectDialogOpen(false);
      setRejectionReason("");
    } catch (error) {
      setDecisionError(decisionFailure(error));
    } finally {
      setSubmitting(false);
    }
  };

  const isPending =
    entity.validationStatus === "pending" || !entity.validationStatus;
  const showActions = isPending && decisionSupported;

  return (
    <>
      <Card
        className={cn(
          "border-l-4 transition-all cursor-pointer hover:shadow-md",
          getConfidenceColor(entity.confidence),
          isActive && "ring-2 ring-primary shadow-lg",
          entity.validationStatus === "approved" && "opacity-75",
          entity.validationStatus === "rejected" && "opacity-50",
        )}
        onClick={() => onEntityClick?.(entity)}
        data-testid="evidence-entity-card"
        data-entity-id={entity.id}
        data-active={isActive ? "true" : "false"}
      >
        <CardContent className="p-4 space-y-3">
          {/* Header with type and status */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="break-words text-sm font-medium">{entity.type}</span>
            </div>
            {getStatusBadge()}
          </div>

          {/* Extracted text */}
          <div className="space-y-1">
            <p className="break-words text-sm line-clamp-3">{entity.text}</p>
            {entity.originalText && entity.originalText !== entity.text && (
              <p className="text-xs text-muted-foreground italic">
                Original: {entity.originalText.substring(0, 100)}...
              </p>
            )}
          </div>

          {/* Metadata */}
          <div className="flex items-center gap-2 flex-wrap">
            {entity.technicalSourceSection && (
              <Badge variant="outline">Source section {entity.technicalSourceSection}</Badge>
            )}
            {entity.technicalSourceUnverified && (
              <Badge variant="outline">Technical requirement not verified</Badge>
            )}
            <Badge variant={confidenceBadge.variant}>
              {entity.confidence === null ? confidenceBadge.label : `${entity.confidence}% - ${confidenceBadge.label}`}
            </Badge>
            <Badge variant="outline" className="text-xs">
              {entity.page !== null ? `Page ${entity.page}` : "Exact location unavailable"}
            </Badge>
            {entity.linkedWbs && entity.linkedWbs.length > 0 && (
              <Badge variant="outline" className="text-xs">
                <LinkIcon className="mr-1 h-3 w-3" />
                {entity.linkedWbs.length} WBS
              </Badge>
            )}
            {entity.linkedAlerts && entity.linkedAlerts.length > 0 && (
              <Badge variant="outline" className="text-xs text-amber-600">
                <AlertTriangle className="mr-1 h-3 w-3" />
                {entity.linkedAlerts.length} Alerts
              </Badge>
            )}
          </div>

          {/* Rejection reason if rejected */}
          {entity.validationStatus === "rejected" && entity.rejectionReason && (
            <div className="p-2 bg-red-50 rounded text-xs text-red-700">
              <strong>Rejection reason:</strong> {entity.rejectionReason}
            </div>
          )}

          {!decisionSupported && (
            <p className="border-t pt-2 text-xs text-muted-foreground" data-testid="entity-inspection-note">
              Source inspection only. This item type has no individual approval: nothing is saved from here. The
              document as a whole is approved or rejected in Review.
            </p>
          )}

          {/* Action buttons - only for pending entities whose decision the backend can persist */}
          {showActions && (
            <div className="flex flex-wrap items-center gap-2 pt-2 border-t">
              <Button
                size="sm"
                variant="outline"
                className="min-w-[7rem] flex-1 text-green-600 hover:bg-green-50 hover:text-green-700"
                onClick={(e) => {
                  e.stopPropagation();
                  setDecisionError(null);
                  setApproveDialogOpen(true);
                }}
              >
                <CheckCircle className="mr-1 h-4 w-4" />
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="min-w-[7rem] flex-1 text-red-600 hover:bg-red-50 hover:text-red-700"
                onClick={(e) => {
                  e.stopPropagation();
                  setDecisionError(null);
                  setRejectDialogOpen(true);
                }}
              >
                <XCircle className="mr-1 h-4 w-4" />
                Reject
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Gate 6 Human-in-the-loop: Approve Confirmation Dialog */}
      <AlertDialog
        open={approveDialogOpen}
        onOpenChange={(open) => {
          if (!submitting) setApproveDialogOpen(open);
        }}
      >
        <AlertDialogContent className="max-h-[90dvh] w-[calc(100vw-2rem)] max-w-lg overflow-y-auto">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              Confirm Approval
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>Are you sure you want to approve this extraction?</p>
              <div className="mt-3 p-3 bg-muted rounded-lg">
                <p className="font-medium text-sm text-foreground">
                  {entity.type}
                </p>
                <p className="text-sm mt-1">
                  {entity.text.substring(0, 150)}...
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  Confidence: {entity.confidence === null ? "Not measured" : `${entity.confidence}%`} | Page {entity.page ?? "unavailable"}
                </p>
              </div>
              <p className="text-sm mt-3">
                This asks the server to record your decision. It is shown as approved only after the server
                confirms it.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          {noteRequired ? (
            <div className="px-6 pb-2">
              <Label htmlFor={`approval-note-${entity.id}`} className="text-sm font-medium">
                Validation note <span className="text-red-500">*</span>
              </Label>
              <p className="mt-1 text-xs text-amber-700">
                Confidence {entity.confidence === null ? "is not measured" : "is below 90%"}: explain why this
                extraction is still acceptable.
              </p>
              <Textarea
                id={`approval-note-${entity.id}`}
                data-testid="entity-approval-note"
                value={approvalNote}
                onChange={(e) => setApprovalNote(e.target.value)}
                className="mt-2"
                rows={3}
              />
            </div>
          ) : null}
          {decisionError ? (
            <p role="alert" className="px-6 text-sm text-destructive" data-testid="entity-decision-error">
              {decisionError}
            </p>
          ) : null}
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel disabled={submitting}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={submitting || (noteRequired && !approvalNote.trim())}
              data-testid="entity-approve-confirm"
              onClick={(event) => {
                event.preventDefault();
                void handleApproveConfirm();
              }}
              className="bg-green-600 hover:bg-green-700"
            >
              <CheckCircle className="mr-2 h-4 w-4" />
              {submitting ? "Saving…" : "Confirm Approval"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Gate 6 Human-in-the-loop: Reject Confirmation Dialog with Reason */}
      <AlertDialog
        open={rejectDialogOpen}
        onOpenChange={(open) => {
          if (!submitting) setRejectDialogOpen(open);
        }}
      >
        <AlertDialogContent className="max-h-[90dvh] w-[calc(100vw-2rem)] max-w-lg overflow-y-auto">
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-600" />
              Confirm Rejection
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>Are you sure you want to reject this extraction?</p>
              <div className="mt-3 p-3 bg-muted rounded-lg">
                <p className="font-medium text-sm text-foreground">
                  {entity.type}
                </p>
                <p className="text-sm mt-1">
                  {entity.text.substring(0, 150)}...
                </p>
                <p className="text-xs text-muted-foreground mt-2">
                  Confidence: {entity.confidence === null ? "Not measured" : `${entity.confidence}%`} | Page {entity.page ?? "unavailable"}
                </p>
              </div>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <div className="px-6 pb-2">
            <Label htmlFor="rejection-reason" className="text-sm font-medium">
              Rejection Reason <span className="text-red-500">*</span>
            </Label>
            <Textarea
              id="rejection-reason"
              placeholder="Please provide a reason for rejecting this extraction (e.g., incorrect extraction, wrong category, incomplete data)..."
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              className="mt-2"
              rows={3}
            />
            <p className="text-xs text-muted-foreground mt-1">
              This feedback will be logged for audit purposes and used to
              improve future extractions.
            </p>
          </div>
          {decisionError ? (
            <p role="alert" className="px-6 text-sm text-destructive" data-testid="entity-decision-error">
              {decisionError}
            </p>
          ) : null}
          <AlertDialogFooter className="gap-2">
            <AlertDialogCancel disabled={submitting} onClick={() => setRejectionReason("")}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(event) => {
                event.preventDefault();
                void handleRejectConfirm();
              }}
              disabled={submitting || !rejectionReason.trim()}
              data-testid="entity-reject-confirm"
              className="bg-red-600 hover:bg-red-700 disabled:opacity-50"
            >
              <XCircle className="mr-2 h-4 w-4" />
              {submitting ? "Saving…" : "Confirm Rejection"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
