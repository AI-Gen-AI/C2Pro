import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const narrow = vi.hoisted(() => ({ value: false }));
vi.mock("@/hooks/useIsNarrowViewport", () => ({ useIsNarrowViewport: () => narrow.value }));
vi.mock("./EvidenceViewerPanel", () => ({ EvidenceViewerPanel: () => <div data-testid="source-panel">source</div> }));
vi.mock("./EvidenceInspectorPanel", () => ({ EvidenceInspectorPanel: () => <div data-testid="entities-panel">entities</div> }));
vi.mock("@/components/ui/resizable", () => ({
  ResizablePanelGroup: ({ children }: { children: React.ReactNode }) => <div data-testid="desktop-split">{children}</div>,
  ResizablePanel: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  ResizableHandle: () => <div data-testid="split-handle" />,
}));

import { EvidenceWorkspace } from "./EvidenceWorkspace";

const props = {
  splitView: true,
  selectedDocument: null,
  selectedDocumentId: "d1",
  highlights: [],
  activeHighlightId: null,
  activePanelTab: "entities",
  entities: [],
  entitiesLoading: false,
  entitiesError: null,
  alertsState: [],
  alertsLoading: false,
  alertsError: null,
  activeEntityId: null,
  highlightSearchQuery: "",
  filteredHighlightResults: [],
  relationshipViewMode: "graph",
  relationshipGraph: { entityNodes: [], alertNodes: [], linkedAlertCount: 0 },
  relationshipExplanation: null,
  evidenceTimeline: [],
  reviewerIdentityReady: true,
  onHighlightClick: vi.fn(),
  onActivePanelTabChange: vi.fn(),
  onApproveEntity: vi.fn(),
  onRejectEntity: vi.fn(),
  onEntityClick: vi.fn(),
  onSearchQueryChange: vi.fn(),
  onSelectPanelItem: vi.fn(),
  onRelationshipViewModeChange: vi.fn(),
  onReviewAlert: vi.fn(),
  onResolveAlert: vi.fn(),
} as unknown as React.ComponentProps<typeof EvidenceWorkspace>;

describe("EvidenceWorkspace layout", () => {
  beforeEach(() => {
    narrow.value = false;
  });

  it("keeps the resizable source|entities split on desktop", () => {
    render(<EvidenceWorkspace {...props} />);
    expect(screen.getByTestId("desktop-split")).toBeInTheDocument();
    expect(screen.getByTestId("source-panel")).toBeInTheDocument();
    expect(screen.getByTestId("entities-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("evidence-mobile-workspace")).not.toBeInTheDocument();
  });

  it("on a phone shows one full-width column at a time through Source / Entities tabs, with no draggable split", async () => {
    narrow.value = true;
    render(<EvidenceWorkspace {...props} />);
    expect(screen.queryByTestId("desktop-split")).not.toBeInTheDocument();
    expect(screen.queryByTestId("split-handle")).not.toBeInTheDocument();
    expect(screen.getByTestId("evidence-mobile-workspace")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-tab-source")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-tab-entities")).toBeInTheDocument();
    expect(screen.getByTestId("source-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("entities-panel")).not.toBeInTheDocument();
  });
});
