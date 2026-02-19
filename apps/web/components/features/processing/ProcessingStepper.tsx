/**
 * Test Suite ID: S2-10
 * Roadmap Reference: S2-10 SSE processing stepper + withCredentials (FLAG-3)
 */
import { useEffect, useMemo, useState } from "react";
import { flushSync } from "react-dom";

type StageData = {
  stage: number;
  name: string;
  progress: number;
};

type CompleteData = {
  global_score: number;
  documents_analyzed: number;
  completed_at?: string;
};

type ProcessingSseEvent =
  | { event: "stage"; data: StageData }
  | { event: "complete"; data: CompleteData };

type StepperState = {
  stages: StageData[];
  progress: number;
  statusText: string;
  completeData?: CompleteData;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isString(value: unknown): value is string {
  return typeof value === "string";
}

export function isProcessingSseEvent(value: unknown): value is ProcessingSseEvent {
  if (!isRecord(value) || !isString(value.event) || !isRecord(value.data)) {
    return false;
  }

  if (value.event === "stage") {
    return (
      isNumber(value.data.stage) &&
      isString(value.data.name) &&
      isNumber(value.data.progress)
    );
  }

  if (value.event === "complete") {
    return (
      isNumber(value.data.global_score) &&
      isNumber(value.data.documents_analyzed) &&
      (value.data.completed_at === undefined || isString(value.data.completed_at))
    );
  }

  return false;
}

export function createProcessingEventSource(
  projectId: string,
  init: EventSourceInit = { withCredentials: true },
): EventSource {
  if (init.withCredentials !== true) {
    throw new Error("withCredentials must be true for processing SSE");
  }

  const existing = eventSourcesByProject.get(projectId);
  if (existing) {
    return existing;
  }

  const source = new EventSource(`/api/v1/projects/${projectId}/process/stream`, {
    ...init,
    withCredentials: true,
  });
  eventSourcesByProject.set(projectId, source);
  return source;
}

const eventSourcesByProject = new Map<string, EventSource>();

export function ProcessingStepper({ projectId }: { projectId: string }) {
  const [state, setState] = useState<StepperState>({
    stages: [],
    progress: 0,
    statusText: "Waiting for processing updates...",
  });

  useEffect(() => {
    const source = createProcessingEventSource(projectId);

    const onStage = (event: MessageEvent<string>) => {
      const parsed = {
        event: "stage",
        data: JSON.parse(event.data),
      };
      if (!isProcessingSseEvent(parsed)) return;

      flushSync(() => {
        setState((current) => ({
          ...current,
          stages: [...current.stages, parsed.data],
          progress: parsed.data.progress,
          statusText: `Processing stage: ${parsed.data.name}`,
        }));
      });
    };

    const onComplete = (event: MessageEvent<string>) => {
      const parsed = {
        event: "complete",
        data: JSON.parse(event.data),
      };
      if (!isProcessingSseEvent(parsed)) return;

      flushSync(() => {
        setState((current) => ({
          ...current,
          progress: 100,
          statusText: "Processing complete",
          completeData: parsed.data,
        }));
      });
      source.close();
    };

    const onError = () => {
      flushSync(() => {
        setState((current) => ({
          ...current,
          statusText: "Processing stream interrupted",
        }));
      });
    };

    source.addEventListener("stage", onStage as EventListener);
    source.addEventListener("complete", onComplete as EventListener);
    source.addEventListener("error", onError);

    return () => {
      source.removeEventListener("stage", onStage as EventListener);
      source.removeEventListener("complete", onComplete as EventListener);
      source.removeEventListener("error", onError);
      source.close();
    };
  }, [projectId]);

  const orderedSteps = useMemo(
    () => [...state.stages].sort((a, b) => a.stage - b.stage),
    [state.stages],
  );

  return (
    <section aria-label="Processing Stepper">
      <div
        role="progressbar"
        aria-label="Processing progress"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={state.progress}
      />
      <div role="status" aria-live="polite">
        {state.statusText}
      </div>

      <ol>
        {orderedSteps.map((step) => (
          <li key={step.stage} data-testid={`processing-step-${step.stage}`}>
            {step.name}
          </li>
        ))}
      </ol>

      {state.completeData ? (
        <div>
          <p>Global score: {state.completeData.global_score}</p>
          <p>Documents analyzed: {state.completeData.documents_analyzed}</p>
        </div>
      ) : null}
    </section>
  );
}
