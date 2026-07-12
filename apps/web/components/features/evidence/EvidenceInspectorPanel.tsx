import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EntityValidationList, type ExtractedEntity } from "@/components/evidence";
import type { PdfHighlight } from "@/components/features/evidence/PdfEvidenceViewer";
import { cn } from "@/lib/utils";
import type { Alert as ProjectAlert } from "@/types/project";
import {
  formatEvidenceTimelineDate,
  type EvidencePanelTab,
} from "./evidence-page-utils";

interface RelationshipGraph {
  entityNodes: Array<{ id: string; label: string; page: number }>;
  alertNodes: Array<{ id: string; label: string; severity: ProjectAlert["severity"] }>;
  linkedAlertCount: number;
}

interface RelationshipExplanation {
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
}

interface EvidenceTimelineEvent {
  id: string;
  title: string;
  occurredAt: string;
  detail: string;
}

interface EvidenceInspectorPanelProps {
  activePanelTab: EvidencePanelTab;
  onActivePanelTabChange: (tab: EvidencePanelTab) => void;
  entities: ExtractedEntity[];
  entitiesLoading: boolean;
  entitiesError: Error | null;
  alertsState: ProjectAlert[];
  alertsLoading: boolean;
  alertsError: Error | null;
  activeEntityId: string | null;
  activeHighlightId: string | null;
  highlightSearchQuery: string;
  filteredHighlightResults: PdfHighlight[];
  relationshipViewMode: "graph" | "3d";
  relationshipGraph: RelationshipGraph;
  relationshipExplanation: RelationshipExplanation | null;
  evidenceTimeline: EvidenceTimelineEvent[];
  reviewerIdentityReady: boolean;
  onApproveEntity: (entityId: string) => void;
  onRejectEntity: (entityId: string, reason: string) => void;
  onEntityClick: (entity: ExtractedEntity) => void;
  onSearchQueryChange: (value: string) => void;
  onSelectPanelItem: (id: string) => void;
  onRelationshipViewModeChange: (mode: "graph" | "3d") => void;
  onReviewAlert: (alertId: string, decision: "approve" | "reject") => void;
  onResolveAlert: (alertId: string) => void;
}

export function EvidenceInspectorPanel({
  activePanelTab,
  onActivePanelTabChange,
  entities,
  entitiesLoading,
  entitiesError,
  alertsState,
  alertsLoading,
  alertsError,
  activeEntityId,
  activeHighlightId,
  highlightSearchQuery,
  filteredHighlightResults,
  relationshipViewMode,
  relationshipGraph,
  relationshipExplanation,
  evidenceTimeline,
  reviewerIdentityReady,
  onApproveEntity,
  onRejectEntity,
  onEntityClick,
  onSearchQueryChange,
  onSelectPanelItem,
  onRelationshipViewModeChange,
  onReviewAlert,
  onResolveAlert,
}: EvidenceInspectorPanelProps) {
  return (
    <Card className="h-full rounded-2xl border-border/80 bg-card/85 shadow-sm">
      <CardHeader className="border-b border-border/70">
        <CardTitle>Extracted Entities</CardTitle>
      </CardHeader>
      <CardContent className="p-5">
        <Tabs
          value={activePanelTab}
          onValueChange={(value) => onActivePanelTabChange(value as EvidencePanelTab)}
          className="w-full"
        >
          <TabsList className="grid w-full grid-cols-3 rounded-2xl border border-border/80 bg-muted/35 p-1 shadow-sm">
            <TabsTrigger value="entities" className="rounded-xl">Entities</TabsTrigger>
            <TabsTrigger value="alerts" className="rounded-xl">Alerts</TabsTrigger>
            <TabsTrigger value="search" className="rounded-xl">Search</TabsTrigger>
          </TabsList>

          <TabsContent value="entities" className="space-y-4">
            {entitiesError ? (
              <Alert>
                <AlertTriangle className="h-4 w-4" />
                <AlertDescription>
                  Failed to load entities: {entitiesError.message}
                </AlertDescription>
              </Alert>
            ) : (
              <EntityValidationList
                entities={entities}
                onApprove={onApproveEntity}
                onReject={onRejectEntity}
                onEntityClick={onEntityClick}
                activeEntityId={activeEntityId}
                isLoading={entitiesLoading}
              />
            )}
          </TabsContent>

          <TabsContent value="alerts" className="space-y-4">
            <AlertList
              alertsState={alertsState}
              alertsLoading={alertsLoading}
              alertsError={alertsError}
              activeEntityId={activeEntityId}
              reviewerIdentityReady={reviewerIdentityReady}
              onSelectPanelItem={onSelectPanelItem}
              onReviewAlert={onReviewAlert}
              onResolveAlert={onResolveAlert}
            />
          </TabsContent>

          <TabsContent value="search" className="space-y-4">
            <Input
              aria-label="Search highlights"
              placeholder="Search highlights in this document..."
              value={highlightSearchQuery}
              onChange={(event) => onSearchQueryChange(event.target.value)}
              className="rounded-xl border-border/80 bg-background/95 shadow-sm"
            />
            <p className="text-sm text-muted-foreground">
              {filteredHighlightResults.length} matches
            </p>
            {filteredHighlightResults.length === 0 ? (
              <Alert>
                <AlertDescription>
                  No highlights match the current search.
                </AlertDescription>
              </Alert>
            ) : (
              <div className="space-y-2">
                {filteredHighlightResults.map((highlight) => (
                  <button
                    key={highlight.id}
                    type="button"
                    className={cn(
                      "w-full rounded-2xl border bg-background/90 p-4 text-left shadow-sm transition-colors",
                      activeHighlightId === highlight.id
                        ? "border-primary bg-primary/5"
                        : "border-border hover:border-primary/50",
                    )}
                    onClick={() => onSelectPanelItem(highlight.clauseId)}
                  >
                    <p className="font-medium">{highlight.text}</p>
                    <p className="text-xs text-muted-foreground">
                      {highlight.clauseId} - page {highlight.page}
                    </p>
                  </button>
                ))}
              </div>
            )}
          </TabsContent>
        </Tabs>

        <RelationshipSection
          relationshipViewMode={relationshipViewMode}
          relationshipGraph={relationshipGraph}
          activeEntityId={activeEntityId}
          onRelationshipViewModeChange={onRelationshipViewModeChange}
          onSelectPanelItem={onSelectPanelItem}
        />
        <RelationshipExplanationPanel relationshipExplanation={relationshipExplanation} />
        <EvidenceTimelinePanel evidenceTimeline={evidenceTimeline} />
      </CardContent>
    </Card>
  );
}

function AlertList({
  alertsState,
  alertsLoading,
  alertsError,
  activeEntityId,
  reviewerIdentityReady,
  onSelectPanelItem,
  onReviewAlert,
  onResolveAlert,
}: Pick<
  EvidenceInspectorPanelProps,
  | "alertsState"
  | "alertsLoading"
  | "alertsError"
  | "activeEntityId"
  | "reviewerIdentityReady"
  | "onSelectPanelItem"
  | "onReviewAlert"
  | "onResolveAlert"
>) {
  if (alertsError) {
    return (
      <Alert>
        <AlertDescription>
          Failed to load alerts: {alertsError.message}
        </AlertDescription>
      </Alert>
    );
  }

  if (alertsLoading) {
    return (
      <Alert>
        <AlertDescription>Loading alerts...</AlertDescription>
      </Alert>
    );
  }

  if (alertsState.length === 0) {
    return (
      <Alert>
        <AlertDescription>No alerts for this document.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-2">
      {alertsState.map((alert) => (
        <div
          key={alert.id}
          className={cn(
            "rounded-2xl border bg-background/90 p-4 shadow-sm transition-colors",
            activeEntityId === alert.id
              ? "border-primary bg-primary/5"
              : "border-border",
          )}
        >
          <button
            type="button"
            className="w-full text-left"
            aria-pressed={activeEntityId === alert.id}
            aria-label={`Focus alert ${alert.title}`}
            onClick={() => onSelectPanelItem(alert.id)}
          >
            <p className="font-medium">{alert.title}</p>
            <p className="text-sm text-muted-foreground">
              {alert.description}
            </p>
          </button>
          <div className="mt-3 flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="rounded-xl bg-background/95 shadow-sm"
              disabled={!reviewerIdentityReady}
              title={!reviewerIdentityReady ? "Loading your identity…" : undefined}
              onClick={() => onReviewAlert(alert.id, "approve")}
            >
              Approve Alert
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="rounded-xl bg-background/95 shadow-sm"
              disabled={!reviewerIdentityReady}
              title={!reviewerIdentityReady ? "Loading your identity…" : undefined}
              onClick={() => onReviewAlert(alert.id, "reject")}
            >
              Reject Alert
            </Button>
            <Button
              size="sm"
              className="rounded-xl shadow-sm"
              disabled={!reviewerIdentityReady}
              title={!reviewerIdentityReady ? "Loading your identity…" : undefined}
              onClick={() => onResolveAlert(alert.id)}
            >
              Resolve Alert
            </Button>
          </div>
        </div>
      ))}
    </div>
  );
}

function RelationshipSection({
  relationshipViewMode,
  relationshipGraph,
  activeEntityId,
  onRelationshipViewModeChange,
  onSelectPanelItem,
}: Pick<
  EvidenceInspectorPanelProps,
  | "relationshipViewMode"
  | "relationshipGraph"
  | "activeEntityId"
  | "onRelationshipViewModeChange"
  | "onSelectPanelItem"
>) {
  return (
    <div className="mt-6 rounded-2xl border border-border/80 bg-muted/25 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            {relationshipViewMode === "3d" ? "3D Relationship Viewer" : "Relationship Graph"}
          </h3>
          <p className="text-xs text-muted-foreground">
            {relationshipViewMode === "3d"
              ? "Depth layers"
              : `${relationshipGraph.linkedAlertCount} linked alert${
                  relationshipGraph.linkedAlertCount === 1 ? "" : "s"
                }`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant={relationshipViewMode === "graph" ? "default" : "outline"}
            className={cn("rounded-xl shadow-sm", relationshipViewMode === "graph" ? "" : "bg-background/95")}
            onClick={() => onRelationshipViewModeChange("graph")}
          >
            Graph View
          </Button>
          <Button
            type="button"
            size="sm"
            variant={relationshipViewMode === "3d" ? "default" : "outline"}
            className={cn("rounded-xl shadow-sm", relationshipViewMode === "3d" ? "" : "bg-background/95")}
            onClick={() => onRelationshipViewModeChange("3d")}
          >
            3D Relationship View
          </Button>
          <Badge variant="outline" className="rounded-full bg-background/90 px-3 py-1 shadow-sm">
            {relationshipGraph.entityNodes.length} entities /{" "}
            {relationshipGraph.alertNodes.length} alerts
          </Badge>
        </div>
      </div>
      {relationshipViewMode === "3d" ? (
        <Relationship3DGraph
          relationshipGraph={relationshipGraph}
          activeEntityId={activeEntityId}
          onSelectPanelItem={onSelectPanelItem}
        />
      ) : (
        <RelationshipGraphView
          relationshipGraph={relationshipGraph}
          activeEntityId={activeEntityId}
          onSelectPanelItem={onSelectPanelItem}
        />
      )}
    </div>
  );
}

function Relationship3DGraph({
  relationshipGraph,
  activeEntityId,
  onSelectPanelItem,
}: Pick<EvidenceInspectorPanelProps, "relationshipGraph" | "activeEntityId" | "onSelectPanelItem">) {
  return (
    <div className="mt-4 space-y-4">
      <div className="grid gap-4 lg:grid-cols-3" style={{ perspective: "1200px" }}>
        <GraphNodeColumn
          title="Layer 1 · Entities"
          nodes={relationshipGraph.entityNodes.map((node) => ({
            ...node,
            meta: `Entity · page ${node.page}`,
          }))}
          activeEntityId={activeEntityId}
          onSelectPanelItem={onSelectPanelItem}
          style={{ transform: "rotateY(18deg) translateZ(24px)" }}
        />
        <div
          className="rounded-2xl border border-dashed border-border/80 bg-background/80 p-4 shadow-sm"
          style={{ transform: "translateZ(48px)" }}
        >
          <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Layer 2 · Relationship Depth
          </p>
          <div className="space-y-2 text-sm text-muted-foreground">
            <p>Contract entities project forward into active alerts.</p>
            <p>Click any node to focus the linked highlight in the evidence viewer.</p>
          </div>
        </div>
        <GraphNodeColumn
          title="Layer 3 · Alerts"
          nodes={relationshipGraph.alertNodes.map((node) => ({
            ...node,
            meta: `Alert · ${String(node.severity).toLowerCase()}`,
          }))}
          activeEntityId={activeEntityId}
          onSelectPanelItem={onSelectPanelItem}
          style={{ transform: "rotateY(-18deg) translateZ(24px)" }}
        />
      </div>
    </div>
  );
}

function RelationshipGraphView({
  relationshipGraph,
  activeEntityId,
  onSelectPanelItem,
}: Pick<EvidenceInspectorPanelProps, "relationshipGraph" | "activeEntityId" | "onSelectPanelItem">) {
  return (
    <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto_1fr] lg:items-start">
      <GraphNodeList
        nodes={relationshipGraph.entityNodes.map((node) => ({
          ...node,
          meta: `Entity · page ${node.page}`,
        }))}
        activeEntityId={activeEntityId}
        onSelectPanelItem={onSelectPanelItem}
      />
      <div className="hidden items-center justify-center lg:flex">
        <div className="h-full min-h-[120px] w-px bg-border" />
      </div>
      <GraphNodeList
        nodes={relationshipGraph.alertNodes.map((node) => ({
          ...node,
          meta: `Alert · ${String(node.severity).toLowerCase()}`,
        }))}
        activeEntityId={activeEntityId}
        onSelectPanelItem={onSelectPanelItem}
      />
    </div>
  );
}

function GraphNodeColumn({
  title,
  nodes,
  activeEntityId,
  onSelectPanelItem,
  style,
}: {
  title: string;
  nodes: Array<{ id: string; label: string; meta: string }>;
  activeEntityId: string | null;
  onSelectPanelItem: (id: string) => void;
  style?: React.CSSProperties;
}) {
  return (
    <div className="rounded-2xl border border-border/80 bg-background/95 p-4 shadow-sm" style={style}>
      <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </p>
      <GraphNodeList
        nodes={nodes}
        activeEntityId={activeEntityId}
        onSelectPanelItem={onSelectPanelItem}
      />
    </div>
  );
}

function GraphNodeList({
  nodes,
  activeEntityId,
  onSelectPanelItem,
}: {
  nodes: Array<{ id: string; label: string; meta: string }>;
  activeEntityId: string | null;
  onSelectPanelItem: (id: string) => void;
}) {
  return (
    <div className="space-y-2">
      {nodes.map((node) => (
        <button
          key={node.id}
          type="button"
          aria-label={`Graph node ${node.id}`}
          className={cn(
            "w-full rounded-xl border bg-background px-3 py-2 text-left shadow-sm transition-colors",
            activeEntityId === node.id
              ? "border-primary bg-primary/5"
              : "border-border hover:border-primary/50",
          )}
          onClick={() => onSelectPanelItem(node.id)}
        >
          <div className="text-sm font-medium text-foreground">{node.label}</div>
          <div className="text-xs text-muted-foreground">{node.meta}</div>
        </button>
      ))}
    </div>
  );
}

function RelationshipExplanationPanel({
  relationshipExplanation,
}: {
  relationshipExplanation: RelationshipExplanation | null;
}) {
  return (
    <div className="mt-6 rounded-2xl border border-border/80 bg-muted/25 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            AI Relationship Explanation
          </h3>
          <p className="text-xs text-muted-foreground">
            Backend-generated explanation grounded in evidence graph citations
          </p>
        </div>
        <Badge variant="outline" className="rounded-full bg-background/90 px-3 py-1 shadow-sm">
          Model-backed
        </Badge>
      </div>

      <div className="mt-4 space-y-3">
        {relationshipExplanation ? (
          <>
            <p className="text-sm text-foreground">{relationshipExplanation.summary}</p>
            <div className="grid gap-3 md:grid-cols-3">
              <ExplanationMetric label="Strongest Cluster" value={relationshipExplanation.strongestCluster} />
              <ExplanationMetric label="Review Priority" value={relationshipExplanation.reviewPriority} />
              <ExplanationMetric label="Latest Signal" value={relationshipExplanation.latestSignal} />
            </div>
            <div className="rounded-2xl border border-border/80 bg-background/95 p-3 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Evidence Citations
              </p>
              <div className="mt-3 space-y-2">
                {relationshipExplanation.citations.map((citation) => (
                  <div
                    key={`${citation.clauseId}-${citation.clauseCode}`}
                    className="rounded-xl border border-border/70 bg-muted/25 p-2 shadow-sm"
                  >
                    <p className="text-sm font-medium text-foreground">
                      {citation.clauseCode} · {citation.label}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {citation.page ? `Page ${citation.page}` : "Page N/A"} · {citation.reason}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </>
        ) : (
          <Alert>
            <AlertDescription>
              No relationship explanation is available until entities or alerts are present.
            </AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  );
}

function ExplanationMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-border/80 bg-background/95 p-3 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <p className="mt-2 text-sm text-foreground">{value}</p>
    </div>
  );
}

function EvidenceTimelinePanel({
  evidenceTimeline,
}: {
  evidenceTimeline: EvidenceTimelineEvent[];
}) {
  return (
    <div className="mt-6 rounded-2xl border border-border/80 bg-muted/25 p-5 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-foreground">
            Evidence Evolution Timeline
          </h3>
          <p className="text-xs text-muted-foreground">
            Persisted document lifecycle and alert history events
          </p>
        </div>
        <Badge variant="outline" className="rounded-full bg-background/90 px-3 py-1 shadow-sm">
          {evidenceTimeline.length} events
        </Badge>
      </div>

      <div className="mt-4 space-y-3">
        {evidenceTimeline.length > 0 ? (
          evidenceTimeline.map((event) => (
            <div
              key={event.id}
              className="flex items-start gap-3 rounded-2xl border border-border/80 bg-background/95 p-3 shadow-sm"
            >
              <div className="mt-1 h-2.5 w-2.5 rounded-full bg-primary" />
              <div className="min-w-0">
                <p className="font-medium text-sm">{event.title}</p>
                <p className="text-xs text-muted-foreground">
                  {formatEvidenceTimelineDate(event.occurredAt)}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">{event.detail}</p>
              </div>
            </div>
          ))
        ) : (
          <Alert>
            <AlertDescription>
              No evidence history is available for the current document.
            </AlertDescription>
          </Alert>
        )}
      </div>
    </div>
  );
}
