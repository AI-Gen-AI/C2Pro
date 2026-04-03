import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";

const useSearchParamsMock = vi.fn();
const useProjectDocumentsMock = vi.fn();
const useProjectMock = vi.fn();
const useDocumentEntitiesMock = vi.fn();
const useDocumentAlertsMock = vi.fn();
const useDocumentHistoryMock = vi.fn();
const useDocumentRelationshipExplanationMock = vi.fn();
const reviewApprovalMutateAsyncMock = vi.fn();
const reviewAlertMutateAsyncMock = vi.fn();
const resolveAlertMutateAsyncMock = vi.fn();

vi.mock("next/navigation", () => ({
  useParams: () => ({ id: "proj-1" }),
  useSearchParams: () => useSearchParamsMock(),
}));

vi.mock("@/hooks/useProjectDocuments", () => ({
  useProjectDocuments: (...args: unknown[]) => useProjectDocumentsMock(...args),
}));

vi.mock("@/hooks/useProject", () => ({
  useProject: (...args: unknown[]) => useProjectMock(...args),
}));

vi.mock("@/hooks/useDocumentEntities", () => ({
  useDocumentEntities: (...args: unknown[]) => useDocumentEntitiesMock(...args),
}));

vi.mock("@/hooks/useDocumentAlerts", () => ({
  useDocumentAlerts: (...args: unknown[]) => useDocumentAlertsMock(...args),
}));

vi.mock("@/hooks/useDocumentHistory", () => ({
  useDocumentHistory: (...args: unknown[]) => useDocumentHistoryMock(...args),
}));

vi.mock("@/hooks/useDocumentRelationshipExplanation", () => ({
  useDocumentRelationshipExplanation: (...args: unknown[]) =>
    useDocumentRelationshipExplanationMock(...args),
}));

vi.mock("@/lib/api/generated/approvals/approvals", () => ({
  useReviewResourceApiV1ApprovalsResourceTypeResourceIdPatch: () => ({
    mutateAsync: (...args: unknown[]) => reviewApprovalMutateAsyncMock(...args),
  }),
}));

vi.mock("@/lib/api/generated/alerts/alerts", () => ({
  useReviewAlertApiV1AlertsAlertIdReviewPost: () => ({
    mutateAsync: (...args: unknown[]) => reviewAlertMutateAsyncMock(...args),
  }),
  useResolveAlertApiV1AlertsAlertIdResolvePost: () => ({
    mutateAsync: (...args: unknown[]) => resolveAlertMutateAsyncMock(...args),
  }),
}));

vi.mock("@/components/features/evidence/LazyPdfEvidenceViewer", () => ({
  LazyPdfEvidenceViewer: ({
    fileUrl,
    highlights,
    activeHighlightId,
    onHighlightClick,
  }: {
    fileUrl: string;
    highlights: Array<{
      id: string;
      clauseId: string;
      page: number;
      text: string;
    }>;
    activeHighlightId: string | null;
    onHighlightClick: (id: string) => void;
  }) => (
    <div>
      <div data-testid="viewer-file-url">{fileUrl}</div>
      <div data-testid="viewer-active-highlight">
        {activeHighlightId ?? "none"}
      </div>
      <div data-testid="viewer-highlight-ids">
        {highlights.map((item) => item.id).join(",")}
      </div>
      {highlights.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onHighlightClick(item.id)}
        >
          Viewer Highlight {item.text}
        </button>
      ))}
      <button
        type="button"
        onClick={() => onHighlightClick(highlights[0]?.id ?? "")}
      >
        Trigger Viewer Highlight
      </button>
    </div>
  ),
}));

vi.mock("@/components/evidence", () => ({
  EntityValidationList: ({
    entities,
    onEntityClick,
    activeEntityId,
    onApprove,
    onReject,
  }: {
    entities: Array<{ id: string; text: string }>;
    onEntityClick?: (entity: { id: string; text: string }) => void;
    activeEntityId?: string | null;
    onApprove: (entityId: string) => void;
    onReject: (entityId: string, reason: string) => void;
  }) => (
    <div>
      <div data-testid="active-entity-id">{activeEntityId ?? "none"}</div>
      {entities.map((entity) => (
        <div key={entity.id}>
          <button type="button" onClick={() => onEntityClick?.(entity)}>
            Entity {entity.id}
          </button>
          <button type="button" onClick={() => onApprove(entity.id)}>
            Approve Entity {entity.id}
          </button>
          <button type="button" onClick={() => onReject(entity.id, "bad data")}>
            Reject Entity {entity.id}
          </button>
        </div>
      ))}
    </div>
  ),
}));

vi.mock("@/components/ui/tabs", () => ({
  Tabs: ({ children }: { children: any }) => <div>{children}</div>,
  TabsList: ({ children }: { children: any }) => <div>{children}</div>,
  TabsTrigger: ({ children }: { children: any }) => (
    <button type="button">{children}</button>
  ),
  TabsContent: ({ children }: { children: any }) => <div>{children}</div>,
}));

vi.mock("@/components/ui/dropdown-menu", () => ({
  DropdownMenu: ({ children }: { children: any }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }: { children: any }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }: { children: any }) => <div>{children}</div>,
  DropdownMenuItem: ({
    children,
    onClick,
  }: {
    children: any;
    onClick?: () => void;
  }) => (
    <button type="button" onClick={onClick}>
      {children}
    </button>
  ),
}));

import EvidencePage from "./page";

describe("EvidencePage highlight mapping", () => {
  beforeEach(() => {
    useSearchParamsMock.mockReset();
    useProjectDocumentsMock.mockReset();
    useProjectMock.mockReset();
    useDocumentEntitiesMock.mockReset();
    useDocumentAlertsMock.mockReset();
    useDocumentHistoryMock.mockReset();
    useDocumentRelationshipExplanationMock.mockReset();
    reviewApprovalMutateAsyncMock.mockReset();
    reviewAlertMutateAsyncMock.mockReset();
    resolveAlertMutateAsyncMock.mockReset();
    useProjectMock.mockReturnValue({
      data: {
        id: "proj-1",
        name: "Atlas Ridge",
      },
    });

    useSearchParamsMock.mockReturnValue({
      get: vi.fn().mockReturnValue(null),
    });
    useProjectDocumentsMock.mockReturnValue({
      documents: [
        {
          id: "doc-1",
          name: "Contract.pdf",
          type: "contract",
          created_at: "2026-01-20T09:00:00Z",
          updated_at: "2026-01-21T09:00:00Z",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    useDocumentEntitiesMock.mockReturnValue({
      entities: [
        {
          id: "clause-1",
          type: "stakeholder",
          text: "Delay penalty",
          confidence: 92,
          page: 3,
        },
      ],
      highlights: [
        {
          id: "highlight-clause-1",
          entityId: "clause-1",
          page: 3,
          color: "green",
          label: "Delay penalty",
          rects: [],
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    useDocumentAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "alert-1",
          title: "Delay issue",
          description: "Needs review",
          severity: "high",
          status: "open",
          created_at: "2026-01-21T14:23:00Z",
          updated_at: "2026-01-21T16:30:00Z",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    useDocumentHistoryMock.mockReturnValue({
      items: [],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    useDocumentRelationshipExplanationMock.mockReturnValue({
      explanation: null,
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    reviewApprovalMutateAsyncMock.mockResolvedValue({ status: "APPROVED" });
    reviewAlertMutateAsyncMock.mockResolvedValue({
      id: "alert-1",
      title: "Delay issue",
      description: "Needs review",
      severity: "high",
      status: "in_progress",
    });
    resolveAlertMutateAsyncMock.mockResolvedValue({
      id: "alert-1",
      title: "Delay issue",
      description: "Needs review",
      severity: "high",
      status: "resolved",
    });
  });

  it("maps entity selection to the generated highlight id", () => {
    render(<EvidencePage />);

    fireEvent.click(screen.getByRole("button", { name: /^entity clause-1$/i }));

    expect(screen.getByTestId("viewer-active-highlight")).toHaveTextContent(
      "highlight-clause-1",
    );
  });

  it("maps viewer highlight clicks back to the entity id", () => {
    render(<EvidencePage />);

    fireEvent.click(
      screen.getByRole("button", { name: /trigger viewer highlight/i }),
    );

    expect(screen.getByTestId("active-entity-id")).toHaveTextContent(
      "clause-1",
    );
  });

  it("maps viewer alert highlight clicks back to the alerts panel selection", () => {
    useDocumentAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "alert-1",
          title: "Delay issue",
          description: "Needs review",
          severity: "critical",
          status: "open",
          evidence_json: {
            evidence_location: {
              page_number: 2,
              bbox: [0.1, 0.2, 0.3, 0.4],
              normalized: true,
            },
          },
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<EvidencePage />);

    fireEvent.click(
      screen.getByRole("button", { name: /viewer highlight delay issue/i }),
    );

    expect(screen.getByTestId("viewer-active-highlight")).toHaveTextContent(
      "highlight-alert-1",
    );
    expect(
      screen.getByRole("button", { name: /focus alert delay issue/i }),
    ).toHaveAttribute("aria-pressed", "true");
  });

  it("wires entity approval to the backend approval endpoint", async () => {
    render(<EvidencePage />);

    fireEvent.click(
      screen.getByRole("button", { name: /approve entity clause-1/i }),
    );

    expect(screen.getByText("Confirm evidence action")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /confirm action/i }));

    await waitFor(() => {
      expect(reviewApprovalMutateAsyncMock).toHaveBeenCalledWith({
        resourceType: "stakeholders",
        resourceId: "clause-1",
        data: {
          status: "APPROVED",
          correction_data: undefined,
          feedback_comment: null,
        },
      });
    });
  });

  it("shows the fetched project name instead of the raw route id in the evidence subtitle", () => {
    render(<EvidencePage />);

    expect(screen.getByText("Project: Atlas Ridge")).toBeInTheDocument();
    expect(screen.queryByText("Project: proj-1")).not.toBeInTheDocument();
  });

  it("requires a validation note before approving entities below 90 percent confidence", async () => {
    useDocumentEntitiesMock.mockReturnValue({
      entities: [
        {
          id: "clause-2",
          type: "stakeholder",
          text: "Unverified scope note",
          confidence: 88,
          page: 4,
        },
      ],
      highlights: [
        {
          id: "highlight-clause-2",
          entityId: "clause-2",
          page: 4,
          color: "yellow",
          label: "Unverified scope note",
          rects: [],
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<EvidencePage />);

    fireEvent.click(
      screen.getByRole("button", { name: /approve entity clause-2/i }),
    );

    expect(screen.getByText("Confirm evidence action")).toBeInTheDocument();
    expect(
      screen.getByText(/confidence below 90% requires a validation note/i),
    ).toBeInTheDocument();

    const confirmButton = screen.getByRole("button", {
      name: /confirm action/i,
    });
    expect(confirmButton).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/validation note/i), {
      target: { value: "Reviewed against source context and accepted." },
    });

    expect(confirmButton).not.toBeDisabled();
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(reviewApprovalMutateAsyncMock).toHaveBeenCalledWith({
        resourceType: "stakeholders",
        resourceId: "clause-2",
        data: {
          status: "APPROVED",
          correction_data: undefined,
          feedback_comment: "Reviewed against source context and accepted.",
        },
      });
    });
  });

  it("requires confirmation before approving or rejecting alerts", async () => {
    render(<EvidencePage />);

    fireEvent.click(screen.getByRole("button", { name: /approve alert/i }));

    expect(screen.getByText("Confirm evidence action")).toBeInTheDocument();
    expect(screen.getByText(/approve alert-1/i)).toBeInTheDocument();
    expect(reviewAlertMutateAsyncMock).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: /confirm action/i }));

    await waitFor(() => {
      expect(reviewAlertMutateAsyncMock).toHaveBeenCalledWith({
        alertId: "alert-1",
        data: {
          decision: "approve",
          comment: "",
        },
      });
    });

    fireEvent.click(screen.getByRole("button", { name: /reject alert/i }));
    expect(screen.getByText(/reject alert-1/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /cancel action/i }));

    expect(reviewAlertMutateAsyncMock).toHaveBeenCalledTimes(1);
  });

  it("wires alert resolution actions to backend endpoints", async () => {
    render(<EvidencePage />);

    fireEvent.click(screen.getByRole("button", { name: /approve alert/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirm action/i }));
    await waitFor(() => {
      expect(
        screen.queryByText("Confirm evidence action"),
      ).not.toBeInTheDocument();
    });
    fireEvent.click(screen.getByRole("button", { name: /resolve alert/i }));

    await waitFor(() => {
      expect(reviewAlertMutateAsyncMock).toHaveBeenCalledWith({
        alertId: "alert-1",
        data: {
          decision: "approve",
          comment: "",
        },
      });
      expect(resolveAlertMutateAsyncMock).toHaveBeenCalledWith({
        alertId: "alert-1",
        data: {
          resolution: "Resolved from evidence viewer",
          resolved_by: "web-evidence-viewer",
          root_cause: "other",
        },
      });
    });
  });

  it("searches highlights and focuses the selected match", () => {
    useDocumentAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "alert-1",
          title: "Delay issue",
          description: "Needs review",
          severity: "critical",
          status: "open",
          evidence_json: {
            evidence_location: {
              page_number: 2,
              bbox: [0.1, 0.2, 0.3, 0.4],
              normalized: true,
            },
          },
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<EvidencePage />);

    fireEvent.change(
      screen.getByPlaceholderText(/search highlights in this document/i),
      {
        target: { value: "delay" },
      },
    );

    expect(screen.getByText(/2 matches/i)).toBeInTheDocument();
    fireEvent.click(
      screen.getByRole("button", { name: /^delay issue alert-1 - page 2$/i }),
    );

    expect(screen.getByTestId("viewer-active-highlight")).toHaveTextContent(
      "highlight-alert-1",
    );
  });

  it("renders an interactive relationship graph and focuses linked evidence from graph nodes", () => {
    useDocumentAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "alert-1",
          title: "Delay issue",
          description: "Needs review",
          severity: "critical",
          status: "open",
          evidence_json: {
            evidence_location: {
              page_number: 2,
              bbox: [0.1, 0.2, 0.3, 0.4],
              normalized: true,
            },
          },
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<EvidencePage />);

    expect(screen.getByText(/relationship graph/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /graph node clause-1/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /graph node alert-1/i })).toBeInTheDocument();
    expect(screen.getByText(/1 linked alert/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /graph node clause-1/i }));

    expect(screen.getByTestId("viewer-active-highlight")).toHaveTextContent(
      "highlight-clause-1",
    );
  });

  it("toggles the relationship section into a 3D viewer mode and keeps graph-node focus wiring", () => {
    useDocumentAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "alert-1",
          title: "Delay issue",
          description: "Needs review",
          severity: "critical",
          status: "open",
          evidence_json: {
            evidence_location: {
              page_number: 2,
              bbox: [0.1, 0.2, 0.3, 0.4],
              normalized: true,
            },
          },
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<EvidencePage />);

    fireEvent.click(screen.getByRole("button", { name: /3d relationship view/i }));

    expect(screen.getByText(/3d relationship viewer/i)).toBeInTheDocument();
    expect(screen.getByText(/depth layers/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /graph node clause-1/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /graph node clause-1/i }));

    expect(screen.getByTestId("viewer-active-highlight")).toHaveTextContent(
      "highlight-clause-1",
    );

    fireEvent.click(screen.getByRole("button", { name: /graph view/i }));

    expect(screen.getByText(/relationship graph/i)).toBeInTheDocument();
  });

  it("renders an evidence evolution timeline from persisted evidence history events", () => {
    useDocumentAlertsMock.mockReturnValue({
      alerts: [
        {
          id: "alert-1",
          title: "Delay issue",
          description: "Needs review",
          severity: "critical",
          status: "open",
          created_at: "2026-01-21T14:23:00Z",
          updated_at: "2026-01-21T16:30:00Z",
          evidence_json: {
            evidence_location: {
              page_number: 2,
              bbox: [0.1, 0.2, 0.3, 0.4],
              normalized: true,
            },
          },
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });
    useDocumentHistoryMock.mockReturnValue({
      items: [
        {
          id: "document-uploaded-doc-1",
          title: "Document uploaded",
          detail: "Contract.pdf",
          occurredAt: "2026-01-20T09:00:00Z",
        },
        {
          id: "document-parsed-doc-1",
          title: "Document parsed",
          detail: "12 clauses extracted",
          occurredAt: "2026-01-21T09:15:00Z",
        },
        {
          id: "alert-history-alert-1-reviewed",
          title: "Alert reviewed",
          detail: "Delay issue",
          occurredAt: "2026-01-21T15:00:00Z",
        },
      ],
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<EvidencePage />);

    const timelineHeading = screen.getByText(/evidence evolution timeline/i);
    expect(timelineHeading).toBeInTheDocument();
    expect(screen.getByText(/document uploaded/i)).toBeInTheDocument();
    expect(screen.getByText(/document parsed/i)).toBeInTheDocument();
    expect(screen.getByText(/alert reviewed/i)).toBeInTheDocument();
    expect(screen.getAllByText(/2026-01-21/i).length).toBeGreaterThan(0);
    expect(
      screen.queryByText(/current snapshot derived from document and alert timestamps/i),
    ).not.toBeInTheDocument();
  });

  it("renders an AI explanation of the current evidence relationships from the live graph data", () => {
    useDocumentRelationshipExplanationMock.mockReturnValue({
      explanation: {
        summary: "This document connects 2 extracted clauses to 2 active alerts.",
        strongestCluster:
          "The strongest relationship cluster centers on delay penalty.",
        reviewPriority:
          "Review priority is elevated because 1 alert is critical.",
        latestSignal: "Most recent signal: notice gap.",
        citations: [
          {
            clauseId: "clause-1",
            clauseCode: "CL-001",
            label: "Delay penalty",
            page: 3,
            reason: "Linked to active alert",
          },
          {
            clauseId: "clause-2",
            clauseCode: "CL-002",
            label: "Notice requirements",
            page: 5,
            reason: "Linked to active alert",
          },
        ],
      },
      loading: false,
      error: null,
      refetch: vi.fn(),
    });

    render(<EvidencePage />);

    expect(screen.getByText(/ai relationship explanation/i)).toBeInTheDocument();
    expect(
      screen.getByText(/this document connects 2 extracted clauses to 2 active alerts/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/the strongest relationship cluster centers on delay penalty/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/review priority is elevated because 1 alert is critical/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/most recent signal: notice gap/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/backend-generated explanation grounded in evidence graph citations/i)).toBeInTheDocument();
    expect(screen.getByText(/cl-001 · delay penalty/i)).toBeInTheDocument();
    expect(screen.getByText(/page 3 · linked to active alert/i)).toBeInTheDocument();
  });

  it("opens evidence templates and previews the selected review template", () => {
    render(<EvidencePage />);

    fireEvent.click(screen.getByRole("button", { name: /evidence templates/i }));

    expect(screen.getByText(/start from an evidence template/i)).toBeInTheDocument();
    expect(
      screen.getByText(/start from an evidence template/i).closest("[role='dialog']"),
    ).toHaveClass("bg-background/95", "shadow-2xl");
    expect(screen.getByRole("button", { name: /claims review/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /technical audit/i }));

    expect(screen.getByText(/technical audit focus/i)).toBeInTheDocument();
    expect(screen.getByText(/specification compliance/i)).toBeInTheDocument();
    expect(screen.getByText(/design-change evidence/i)).toBeInTheDocument();
  });

  it("uses surfaced toolbar controls and confirmation dialogs", () => {
    render(<EvidencePage />);

    expect(screen.getByRole("button", { name: /refresh/i })).toHaveClass(
      "bg-background/95",
      "shadow-sm",
    );
    expect(screen.getByRole("button", { name: /evidence templates/i })).toHaveClass(
      "bg-background/95",
      "shadow-sm",
    );

    fireEvent.click(screen.getByRole("button", { name: /approve entity clause-1/i }));

    expect(
      screen.getByText("Confirm evidence action").closest("[role='dialog']"),
    ).toHaveClass("bg-background/95", "shadow-2xl");
  });

  it("exports the active evidence view to JSON, CSV, and PDF", async () => {
    const popupDocument = {
      write: vi.fn(),
      close: vi.fn(),
    };
    const popupWindow = {
      document: popupDocument,
      focus: vi.fn(),
      print: vi.fn(),
    };
    const openSpy = vi
      .spyOn(window, "open")
      .mockReturnValue(popupWindow as unknown as Window);
    const createObjectUrlSpy = vi
      .spyOn(URL, "createObjectURL")
      .mockReturnValue("blob:evidence-export");
    const revokeObjectUrlSpy = vi
      .spyOn(URL, "revokeObjectURL")
      .mockImplementation(() => undefined);
    const appendSpy = vi.spyOn(document.body, "appendChild");
    const removeSpy = vi.spyOn(document.body, "removeChild");
    const anchorClickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, "click")
      .mockImplementation(() => undefined);

    render(<EvidencePage />);

    fireEvent.click(screen.getByRole("button", { name: /export json/i }));
    fireEvent.click(screen.getByRole("button", { name: /export csv/i }));
    fireEvent.click(screen.getByRole("button", { name: /export pdf/i }));

    expect(createObjectUrlSpy).toHaveBeenCalledTimes(2);
    expect(anchorClickSpy).toHaveBeenCalledTimes(2);
    expect(appendSpy).toHaveBeenCalled();
    expect(removeSpy).toHaveBeenCalled();
    expect(revokeObjectUrlSpy).toHaveBeenCalledWith("blob:evidence-export");
    expect(openSpy).toHaveBeenCalled();
    expect(popupDocument.write).toHaveBeenCalledWith(
      expect.stringContaining("Contract.pdf"),
    );
    expect(popupWindow.print).toHaveBeenCalled();
  });
});
