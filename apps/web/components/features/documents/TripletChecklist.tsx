"use client";

import Link from "next/link";
import { CheckCircle2, Clock, FileText, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DocumentType } from "@/lib/api/generated/models";
import type { DocumentInfo } from "@/types/document";

export type TripletSlotType = Extract<DocumentType, "contract" | "budget" | "schedule">;
export type TripletSlotState = "missing" | "processing" | "awaiting_approval" | "ready";

export type TripletSlot = {
  type: TripletSlotType;
  label: string;
  state: TripletSlotState;
};

export type TripletChecklistState = {
  slots: TripletSlot[];
  complete: boolean;
};

const REQUIRED_SLOTS: Array<{ type: TripletSlotType; label: string }> = [
  { type: "contract", label: "Contract" },
  { type: "budget", label: "Budget" },
  { type: "schedule", label: "Schedule" },
];

/**
 * A document whose analysis finished and waits for a human decision: not evaluated, not failed. It is the
 * user-facing lifecycle state (`lifecycleStatus`); the legacy polling `status` of such a document still reads
 * "processing".
 */
function isAwaitingApprovalStatus(status: unknown): boolean {
  return String(status ?? "").toLowerCase() === "review_required";
}

function isReadyStatus(status: unknown): boolean {
  return ["analyzed", "parsed"].includes(String(status ?? "").toLowerCase());
}

export function deriveTripletChecklist(
  documents: Pick<DocumentInfo, "type" | "status" | "lifecycleStatus">[],
): TripletChecklistState {
  const slots = REQUIRED_SLOTS.map(({ type, label }) => {
    const matchingDocuments = documents.filter((document) => document.type === type);
    const hasReadyDocument = matchingDocuments.some((document) =>
      isReadyStatus(document.status),
    );

    return {
      type,
      label,
      state: hasReadyDocument
        ? "ready"
        : matchingDocuments.some((document) => isAwaitingApprovalStatus(document.lifecycleStatus))
          ? "awaiting_approval"
          : matchingDocuments.length > 0
            ? "processing"
            : "missing",
    } satisfies TripletSlot;
  });

  return {
    slots,
    complete: slots.every((slot) => slot.state === "ready"),
  };
}

type TripletChecklistProps = {
  documents: DocumentInfo[];
  compact?: boolean;
  coherenceHref?: string;
  onUploadType?: (type: TripletSlotType) => void;
  onEvaluateCoherence?: () => void;
  evaluatePending?: boolean;
};

function stateLabel(state: TripletSlotState): string {
  if (state === "ready") return "Ready";
  if (state === "processing") return "Processing";
  if (state === "awaiting_approval") return "Awaiting approval";
  return "Missing";
}

/** One sentence per document type that waits for a decision; null when nothing does. */
export function awaitingApprovalNotice(checklist: TripletChecklistState): string | null {
  const waiting = checklist.slots.filter((slot) => slot.state === "awaiting_approval");
  if (waiting.length === 0) return null;
  const names = waiting.map((slot) => slot.label.toLowerCase()).join(" and ");
  return `The ${names} ${waiting.length > 1 ? "are" : "is"} awaiting approval: nothing is evaluated and no score is produced until a reviewer approves ${waiting.length > 1 ? "them" : "it"} in Review.`;
}

function stateVariant(state: TripletSlotState) {
  if (state === "ready") return "default";
  if (state === "processing" || state === "awaiting_approval") return "secondary";
  return "outline";
}

function SlotIcon({ state }: { state: TripletSlotState }) {
  if (state === "ready") {
    return <CheckCircle2 className="h-4 w-4 text-primary" />;
  }

  if (state === "processing" || state === "awaiting_approval") {
    return <Clock className="h-4 w-4 text-muted-foreground" />;
  }

  return <FileText className="h-4 w-4 text-muted-foreground" />;
}

export function TripletChecklist({
  documents,
  compact = false,
  coherenceHref,
  onUploadType,
  onEvaluateCoherence,
  evaluatePending = false,
}: TripletChecklistProps) {
  const checklist = deriveTripletChecklist(documents);
  const notice = awaitingApprovalNotice(checklist);

  if (compact) {
    return (
      <section className="rounded-lg border bg-card p-4" aria-label="Required document triplet">
        <div className="mb-3 flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold">Required document triplet</h2>
          <Badge variant={checklist.complete ? "default" : "outline"}>
            {checklist.complete ? "Complete" : "Incomplete"}
          </Badge>
        </div>
        <div className="grid gap-2 sm:grid-cols-3">
          {checklist.slots.map((slot) => (
            <div key={slot.type} className="flex items-center gap-2 text-sm">
              <SlotIcon state={slot.state} />
              <span>
                {slot.label} {slot.state.replace("_", " ")}
              </span>
            </div>
          ))}
        </div>
        {notice ? (
          <p role="status" data-testid="triplet-awaiting-approval" className="mt-3 text-sm text-amber-900">
            {notice}
          </p>
        ) : null}
      </section>
    );
  }

  if (checklist.complete) {
    return (
      <section className="flex flex-col gap-3 rounded-2xl border bg-card/80 p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <CheckCircle2 className="h-5 w-5 text-primary" />
          <div>
            <h2 className="text-sm font-semibold">
              Triplet complete — run the coherence audit
            </h2>
            <p className="text-sm text-muted-foreground">
              Contract, budget, and schedule evidence are ready.
            </p>
          </div>
        </div>
        {onEvaluateCoherence ? (
          <Button
            type="button"
            onClick={onEvaluateCoherence}
            disabled={evaluatePending}
            className="rounded-xl"
          >
            {evaluatePending ? "Evaluating..." : "Evaluate coherence"}
          </Button>
        ) : coherenceHref ? (
          <Button asChild variant="outline" className="rounded-xl">
            <Link href={coherenceHref}>Open coherence</Link>
          </Button>
        ) : null}
      </section>
    );
  }

  return (
    <section className="rounded-2xl border bg-card/80 p-4 shadow-sm" aria-label="Required document triplet">
      <div className="mb-4 flex flex-col gap-1">
        <h2 className="text-sm font-semibold">Required document triplet</h2>
        <p className="text-sm text-muted-foreground">
          Upload contract, budget, and schedule documents before running the coherence audit.
        </p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        {checklist.slots.map((slot) => (
          <div key={slot.type} className="rounded-xl border bg-background/80 p-3">
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <SlotIcon state={slot.state} />
                <span className="font-medium">{slot.label}</span>
              </div>
              <Badge variant={stateVariant(slot.state)}>{stateLabel(slot.state)}</Badge>
            </div>
            {slot.state === "missing" ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3 rounded-xl"
                onClick={() => onUploadType?.(slot.type)}
              >
                <Upload className="mr-2 h-4 w-4" />
                Upload {slot.type}
              </Button>
            ) : null}
          </div>
        ))}
      </div>
      {notice ? (
        <p
          role="status"
          data-testid="triplet-awaiting-approval"
          className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
        >
          {notice}
        </p>
      ) : null}
    </section>
  );
}
