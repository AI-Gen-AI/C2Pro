import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@/src/tests/test-utils";

const useSearchParamsMock = vi.fn();
const useProjectDocumentsMock = vi.fn();
const useDocumentEntitiesMock = vi.fn();
const useDocumentAlertsMock = vi.fn();
const getDocumentDownloadUrlMock = vi.fn();
const createHighlightsFromAlertsMock = vi.fn();
const reviewApprovalResourceMock = vi.fn();
const reviewAlertMock = vi.fn();
const resolveAlertMock = vi.fn();

vi.mock("react", async () => {
  const actual = await vi.importActual<typeof import("react")>("react");
  return {
    ...actual,
    use: <T,>(value: Promise<T> | T) => value,
  };
});

vi.mock("next/navigation", () => ({
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

vi.mock("@/lib/api", () => ({
  getDocumentDownloadUrl: (...args: unknown[]) =>
    getDocumentDownloadUrlMock(...args),
  createHighlightsFromAlerts: (...args: unknown[]) =>
    createHighlightsFromAlertsMock(...args),
  reviewApprovalResource: (...args: unknown[]) =>
    reviewApprovalResourceMock(...args),
  reviewAlert: (...args: unknown[]) => reviewAlertMock(...args),
  resolveAlert: (...args: unknown[]) => resolveAlertMock(...args),
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

import EvidencePage from "./page";

describe("EvidencePage highlight mapping", () => {
  beforeEach(() => {
    useSearchParamsMock.mockReset();
    useProjectDocumentsMock.mockReset();
    useDocumentEntitiesMock.mockReset();
    useDocumentAlertsMock.mockReset();
    getDocumentDownloadUrlMock.mockReset();
    createHighlightsFromAlertsMock.mockReset();
    reviewApprovalResourceMock.mockReset();
    reviewAlertMock.mockReset();
    resolveAlertMock.mockReset();

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
    getDocumentDownloadUrlMock.mockReturnValue("/api/documents/doc-1/download");
    createHighlightsFromAlertsMock.mockReturnValue([]);
    reviewApprovalResourceMock.mockResolvedValue({ status: "APPROVED" });
    reviewAlertMock.mockResolvedValue({
      id: "alert-1",
      title: "Delay issue",
      description: "Needs review",
      severity: "high",
      status: "in_progress",
    });
    resolveAlertMock.mockResolvedValue({
      id: "alert-1",
      title: "Delay issue",
      description: "Needs review",
      severity: "high",
      status: "resolved",
    });
  });

  it("maps entity selection to the generated highlight id", () => {
    render(<EvidencePage params={{ id: "proj-1" } as never} />);

    fireEvent.click(screen.getByRole("button", { name: /^entity clause-1$/i }));

    expect(screen.getByTestId("viewer-active-highlight")).toHaveTextContent(
      "highlight-clause-1",
    );
  });

  it("maps viewer highlight clicks back to the entity id", () => {
    render(<EvidencePage params={{ id: "proj-1" } as never} />);

    fireEvent.click(
      screen.getByRole("button", { name: /trigger viewer highlight/i }),
    );

    expect(screen.getByTestId("active-entity-id")).toHaveTextContent(
      "clause-1",
    );
  });

  it("wires entity approval to the backend approval endpoint", async () => {
    render(<EvidencePage params={{ id: "proj-1" } as never} />);

    fireEvent.click(
      screen.getByRole("button", { name: /approve entity clause-1/i }),
    );

    await waitFor(() => {
      expect(reviewApprovalResourceMock).toHaveBeenCalledWith(
        "stakeholders",
        "clause-1",
        "APPROVED",
      );
    });
  });

  it("wires alert resolution actions to backend endpoints", async () => {
    render(<EvidencePage params={{ id: "proj-1" } as never} />);

    fireEvent.click(screen.getByRole("button", { name: /approve alert/i }));
    fireEvent.click(screen.getByRole("button", { name: /resolve alert/i }));

    await waitFor(() => {
      expect(reviewAlertMock).toHaveBeenCalledWith("alert-1", "approve");
      expect(resolveAlertMock).toHaveBeenCalledWith(
        "alert-1",
        "Resolved from evidence viewer",
        "web-evidence-viewer",
      );
    });
  });

  it("searches highlights and focuses the selected match", () => {
    createHighlightsFromAlertsMock.mockReturnValue([
      {
        id: "highlight-alert-1",
        entityId: "alert-1",
        page: 2,
        color: "red",
        label: "Delay issue",
        rects: [],
      },
    ]);

    render(<EvidencePage params={{ id: "proj-1" } as never} />);

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
});
