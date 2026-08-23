import { act } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@/src/tests/test-utils";
import { AnalysisProgressTracker } from "./AnalysisProgressTracker";

const authState = vi.hoisted(() => ({
  token: "test-token" as string | null,
}));

const handleAuthErrorStatus = vi.hoisted(() => vi.fn());

vi.mock("@/stores/auth", () => ({
  useAuthStore: {
    getState: () => authState,
  },
}));

vi.mock("@/lib/api/client", () => ({
  handleAuthErrorStatus,
}));

type Listener = (event: MessageEvent<string>) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];
  onerror: (() => void) | null = null;
  readonly listeners = new Map<string, Listener[]>();

  constructor() {
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

  close() {}

  emit(type: string, data: unknown) {
    const event = new MessageEvent("message", {
      data: JSON.stringify(data),
    });
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }
}

describe("AnalysisProgressTracker", () => {
  beforeEach(() => {
    authState.token = "test-token";
    handleAuthErrorStatus.mockReset();
    MockEventSource.instances = [];
    vi.stubGlobal(
      "EventSource",
      MockEventSource as unknown as typeof EventSource,
    );
  });

  it("turns stream auth loss into a session-expired state", () => {
    render(<AnalysisProgressTracker projectId="proj-123" />);

    authState.token = null;
    act(() => {
      MockEventSource.instances[0]?.onerror?.();
    });

    expect(handleAuthErrorStatus).toHaveBeenCalledWith(401);
    expect(screen.getByText(/session expired/i)).toBeInTheDocument();
  });

  it("maps technical stage events into four user-facing progress buckets", () => {
    render(<AnalysisProgressTracker projectId="proj-123" />);

    expect(screen.getByText("Reading documents")).toBeInTheDocument();
    expect(screen.getByText("Extracting & cross-checking")).toBeInTheDocument();
    expect(screen.getByText("Quality review")).toBeInTheDocument();
    expect(screen.getByText("Finalizing")).toBeInTheDocument();
    expect(screen.queryByText(/17-node LangGraph pipeline/i)).not.toBeInTheDocument();

    act(() => {
      MockEventSource.instances[0]?.emit("stage", {
        stage: 5,
        name: "WBS Extraction",
        progress: 35,
      });
    });

    expect(screen.getByText(/currently: extracting & cross-checking/i)).toBeInTheDocument();
    expect(screen.getByText("35%")).toBeInTheDocument();
  });

  it("settles into a completed state and stops the finalizing spinner on the complete event", () => {
    const { container } = render(<AnalysisProgressTracker projectId="proj-123" />);
    const source = MockEventSource.instances[0]!;

    // Finalizing can legitimately be RUNNING while progress is already 100 (pre-complete).
    act(() => {
      source.emit("stage", { stage: 16, name: "Final Assembly", progress: 100 });
    });
    expect(screen.getByText(/currently: finalizing/i)).toBeInTheDocument();
    expect(screen.getByText("In Progress")).toBeInTheDocument(); // progress=100 alone is NOT completion
    expect(container.querySelector(".animate-spin")).not.toBeNull(); // finalizing spinner is running

    // The complete event flips the whole tracker to COMPLETED.
    act(() => {
      source.emit("complete", { result: "ok" });
    });

    expect(screen.queryByText(/currently: finalizing/i)).not.toBeInTheDocument();
    expect(screen.getAllByText("Completed").length).toBeGreaterThan(0);
    expect(container.querySelector(".animate-spin")).toBeNull(); // spinner stopped
  });
});
