import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";
import { CoherenceActions } from "./coherence-actions";

const useProjectDocumentsMock = vi.fn();
const evaluateCoherenceMock = vi.fn();

vi.mock("@/hooks/useProjectDocuments", () => ({
  useProjectDocuments: (...args: unknown[]) => useProjectDocumentsMock(...args),
}));

vi.mock("@/hooks/useProjectCoherenceActions", () => ({
  useProjectCoherenceActions: () => ({
    evaluateCoherence: evaluateCoherenceMock,
    rerunAnalysis: vi.fn(),
    isEvaluating: false,
    isRerunningAnalysis: false,
  }),
}));

describe("CoherenceActions", () => {
  beforeEach(() => {
    useProjectDocumentsMock.mockReset();
    evaluateCoherenceMock.mockReset();
  });

  it("disables evaluation until the required triplet is complete", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        { id: "contract", name: "Contract.pdf", type: "contract", status: "parsed" },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<CoherenceActions projectId="proj-real-1" />);

    expect(
      screen.getByRole("button", { name: /evaluate coherence/i }),
    ).toBeDisabled();
    expect(screen.getByText(/upload contract, budget, and schedule/i)).toBeInTheDocument();
  });

  it("runs coherence evaluation when the triplet is complete", async () => {
    evaluateCoherenceMock.mockResolvedValueOnce(undefined);
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        { id: "contract", name: "Contract.pdf", type: "contract", status: "parsed" },
        { id: "budget", name: "Budget.xlsx", type: "budget", status: "parsed" },
        { id: "schedule", name: "Schedule.xlsx", type: "schedule", status: "analyzed" },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<CoherenceActions projectId="proj-real-1" />);

    fireEvent.click(screen.getByRole("button", { name: /evaluate coherence/i }));

    await waitFor(() => expect(evaluateCoherenceMock).toHaveBeenCalledTimes(1));
  });
});
