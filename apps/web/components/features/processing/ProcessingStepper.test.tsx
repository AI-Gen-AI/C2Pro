/**
 * Test Suite ID: S2-10
 * Roadmap Reference: S2-10 SSE processing stepper + withCredentials (FLAG-3)
 */
import { render, screen } from "@/src/tests/test-utils";
import { describe, expect, it, vi } from "vitest";
import {
  ProcessingStepper,
  createProcessingEventSource,
  isProcessingSseEvent,
} from "@/components/features/processing/ProcessingStepper";

type Listener = (event: MessageEvent<string>) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];
  readonly url: string;
  readonly withCredentials: boolean;
  readonly listeners = new Map<string, Listener[]>();

  constructor(url: string, init?: EventSourceInit) {
    this.url = url;
    this.withCredentials = init?.withCredentials ?? false;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListenerOrEventListenerObject) {
    const callback =
      typeof listener === "function"
        ? (listener as Listener)
        : ((listener as EventListenerObject).handleEvent as Listener);
    const current = this.listeners.get(type) ?? [];
    this.listeners.set(type, [...current, callback]);
  }

  removeEventListener(
    type: string,
    listener: EventListenerOrEventListenerObject,
  ) {
    const callback =
      typeof listener === "function"
        ? (listener as Listener)
        : ((listener as EventListenerObject).handleEvent as Listener);
    const current = this.listeners.get(type) ?? [];
    this.listeners.set(
      type,
      current.filter((candidate) => candidate !== callback),
    );
  }

  close() {}

  emit(eventType: string, payload: unknown) {
    const listeners = this.listeners.get(eventType) ?? [];
    const event = new MessageEvent<string>(eventType, {
      data: JSON.stringify(payload),
    });
    listeners.forEach((listener) => listener(event));
  }
}

describe("S2-10 RED - ProcessingStepper", () => {
  it("[S2-10-RED-01] enforces credentialed SSE transport with withCredentials=true", () => {
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);

    createProcessingEventSource("proj_demo_001");

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0]?.withCredentials).toBe(true);
  });

  it("[S2-10-RED-01b] rejects non-credentialed stream config", () => {
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);

    expect(() =>
      createProcessingEventSource("proj_demo_001", { withCredentials: false }),
    ).toThrow(/withCredentials must be true/i);
  });

  it("[S2-10-RED-02] progresses exact step order and progress from staged SSE events", () => {
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);

    render(<ProcessingStepper projectId="proj_demo_001" />);

    const source = MockEventSource.instances[0];
    expect(source).toBeDefined();

    source?.emit("stage", { stage: 1, name: "Extracting text", progress: 16 });
    source?.emit("stage", { stage: 2, name: "Identifying clauses", progress: 33 });
    source?.emit("stage", { stage: 3, name: "Cross-referencing", progress: 50 });
    source?.emit("stage", { stage: 4, name: "Detecting anomalies", progress: 66 });
    source?.emit("stage", { stage: 5, name: "Calculating weights", progress: 83 });

    expect(screen.getByTestId("processing-step-1")).toHaveTextContent(
      /extracting text/i,
    );
    expect(screen.getByTestId("processing-step-2")).toHaveTextContent(
      /identifying clauses/i,
    );
    expect(screen.getByTestId("processing-step-3")).toHaveTextContent(
      /cross-referencing/i,
    );
    expect(screen.getByTestId("processing-step-4")).toHaveTextContent(
      /detecting anomalies/i,
    );
    expect(screen.getByTestId("processing-step-5")).toHaveTextContent(
      /calculating weights/i,
    );
    expect(
      screen.getByRole("progressbar", { name: /processing progress/i }),
    ).toHaveAttribute("aria-valuenow", "83");
  });

  it("[S2-10-RED-03] transitions to terminal success on complete event", () => {
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);

    render(<ProcessingStepper projectId="proj_demo_001" />);

    const source = MockEventSource.instances[0];
    source?.emit("complete", {
      global_score: 78,
      documents_analyzed: 8,
      completed_at: "2026-02-14T12:00:00Z",
    });

    expect(screen.getByRole("status")).toHaveTextContent(/processing complete/i);
    expect(
      screen.getByRole("progressbar", { name: /processing progress/i }),
    ).toHaveAttribute("aria-valuenow", "100");
    expect(screen.getByText(/global score: 78/i)).toBeInTheDocument();
    expect(screen.getByText(/documents analyzed: 8/i)).toBeInTheDocument();
  });

  it("[S2-10-RED-07] publishes accessible live updates for each transition", () => {
    vi.stubGlobal("EventSource", MockEventSource as unknown as typeof EventSource);

    render(<ProcessingStepper projectId="proj_demo_001" />);

    const liveRegion = screen.getByRole("status");
    expect(liveRegion).toHaveAttribute("aria-live", "polite");

    MockEventSource.instances[0]?.emit("stage", {
      stage: 1,
      name: "Extracting text",
      progress: 16,
    });

    expect(liveRegion).toHaveTextContent(/extracting text/i);
  });

  it("[S2-10-RED-08] accepts only expected SSE event schema", () => {
    expect(
      isProcessingSseEvent({
        event: "stage",
        data: { stage: 1, name: "Extracting text", progress: 16 },
      }),
    ).toBe(true);

    expect(
      isProcessingSseEvent({
        event: "stage",
        data: { stage: "one", name: "Extracting text", progress: 16 },
      }),
    ).toBe(false);

    expect(
      isProcessingSseEvent({
        event: "complete",
        data: { global_score: "78", documents_analyzed: 8 },
      }),
    ).toBe(false);
  });
});
