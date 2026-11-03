import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";
import { CoherenceActions } from "./coherence-actions";

const useProjectDocumentsMock = vi.fn();
const evaluateCoherenceMock = vi.fn();
let contractPendingApproval = false;

vi.mock("@/hooks/useProjectDocuments", () => ({
  useProjectDocuments: (...args: unknown[]) => useProjectDocumentsMock(...args),
}));

vi.mock("@/hooks/useProjectCoherenceActions", () => ({
  useProjectCoherenceActions: () => ({
    evaluateCoherence: evaluateCoherenceMock,
    rerunAnalysis: vi.fn(),
    contractPendingApproval,
    isEvaluating: false,
    isRerunningAnalysis: false,
  }),
  CONTRACT_PENDING_MESSAGE: "A contract is awaiting approval, so nothing was evaluated.",
}));

describe("CoherenceActions", () => {
  beforeEach(() => {
    useProjectDocumentsMock.mockReset();
    evaluateCoherenceMock.mockReset();
    contractPendingApproval = false;
  });

  it("tells the user a contract awaits approval, without a score or an error", () => {
    contractPendingApproval = true;
    useProjectDocumentsMock.mockReturnValue({
      documents: [{ id: "contract", name: "Contract.docx", type: "contract", status: "parsed" }],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<CoherenceActions projectId="proj-real-1" />);

    expect(screen.getByTestId("contract-pending-approval")).toHaveTextContent(
      /contract is awaiting approval/i,
    );
    expect(screen.queryByText(/not found/i)).not.toBeInTheDocument();
  });

  it("shows no pending-approval notice by default", () => {
    useProjectDocumentsMock.mockReturnValue({
      documents: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<CoherenceActions projectId="proj-real-1" />);

    expect(screen.queryByTestId("contract-pending-approval")).not.toBeInTheDocument();
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
