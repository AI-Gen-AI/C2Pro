"use client";

import { use, useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  AlertTriangle,
  CheckCircle,
  ChevronDown,
  Clock,
  Columns2,
  Database,
  Download,
  FileJson,
  FileText,
  RefreshCw,
} from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EntityValidationList, ExtractedEntity } from "@/components/evidence";
import {
  PdfEvidenceViewer,
  PdfHighlight,
} from "@/components/features/evidence/PdfEvidenceViewer";
import { useDocumentAlerts } from "@/hooks/useDocumentAlerts";
import { useDocumentEntities } from "@/hooks/useDocumentEntities";
import { useProjectDocuments } from "@/hooks/useProjectDocuments";
import {
  createHighlightsFromAlerts,
  getDocumentDownloadUrl,
  resolveAlert,
  reviewAlert,
  reviewApprovalResource,
} from "@/lib/api";
import { cn } from "@/lib/utils";

interface EvidencePageProps {
  params: Promise<{
    id: string;
  }>;
}

function normalizeConfidence(value: number): number {
  if (value <= 1) {
    return Math.round(value * 100);
  }
  return Math.round(value);
}

function normalizeEntityType(value: string): string {
  if (!value) {
    return "Entity";
  }
  return value.charAt(0).toUpperCase() + value.slice(1);
}

export default function EvidencePage({ params }: EvidencePageProps) {
  const { id } = use(params);
  const searchParams = useSearchParams();
  const requestedDocumentId = searchParams.get("documentId");

  const [splitView, setSplitView] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    null,
  );
  const [activeEntityId, setActiveEntityId] = useState<string | null>(null);
  const [highlightSearchQuery, setHighlightSearchQuery] = useState("");

  const {
    documents,
    loading: documentsLoading,
    error: documentsError,
    refetch: refetchDocuments,
  } = useProjectDocuments(id);

  useEffect(() => {
    if (documents.length === 0) {
      setSelectedDocumentId(null);
      return;
    }

    if (
      requestedDocumentId &&
      documents.some((doc) => doc.id === requestedDocumentId)
    ) {
      setSelectedDocumentId(requestedDocumentId);
      return;
    }

    if (
      !selectedDocumentId ||
      !documents.some((doc) => doc.id === selectedDocumentId)
    ) {
      setSelectedDocumentId(documents[0]?.id ?? null);
    }
  }, [documents, requestedDocumentId, selectedDocumentId]);

  const selectedDocument = useMemo(
    () => documents.find((doc) => doc.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
  );

  const {
    entities: apiEntities,
    highlights: entityHighlights,
    loading: entitiesLoading,
    error: entitiesError,
    refetch: refetchEntities,
  } = useDocumentEntities(selectedDocumentId);
  const {
    alerts,
    loading: alertsLoading,
    error: alertsError,
    refetch: refetchAlerts,
  } = useDocumentAlerts(selectedDocumentId);
  const [alertsState, setAlertsState] = useState(alerts);
  const [actionError, setActionError] = useState<string | null>(null);

  const highlights = useMemo<PdfHighlight[]>(() => {
    const mappedEntityHighlights: PdfHighlight[] = entityHighlights.map(
      (highlight) => {
        const entity = apiEntities.find(
          (item) => item.id === highlight.entityId,
        );

        return {
          id: highlight.id,
          clauseId: highlight.entityId,
          page: highlight.page,
          text: highlight.label ?? entity?.text ?? highlight.entityId,
          severity: mapHighlightColorToSeverity(highlight.color),
        };
      },
    );

    const alertHighlights: PdfHighlight[] = createHighlightsFromAlerts(
      alertsState,
    ).map((highlight) => {
      const alert = alertsState.find((item) => item.id === highlight.entityId);

      return {
        id: highlight.id,
        clauseId: highlight.entityId,
        page: highlight.page,
        text: highlight.label ?? alert?.title ?? highlight.entityId,
        severity: mapHighlightColorToSeverity(highlight.color),
      };
    });

    return [...mappedEntityHighlights, ...alertHighlights];
  }, [apiEntities, entityHighlights, alertsState]);

  const activeHighlightId = useMemo(() => {
    if (!activeEntityId) {
      return null;
    }

    const entityHighlight = highlights.find(
      (highlight) => highlight.clauseId === activeEntityId,
    );

    return entityHighlight?.id ?? activeEntityId;
  }, [activeEntityId, highlights]);

  const filteredHighlightResults = useMemo(() => {
    const query = highlightSearchQuery.trim().toLowerCase();
    if (!query) {
      return highlights;
    }

    return highlights.filter((highlight) => {
      return (
        highlight.text.toLowerCase().includes(query) ||
        highlight.clauseId.toLowerCase().includes(query) ||
        highlight.id.toLowerCase().includes(query)
      );
    });
  }, [highlightSearchQuery, highlights]);

  const mappedEntities = useMemo<ExtractedEntity[]>(
    () =>
      apiEntities.map((entity) => ({
        id: entity.id,
        type: normalizeEntityType(entity.type),
        text: entity.text,
        approvalResourceType: mapEntityTypeToApprovalResourceType(entity.type),
        confidence: normalizeConfidence(entity.confidence),
        page: entity.page,
        validationStatus: "pending",
      })),
    [apiEntities],
  );

  const [entities, setEntities] = useState<ExtractedEntity[]>([]);

  useEffect(() => {
    setEntities(mappedEntities);
  }, [mappedEntities]);

  useEffect(() => {
    setAlertsState(alerts);
  }, [alerts]);

  const handleApproveEntity = useCallback(
    async (entityId: string) => {
      const entity = entities.find((item) => item.id === entityId);
      if (!entity) {
        return;
      }

      if (!entity.approvalResourceType) {
        setActionError(
          `No backend approval endpoint is available for ${entity.type.toLowerCase()} entities yet.`,
        );
        return;
      }

      setActionError(null);
      await reviewApprovalResource(
        entity.approvalResourceType,
        entityId,
        "APPROVED",
      );

      setEntities((prev) =>
        prev.map((item) =>
          item.id === entityId
            ? { ...item, validationStatus: "approved", validated: true }
            : item,
        ),
      );
    },
    [entities],
  );

  const handleRejectEntity = useCallback(
    async (entityId: string, reason: string) => {
      const entity = entities.find((item) => item.id === entityId);
      if (!entity) {
        return;
      }

      if (!entity.approvalResourceType) {
        setActionError(
          `No backend approval endpoint is available for ${entity.type.toLowerCase()} entities yet.`,
        );
        return;
      }

      setActionError(null);
      await reviewApprovalResource(
        entity.approvalResourceType,
        entityId,
        "REJECTED",
        { feedbackComment: reason },
      );

      setEntities((prev) =>
        prev.map((item) =>
          item.id === entityId
            ? {
                ...item,
                validationStatus: "rejected",
                validated: false,
                rejectionReason: reason,
              }
            : item,
        ),
      );
    },
    [entities],
  );

  const handleEntityClick = useCallback((entity: ExtractedEntity) => {
    setActiveEntityId(entity.id);
  }, []);

  const handleHighlightClick = useCallback((id: string) => {
    setActiveEntityId(id);
  }, []);

  const handleRefresh = useCallback(async () => {
    await Promise.all([refetchDocuments(), refetchEntities(), refetchAlerts()]);
  }, [refetchDocuments, refetchEntities, refetchAlerts]);

  const handleReviewAlert = useCallback(
    async (alertId: string, decision: "approve" | "reject") => {
      setActionError(null);
      const updatedAlert = await reviewAlert(alertId, decision);
      setAlertsState((prev) =>
        prev.map((alert) => (alert.id === alertId ? updatedAlert : alert)),
      );
    },
    [],
  );

  const handleResolveAlert = useCallback(async (alertId: string) => {
    setActionError(null);
    const updatedAlert = await resolveAlert(
      alertId,
      "Resolved from evidence viewer",
      "web-evidence-viewer",
    );
    setAlertsState((prev) =>
      prev.map((alert) => (alert.id === alertId ? updatedAlert : alert)),
    );
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Evidence Viewer</h1>
          <p className="text-muted-foreground">Project: {id}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => void handleRefresh()}
          >
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                <Download className="mr-2 h-4 w-4" />
                Export
                <ChevronDown className="ml-2 h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuItem>
                <FileJson className="mr-2 h-4 w-4" />
                Export JSON
              </DropdownMenuItem>
              <DropdownMenuItem>
                <Database className="mr-2 h-4 w-4" />
                Export CSV
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant={splitView ? "default" : "outline"}
            size="sm"
            onClick={() => setSplitView((value) => !value)}
          >
            <Columns2 className="mr-2 h-4 w-4" />
            Split View
          </Button>
        </div>
      </div>

      {documentsError ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
          Failed to load documents: {documentsError.message}
        </div>
      ) : null}

      {actionError ? (
        <Alert variant="destructive">
          <AlertDescription>{actionError}</AlertDescription>
        </Alert>
      ) : null}

      <ResizablePanelGroup
        direction="horizontal"
        className="min-h-[calc(100vh-12rem)]"
      >
        <ResizablePanel defaultSize={splitView ? 50 : 70} minSize={30}>
          <Card className="h-full">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="flex items-center gap-2">
                  <FileText className="h-5 w-5" />
                  {selectedDocument?.name ?? "No document selected"}
                </CardTitle>
                {selectedDocument ? (
                  <Badge variant="outline">{selectedDocument.type}</Badge>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {selectedDocumentId ? (
                <PdfEvidenceViewer
                  fileUrl={getDocumentDownloadUrl(selectedDocumentId)}
                  highlights={highlights}
                  activeHighlightId={activeHighlightId}
                  onHighlightClick={handleHighlightClick}
                />
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-4 rounded-lg border-2 border-dashed border-border bg-muted/20 p-8">
                  <FileText className="h-16 w-16 text-muted-foreground" />
                  <div className="text-center">
                    <h3 className="text-lg font-semibold">
                      No Document Selected
                    </h3>
                    <p className="mt-2 text-sm text-muted-foreground">
                      Select a document from the list below to view evidence.
                    </p>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </ResizablePanel>

        <ResizableHandle withHandle />

        <ResizablePanel defaultSize={splitView ? 50 : 30} minSize={20}>
          <Card className="h-full">
            <CardHeader>
              <CardTitle>Extracted Entities</CardTitle>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="entities" className="w-full">
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger value="entities">Entities</TabsTrigger>
                  <TabsTrigger value="alerts">Alerts</TabsTrigger>
                  <TabsTrigger value="search">Search</TabsTrigger>
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
                      onApprove={handleApproveEntity}
                      onReject={handleRejectEntity}
                      onEntityClick={handleEntityClick}
                      activeEntityId={activeEntityId}
                      isLoading={entitiesLoading}
                    />
                  )}
                </TabsContent>

                <TabsContent value="alerts" className="space-y-4">
                  {alertsError ? (
                    <Alert>
                      <AlertDescription>
                        Failed to load alerts: {alertsError.message}
                      </AlertDescription>
                    </Alert>
                  ) : alertsLoading ? (
                    <Alert>
                      <AlertDescription>Loading alerts...</AlertDescription>
                    </Alert>
                  ) : alertsState.length === 0 ? (
                    <Alert>
                      <AlertDescription>
                        No alerts for this document.
                      </AlertDescription>
                    </Alert>
                  ) : (
                    <div className="space-y-2">
                      {alertsState.map((alert) => (
                        <div key={alert.id} className="rounded-md border p-3">
                          <p className="font-medium">{alert.title}</p>
                          <p className="text-sm text-muted-foreground">
                            {alert.description}
                          </p>
                          <div className="mt-3 flex gap-2">
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                void handleReviewAlert(alert.id, "approve")
                              }
                            >
                              Approve Alert
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                void handleReviewAlert(alert.id, "reject")
                              }
                            >
                              Reject Alert
                            </Button>
                            <Button
                              size="sm"
                              onClick={() => void handleResolveAlert(alert.id)}
                            >
                              Resolve Alert
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="search" className="space-y-4">
                  <Input
                    aria-label="Search highlights"
                    placeholder="Search highlights in this document..."
                    value={highlightSearchQuery}
                    onChange={(event) =>
                      setHighlightSearchQuery(event.target.value)
                    }
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
                            "w-full rounded-md border p-3 text-left transition-colors",
                            activeHighlightId === highlight.id
                              ? "border-primary bg-primary/5"
                              : "border-border hover:border-primary/50",
                          )}
                          onClick={() => setActiveEntityId(highlight.clauseId)}
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
            </CardContent>
          </Card>
        </ResizablePanel>
      </ResizablePanelGroup>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Clock className="h-5 w-5" />
            Project Documents
          </CardTitle>
        </CardHeader>
        <CardContent>
          {documentsLoading ? (
            <p className="text-sm text-muted-foreground">
              Loading documents...
            </p>
          ) : documents.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No documents available for this project.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              {documents.map((doc) => (
                <button
                  key={doc.id}
                  onClick={() => setSelectedDocumentId(doc.id)}
                  className={cn(
                    "flex items-center gap-3 rounded-lg border p-4 text-left transition-colors",
                    selectedDocumentId === doc.id
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50",
                  )}
                >
                  <FileText className="h-8 w-8 text-muted-foreground" />
                  <div className="flex-1">
                    <p className="font-medium text-sm">{doc.name}</p>
                    <p className="text-xs text-muted-foreground">{doc.id}</p>
                  </div>
                  {selectedDocumentId === doc.id ? (
                    <CheckCircle className="h-5 w-5 text-primary" />
                  ) : null}
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function mapHighlightColorToSeverity(color: string): PdfHighlight["severity"] {
  switch (color) {
    case "red":
      return "critical";
    case "orange":
      return "high";
    case "yellow":
      return "medium";
    case "green":
    case "blue":
    default:
      return "low";
  }
}

function mapEntityTypeToApprovalResourceType(
  entityType: string,
): string | null {
  switch (entityType) {
    case "stakeholder":
      return "stakeholders";
    default:
      return null;
  }
}
