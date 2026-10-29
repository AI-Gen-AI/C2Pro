"use client";

import { Button } from "@/components/ui/button";
import {
  deriveTripletChecklist,
  TripletChecklist,
} from "@/components/features/documents/TripletChecklist";
import {
  CONTRACT_PENDING_MESSAGE,
  useProjectCoherenceActions,
} from "@/hooks/useProjectCoherenceActions";
import { useProjectDocuments } from "@/hooks/useProjectDocuments";

type CoherenceActionsProps = {
  projectId: string;
};

export function CoherenceActions({ projectId }: CoherenceActionsProps) {
  const { documents } = useProjectDocuments(projectId);
  const checklist = deriveTripletChecklist(documents);
  const { evaluateCoherence, isEvaluating, contractPendingApproval } =
    useProjectCoherenceActions(projectId);
  const disabled = !checklist.complete || isEvaluating;

  return (
    <section className="rounded-lg border bg-card p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <h2 className="text-sm font-semibold">Coherence audit</h2>
          <p className="text-sm text-muted-foreground">
            Upload contract, budget, and schedule before evaluating coherence.
          </p>
        </div>
        <Button
          type="button"
          className="rounded-xl"
          disabled={disabled}
          title={
            checklist.complete
              ? undefined
              : "Upload contract, budget, and schedule before evaluating coherence."
          }
          onClick={() => void evaluateCoherence()}
        >
          {isEvaluating ? "Evaluating..." : "Evaluate coherence"}
        </Button>
      </div>
      {contractPendingApproval ? (
        <p
          role="status"
          data-testid="contract-pending-approval"
          className="mt-4 rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"
        >
          {CONTRACT_PENDING_MESSAGE}
        </p>
      ) : null}
      {!checklist.complete ? (
        <div className="mt-4">
          <TripletChecklist documents={documents} compact />
        </div>
      ) : null}
    </section>
  );
}
