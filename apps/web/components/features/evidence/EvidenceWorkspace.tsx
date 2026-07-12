import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import type { ExtractedEntity } from "@/components/evidence";
import type { PdfHighlight } from "@/components/features/evidence/PdfEvidenceViewer";
import type { DocumentInfo } from "@/types/document";
import type { Alert as ProjectAlert } from "@/types/project";
import { EvidenceInspectorPanel } from "./EvidenceInspectorPanel";
import { EvidenceViewerPanel } from "./EvidenceViewerPanel";
import type { EvidencePanelTab } from "./evidence-page-utils";

interface EvidenceWorkspaceProps {
  splitView: boolean;
  selectedDocument: DocumentInfo | null;
  selectedDocumentId: string | null;
  highlights: PdfHighlight[];
  activeHighlightId: string | null;
  activePanelTab: EvidencePanelTab;
  entities: ExtractedEntity[];
  entitiesLoading: boolean;
  entitiesError: Error | null;
  alertsState: ProjectAlert[];
  alertsLoading: boolean;
  alertsError: Error | null;
  activeEntityId: string | null;
  highlightSearchQuery: string;
  filteredHighlightResults: PdfHighlight[];
  relationshipViewMode: "graph" | "3d";
  relationshipGraph: {
    entityNodes: Array<{ id: string; label: string; page: number }>;
    alertNodes: Array<{ id: string; label: string; severity: ProjectAlert["severity"] }>;
    linkedAlertCount: number;
  };
  relationshipExplanation: {
    summary: string;
    strongestCluster: string;
    reviewPriority: string;
    latestSignal: string;
    citations: Array<{
      clauseId: string;
      clauseCode: string;
      label: string;
      page?: number | null;
      reason: string;
    }>;
  } | null;
  evidenceTimeline: Array<{
    id: string;
    title: string;
    occurredAt: string;
    detail: string;
  }>;
  reviewerIdentityReady: boolean;
  onHighlightClick: (id: string) => void;
  onActivePanelTabChange: (tab: EvidencePanelTab) => void;
  onApproveEntity: (entityId: string) => void;
  onRejectEntity: (entityId: string, reason: string) => void;
  onEntityClick: (entity: ExtractedEntity) => void;
  onSearchQueryChange: (value: string) => void;
  onSelectPanelItem: (id: string) => void;
  onRelationshipViewModeChange: (mode: "graph" | "3d") => void;
  onReviewAlert: (alertId: string, decision: "approve" | "reject") => void;
  onResolveAlert: (alertId: string) => void;
}

export function EvidenceWorkspace({
  splitView,
  selectedDocument,
  selectedDocumentId,
  highlights,
  activeHighlightId,
  activePanelTab,
  entities,
  entitiesLoading,
  entitiesError,
  alertsState,
  alertsLoading,
  alertsError,
  activeEntityId,
  highlightSearchQuery,
  filteredHighlightResults,
  relationshipViewMode,
  relationshipGraph,
  relationshipExplanation,
  evidenceTimeline,
  reviewerIdentityReady,
  onHighlightClick,
  onActivePanelTabChange,
  onApproveEntity,
  onRejectEntity,
  onEntityClick,
  onSearchQueryChange,
  onSelectPanelItem,
  onRelationshipViewModeChange,
  onReviewAlert,
  onResolveAlert,
}: EvidenceWorkspaceProps) {
  return (
    <ResizablePanelGroup
      direction="horizontal"
      className="min-h-[calc(100vh-12rem)]"
    >
      <ResizablePanel defaultSize={splitView ? 50 : 70} minSize={30}>
        <EvidenceViewerPanel
          selectedDocument={selectedDocument}
          selectedDocumentId={selectedDocumentId}
          highlights={highlights}
          activeHighlightId={activeHighlightId}
          onHighlightClick={onHighlightClick}
        />
      </ResizablePanel>

      <ResizableHandle withHandle />

      <ResizablePanel defaultSize={splitView ? 50 : 30} minSize={20}>
        <EvidenceInspectorPanel
          activePanelTab={activePanelTab}
          onActivePanelTabChange={onActivePanelTabChange}
          entities={entities}
          entitiesLoading={entitiesLoading}
          entitiesError={entitiesError}
          alertsState={alertsState}
          alertsLoading={alertsLoading}
          alertsError={alertsError}
          activeEntityId={activeEntityId}
          activeHighlightId={activeHighlightId}
          highlightSearchQuery={highlightSearchQuery}
          filteredHighlightResults={filteredHighlightResults}
          relationshipViewMode={relationshipViewMode}
          relationshipGraph={relationshipGraph}
          relationshipExplanation={relationshipExplanation}
          evidenceTimeline={evidenceTimeline}
          reviewerIdentityReady={reviewerIdentityReady}
          onApproveEntity={onApproveEntity}
          onRejectEntity={onRejectEntity}
          onEntityClick={onEntityClick}
          onSearchQueryChange={onSearchQueryChange}
          onSelectPanelItem={onSelectPanelItem}
          onRelationshipViewModeChange={onRelationshipViewModeChange}
          onReviewAlert={onReviewAlert}
          onResolveAlert={onResolveAlert}
        />
      </ResizablePanel>
    </ResizablePanelGroup>
  );
}
