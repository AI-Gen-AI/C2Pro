import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";

const useSearchParamsMock = vi.fn();
const useProjectDocumentsMock = vi.fn();
const useDocumentEntitiesMock = vi.fn();
const useDocumentAlertsMock = vi.fn();
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

vi.mock("@/hooks/useDocumentEntities", () => ({
  useDocumentEntities: (...args: unknown[]) => useDocumentEntitiesMock(...args),
}));

vi.mock("@/hooks/useDocumentAlerts", () => ({
  useDocumentAlerts: (...args: unknown[]) => useDocumentAlertsMock(...args),
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

vi.mock("@/components/features/evidence/PdfEvidenceViewer", () => ({
  PdfEvidenceViewer: ({
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
    useDocumentEntitiesMock.mockReset();
    useDocumentAlertsMock.mockReset();
    reviewApprovalMutateAsyncMock.mockReset();
    reviewAlertMutateAsyncMock.mockReset();
    resolveAlertMutateAsyncMock.mockReset();

    useSearchParamsMock.mockReturnValue({
      get: vi.fn().mockReturnValue(null),
    });
    useProjectDocumentsMock.mockReturnValue({
      documents: [{ id: "doc-1", name: "Contract.pdf", type: "contract" }],
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
        },
      ],
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

  it("wires entity approval to the backend approval endpoint", async () => {
    render(<EvidencePage />);

    fireEvent.click(
      screen.getByRole("button", { name: /approve entity clause-1/i }),
    );

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

  it("wires alert resolution actions to backend endpoints", async () => {
    render(<EvidencePage />);

    fireEvent.click(screen.getByRole("button", { name: /approve alert/i }));
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
    fireEvent.click(screen.getByRole("button", { name: /delay issue/i }));

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

  it("opens evidence templates and previews the selected review template", () => {
    render(<EvidencePage />);

    fireEvent.click(screen.getByRole("button", { name: /evidence templates/i }));

    expect(screen.getByText(/start from an evidence template/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /claims review/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /technical audit/i }));

    expect(screen.getByText(/technical audit focus/i)).toBeInTheDocument();
    expect(screen.getByText(/specification compliance/i)).toBeInTheDocument();
    expect(screen.getByText(/design-change evidence/i)).toBeInTheDocument();
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
