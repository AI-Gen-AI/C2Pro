"use client";

import { useState } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  FileText,
  Link as LinkIcon,
} from 'lucide-react';
import { cn } from '@/lib/utils';

// Types for extracted entities
export interface ExtractedEntity {
  id: string;
  type: string;
  text: string;
  originalText?: string;
  confidence: number;
  page: number;
  validated?: boolean;
  validationStatus?: 'pending' | 'approved' | 'rejected';
  rejectionReason?: string;
  linkedWbs?: string[];
  linkedAlerts?: string[];
}

interface EntityValidationCardProps {
  entity: ExtractedEntity;
  onApprove: (entityId: string) => void;
  onReject: (entityId: string, reason: string) => void;
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
  const [rejectionReason, setRejectionReason] = useState('');

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 80) return 'border-l-green-500 bg-green-50/50';
    if (confidence >= 60) return 'border-l-amber-500 bg-amber-50/50';
    return 'border-l-red-500 bg-red-50/50';
  };

  const getConfidenceBadge = (confidence: number) => {
    if (confidence >= 80) return { label: 'High', variant: 'default' as const };
    if (confidence >= 60) return { label: 'Medium', variant: 'secondary' as const };
    return { label: 'Low', variant: 'destructive' as const };
  };

  const getStatusBadge = () => {
    if (entity.validationStatus === 'approved') {
      return (
        <Badge variant="default" className="bg-green-600">
          <CheckCircle className="mr-1 h-3 w-3" />
          Approved
        </Badge>
      );
    }
    if (entity.validationStatus === 'rejected') {
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

  const handleApproveConfirm = () => {
    onApprove(entity.id);
    setApproveDialogOpen(false);
  };

  const handleRejectConfirm = () => {
    onReject(entity.id, rejectionReason);
    setRejectDialogOpen(false);
    setRejectionReason('');
  };

  const isPending = entity.validationStatus === 'pending' || !entity.validationStatus;

  return (
    <>
      <Card
        className={cn(
          'border-l-4 transition-all cursor-pointer hover:shadow-md',
          getConfidenceColor(entity.confidence),
          isActive && 'ring-2 ring-primary shadow-lg',
          entity.validationStatus === 'approved' && 'opacity-75',
          entity.validationStatus === 'rejected' && 'opacity-50'
        )}
        onClick={() => onEntityClick?.(entity)}
      >
        <CardContent className="p-4 space-y-3">
          {/* Header with type and status */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="font-medium text-sm">{entity.type}</span>
            </div>
            {getStatusBadge()}
          </div>

          {/* Extracted text */}
          <div className="space-y-1">
            <p className="text-sm line-clamp-3">{entity.text}</p>
            {entity.originalText && entity.originalText !== entity.text && (
              <p className="text-xs text-muted-foreground italic">
                Original: {entity.originalText.substring(0, 100)}...
              </p>
            )}
          </div>

          {/* Metadata */}
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant={confidenceBadge.variant}>
              {entity.confidence}% - {confidenceBadge.label}
            </Badge>
            <Badge variant="outline" className="text-xs">
              Page {entity.page}
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
          {entity.validationStatus === 'rejected' && entity.rejectionReason && (
            <div className="p-2 bg-red-50 rounded text-xs text-red-700">
              <strong>Rejection reason:</strong> {entity.rejectionReason}
            </div>
          )}

          {/* Action buttons - Only show for pending entities */}
          {isPending && (
            <div className="flex items-center gap-2 pt-2 border-t">
              <Button
                size="sm"
                variant="outline"
                className="flex-1 text-green-600 hover:bg-green-50 hover:text-green-700"
                onClick={(e) => {
                  e.stopPropagation();
                  setApproveDialogOpen(true);
                }}
              >
                <CheckCircle className="mr-1 h-4 w-4" />
                Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                className="flex-1 text-red-600 hover:bg-red-50 hover:text-red-700"
                onClick={(e) => {
                  e.stopPropagation();
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
      <AlertDialog open={approveDialogOpen} onOpenChange={setApproveDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <CheckCircle className="h-5 w-5 text-green-600" />
              Confirm Approval
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>
                Are you sure you want to approve this extraction?
              </p>
              <div className="mt-3 p-3 bg-muted rounded-lg">
                <p className="font-medium text-sm text-foreground">{entity.type}</p>
                <p className="text-sm mt-1">{entity.text.substring(0, 150)}...</p>
                <p className="text-xs text-muted-foreground mt-2">
                  Confidence: {entity.confidence}% | Page {entity.page}
                </p>
              </div>
              <p className="text-sm mt-3">
                This will mark the extraction as <strong>validated</strong> and include it in the analysis results.
              </p>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={handleApproveConfirm}
              className="bg-green-600 hover:bg-green-700"
            >
              <CheckCircle className="mr-2 h-4 w-4" />
              Confirm Approval
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Gate 6 Human-in-the-loop: Reject Confirmation Dialog with Reason */}
      <AlertDialog open={rejectDialogOpen} onOpenChange={setRejectDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <XCircle className="h-5 w-5 text-red-600" />
              Confirm Rejection
            </AlertDialogTitle>
            <AlertDialogDescription className="space-y-2">
              <p>
                Are you sure you want to reject this extraction?
              </p>
              <div className="mt-3 p-3 bg-muted rounded-lg">
                <p className="font-medium text-sm text-foreground">{entity.type}</p>
                <p className="text-sm mt-1">{entity.text.substring(0, 150)}...</p>
                <p className="text-xs text-muted-foreground mt-2">
                  Confidence: {entity.confidence}% | Page {entity.page}
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
              This feedback will be logged for audit purposes and used to improve future extractions.
            </p>
          </div>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={() => setRejectionReason('')}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={handleRejectConfirm}
              disabled={!rejectionReason.trim()}
              className="bg-red-600 hover:bg-red-700 disabled:opacity-50"
            >
              <XCircle className="mr-2 h-4 w-4" />
              Confirm Rejection
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
