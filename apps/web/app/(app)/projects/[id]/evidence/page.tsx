"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  PdfHighlight,
} from "@/components/features/evidence/PdfEvidenceViewer";
import { LazyPdfEvidenceViewer } from "@/components/features/evidence/LazyPdfEvidenceViewer";
import { env } from "@/config/env";
import { useDocumentAlerts } from "@/hooks/useDocumentAlerts";
import { useDocumentEntities } from "@/hooks/useDocumentEntities";
import { useDocumentHistory } from "@/hooks/useDocumentHistory";
import { useDocumentRelationshipExplanation } from "@/hooks/useDocumentRelationshipExplanation";
import { useProjectDocuments } from "@/hooks/useProjectDocuments";
import { useReviewResourceApiV1ApprovalsResourceTypeResourceIdPatch } from "@/lib/api/generated/approvals/approvals";
import {
  useResolveAlertApiV1AlertsAlertIdResolvePost,
  useReviewAlertApiV1AlertsAlertIdReviewPost,
} from "@/lib/api/generated/alerts/alerts";
import { cn } from "@/lib/utils";
import type { AlertResponse as BackendAlertResponse } from "@/types/backend";
import type { Alert as ProjectAlert } from "@/types/project";

type EvidenceTemplate = {
  id: string;
  name: string;
  summary: string;
  reviewFocus: string[];
  tags: string[];
};

type PendingEvidenceAction =
  | {
      kind: "entity-approve";
      entityId: string;
      label: string;
      confidence: number;
    }
  | {
      kind: "entity-reject";
      entityId: string;
      label: string;
      reason: string;
    }
  | {
      kind: "alert-review";
      alertId: string;
      label: string;
      decision: "approve" | "reject";
    };

const EVIDENCE_TEMPLATES: EvidenceTemplate[] = [
  {
    id: "claims-review",
    name: "Claims Review",
    summary: "Claims review focus",
    reviewFocus: [
      "Delay-event support",
      "Notice compliance",
      "Commercial exposure",
    ],
    tags: ["claims", "time-impact", "commercial"],
  },
  {
    id: "technical-audit",
    name: "Technical Audit",
    summary: "Technical audit focus",
    reviewFocus: [
      "Specification compliance",
      "Design-change evidence",
      "Quality deviation traceability",
    ],
    tags: ["technical", "quality", "design"],
  },
  {
    id: "executive-brief",
    name: "Executive Brief",
    summary: "Executive brief focus",
    reviewFocus: [
      "Critical findings only",
      "Decision-ready evidence",
      "Alert prioritization",
    ],
    tags: ["executive", "summary", "risk"],
  },
];

function sanitizeFilename(value: string): string {
  return value
    .trim()
    .replace(/[^a-z0-9_.-]+/gi, "_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "")
    .toLowerCase();
}

function escapeXml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&apos;");
}

function downloadBlob(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
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

function formatEvidenceTimelineDate(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  return parsed.toISOString().slice(0, 10);
}

export default function EvidencePage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const requestedDocumentId = searchParams.get("documentId");

  const [splitView, setSplitView] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    null,
  );
  const [activeEntityId, setActiveEntityId] = useState<string | null>(null);
  const [highlightSearchQuery, setHighlightSearchQuery] = useState("");
  const [isTemplateOpen, setIsTemplateOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>(
    EVIDENCE_TEMPLATES[0]?.id ?? "",
  );
  const [relationshipViewMode, setRelationshipViewMode] = useState<
    "graph" | "3d"
  >("graph");
  const [pendingAction, setPendingAction] =
    useState<PendingEvidenceAction | null>(null);
  const [validationNote, setValidationNote] = useState("");

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
  const {
    items: evidenceTimeline,
  } = useDocumentHistory(selectedDocumentId);
  const {
    explanation: relationshipExplanation,
  } = useDocumentRelationshipExplanation(selectedDocumentId);
  const [alertsState, setAlertsState] = useState(alerts);
  const [actionError, setActionError] = useState<string | null>(null);
  const reviewResource = useReviewResourceApiV1ApprovalsResourceTypeResourceIdPatch();
  const reviewProjectAlert = useReviewAlertApiV1AlertsAlertIdReviewPost();
  const resolveProjectAlert = useResolveAlertApiV1AlertsAlertIdResolvePost();

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

    const alertHighlights: PdfHighlight[] = alertsState.flatMap((alert) => {
      const evidence = extractAlertEvidenceLocation(alert);
      if (!evidence) {
        return [];
      }

      return [
        {
          id: `highlight-${alert.id}`,
          clauseId: alert.id,
          page: evidence.page_number,
          text: alert.title,
          severity: mapAlertSeverityToPdfSeverity(alert.severity),
        },
      ];
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
  const relationshipGraph = useMemo(() => {
    return {
      entityNodes: mappedEntities.map((entity) => ({
        id: entity.id,
        label: entity.text,
        page: entity.page,
      })),
      alertNodes: alertsState.map((alert) => ({
        id: alert.id,
        label: alert.title,
        severity: alert.severity,
      })),
      linkedAlertCount: alertsState.length,
    };
  }, [alertsState, mappedEntities]);
  const selectedTemplate =
    EVIDENCE_TEMPLATES.find((template) => template.id === selectedTemplateId) ??
    EVIDENCE_TEMPLATES[0];
  const [entities, setEntities] = useState<ExtractedEntity[]>([]);

  useEffect(() => {
    setEntities(mappedEntities);
  }, [mappedEntities]);

  useEffect(() => {
    setAlertsState(alerts);
  }, [alerts]);

  const handleApproveEntity = useCallback(
    async (entityId: string, note?: string) => {
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
      await reviewResource.mutateAsync({
        resourceType: entity.approvalResourceType,
        resourceId: entityId,
        data: {
          status: "APPROVED",
          correction_data: undefined,
          feedback_comment: note?.trim() || null,
        },
      });

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
      await reviewResource.mutateAsync({
        resourceType: entity.approvalResourceType,
        resourceId: entityId,
        data: {
          status: "REJECTED",
          correction_data: undefined,
          feedback_comment: reason,
        },
      });

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
      const updatedAlert = await reviewProjectAlert.mutateAsync({
        alertId,
        data: {
          decision,
          comment: "",
        },
      });
      setAlertsState((prev) =>
        prev.map((alert) =>
          alert.id === alertId
            ? (updatedAlert as unknown as BackendAlertResponse)
            : alert,
        ),
      );
    },
    [reviewProjectAlert],
  );

  const handleResolveAlert = useCallback(async (alertId: string) => {
    setActionError(null);
    const updatedAlert = await resolveProjectAlert.mutateAsync({
      alertId,
      data: {
        resolution: "Resolved from evidence viewer",
        resolved_by: "web-evidence-viewer",
        root_cause: "other",
      },
    });
    setAlertsState((prev) =>
      prev.map((alert) =>
        alert.id === alertId
          ? (updatedAlert as unknown as BackendAlertResponse)
          : alert,
      ),
    );
  }, [resolveProjectAlert]);

  const requestApproveEntity = useCallback(
    async (entityId: string) => {
      const entity = entities.find((item) => item.id === entityId);
      if (!entity) {
        return;
      }

      setPendingAction({
        kind: "entity-approve",
        entityId,
        label: entity.text,
        confidence: entity.confidence,
      });
    },
    [entities],
  );

  const requestRejectEntity = useCallback(
    async (entityId: string, reason: string) => {
      const entity = entities.find((item) => item.id === entityId);
      if (!entity) {
        return;
      }

      setPendingAction({
        kind: "entity-reject",
        entityId,
        label: entity.text,
        reason,
      });
    },
    [entities],
  );

  const requestReviewAlert = useCallback(
    (alertId: string, decision: "approve" | "reject") => {
      const alert = alertsState.find((item) => item.id === alertId);
      if (!alert) {
        return;
      }

      setPendingAction({
        kind: "alert-review",
        alertId,
        label: alert.id,
        decision,
      });
    },
    [alertsState],
  );

  const confirmPendingAction = useCallback(async () => {
    if (!pendingAction) {
      return;
    }

    if (pendingAction.kind === "entity-approve") {
      await handleApproveEntity(pendingAction.entityId, validationNote);
    } else if (pendingAction.kind === "entity-reject") {
      await handleRejectEntity(pendingAction.entityId, pendingAction.reason);
    } else {
      await handleReviewAlert(pendingAction.alertId, pendingAction.decision);
    }

    setPendingAction(null);
    setValidationNote("");
  }, [
    handleApproveEntity,
    handleRejectEntity,
    handleReviewAlert,
    pendingAction,
  ]);

  const requiresValidationNote = useMemo(
    () =>
      pendingAction?.kind === "entity-approve" &&
      pendingAction.confidence < 90,
    [pendingAction],
  );

  const pendingActionDescription = useMemo(() => {
    if (!pendingAction) {
      return "";
    }

    if (pendingAction.kind === "entity-approve") {
      return `You are about to approve ${pendingAction.label}.`;
    }

    if (pendingAction.kind === "entity-reject") {
      return `You are about to reject ${pendingAction.label}.`;
    }

    return `You are about to ${pendingAction.decision} ${pendingAction.label}.`;
  }, [pendingAction]);

  const handleExportJson = useCallback(() => {
    if (!selectedDocument) {
      return;
    }

    downloadBlob(
      `${sanitizeFilename(selectedDocument.name)}_evidence.json`,
      JSON.stringify(
        {
          projectId: id,
          documentId: selectedDocument.id,
          documentName: selectedDocument.name,
          exportedAt: new Date().toISOString(),
          entities,
          alerts: alertsState,
          highlights,
        },
        null,
        2,
      ),
      "application/json",
    );
  }, [alertsState, entities, highlights, id, selectedDocument]);

  const handleExportCsv = useCallback(() => {
    if (!selectedDocument) {
      return;
    }

    const rows = [
      ["Type", "Id", "Label", "Page", "Status"],
      ...entities.map((entity) => [
        "entity",
        entity.id,
        entity.text,
        String(entity.page),
        entity.validationStatus ?? "pending",
      ]),
      ...alertsState.map((alert) => [
        "alert",
        alert.id,
        alert.title,
        String(extractAlertEvidenceLocation(alert)?.page_number ?? ""),
        String(alert.status ?? ""),
      ]),
    ];
    const csv = rows
      .map((row) =>
        row
          .map((value) => {
            if (value.includes(",") || value.includes('"') || value.includes("\n")) {
              return `"${value.replace(/"/g, '""')}"`;
            }
            return value;
          })
          .join(","),
      )
      .join("\n");

    downloadBlob(
      `${sanitizeFilename(selectedDocument.name)}_evidence.csv`,
      csv,
      "text/csv;charset=utf-8;",
    );
  }, [alertsState, entities, selectedDocument]);

  const handleExportPdf = useCallback(() => {
    if (!selectedDocument) {
      return;
    }

    const popup = window.open("", "_blank", "noopener,noreferrer,width=960,height=720");
    if (!popup) {
      return;
    }

    const entityRows = entities
      .map(
        (entity) =>
          `<tr><td>${escapeXml(entity.type)}</td><td>${escapeXml(
            entity.text,
          )}</td><td>${entity.page}</td><td>${escapeXml(
            entity.validationStatus ?? "pending",
          )}</td></tr>`,
      )
      .join("");
    const alertRows = alertsState
      .map(
        (alert) =>
          `<tr><td>${escapeXml(alert.title)}</td><td>${escapeXml(
            String(alert.severity),
          )}</td><td>${escapeXml(String(alert.status))}</td></tr>`,
      )
      .join("");

    popup.document.write(`<!DOCTYPE html>
<html lang="en">
  <head>
    <title>${escapeXml(selectedDocument.name)} Evidence Export</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 32px; color: #111827; }
      h1 { margin-bottom: 8px; font-size: 28px; }
      h2 { margin-top: 28px; font-size: 18px; }
      p { margin: 0 0 12px; color: #4b5563; }
      table { width: 100%; border-collapse: collapse; margin-top: 12px; }
      th, td { border: 1px solid #d1d5db; padding: 10px 12px; text-align: left; }
      th { background: #f3f4f6; }
    </style>
  </head>
  <body>
    <h1>Evidence Export</h1>
    <p>${escapeXml(selectedDocument.name)}</p>
    <p>${highlights.length} highlights, ${entities.length} entities, ${alertsState.length} alerts</p>
    <h2>Entities</h2>
    <table>
      <thead><tr><th>Type</th><th>Text</th><th>Page</th><th>Status</th></tr></thead>
      <tbody>${entityRows}</tbody>
    </table>
    <h2>Alerts</h2>
    <table>
      <thead><tr><th>Title</th><th>Severity</th><th>Status</th></tr></thead>
      <tbody>${alertRows}</tbody>
    </table>
  </body>
</html>`);
    popup.document.close();
    popup.focus();
    popup.print();
  }, [alertsState, entities, highlights.length, selectedDocument]);

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
              <DropdownMenuItem onClick={handleExportJson}>
                <FileJson className="mr-2 h-4 w-4" />
                Export JSON
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleExportCsv}>
                <Database className="mr-2 h-4 w-4" />
                Export CSV
              </DropdownMenuItem>
              <DropdownMenuItem onClick={handleExportPdf}>
                <FileText className="mr-2 h-4 w-4" />
                Export PDF
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setIsTemplateOpen(true)}
          >
            Evidence Templates
          </Button>
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
                <LazyPdfEvidenceViewer
                  fileUrl={buildDocumentDownloadUrl(selectedDocumentId)}
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
                      onApprove={requestApproveEntity}
                      onReject={requestRejectEntity}
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
                                requestReviewAlert(alert.id, "approve")
                              }
                            >
                              Approve Alert
                            </Button>
                            <Button
                              size="sm"
                              variant="outline"
                              onClick={() =>
                                requestReviewAlert(alert.id, "reject")
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

              <div className="mt-6 rounded-md border bg-muted/20 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">
                      {relationshipViewMode === "3d"
                        ? "3D Relationship Viewer"
                        : "Relationship Graph"}
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
                      variant={
                        relationshipViewMode === "graph"
                          ? "default"
                          : "outline"
                      }
                      onClick={() => setRelationshipViewMode("graph")}
                    >
                      Graph View
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      variant={
                        relationshipViewMode === "3d" ? "default" : "outline"
                      }
                      onClick={() => setRelationshipViewMode("3d")}
                    >
                      3D Relationship View
                    </Button>
                    <Badge variant="outline">
                      {relationshipGraph.entityNodes.length} entities /{" "}
                      {relationshipGraph.alertNodes.length} alerts
                    </Badge>
                  </div>
                </div>

                {relationshipViewMode === "3d" ? (
                  <div className="mt-4 space-y-4">
                    <div className="grid gap-4 lg:grid-cols-3" style={{ perspective: "1200px" }}>
                      <div
                        className="rounded-md border bg-background/90 p-4 shadow-sm"
                        style={{ transform: "rotateY(18deg) translateZ(24px)" }}
                      >
                        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Layer 1 · Entities
                        </p>
                        <div className="space-y-2">
                          {relationshipGraph.entityNodes.map((node) => (
                            <button
                              key={node.id}
                              type="button"
                              aria-label={`Graph node ${node.id}`}
                              className={cn(
                                "w-full rounded-md border bg-background px-3 py-2 text-left transition-colors",
                                activeEntityId === node.id
                                  ? "border-primary bg-primary/5"
                                  : "border-border hover:border-primary/50",
                              )}
                              onClick={() => setActiveEntityId(node.id)}
                            >
                              <div className="text-sm font-medium text-foreground">
                                {node.label}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Entity · page {node.page}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>

                      <div
                        className="rounded-md border border-dashed bg-muted/30 p-4 shadow-sm"
                        style={{ transform: "translateZ(48px)" }}
                      >
                        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Layer 2 · Relationship Depth
                        </p>
                        <div className="space-y-2 text-sm text-muted-foreground">
                          <p>Contract entities project forward into active alerts.</p>
                          <p>
                            Click any node to focus the linked highlight in the
                            evidence viewer.
                          </p>
                        </div>
                      </div>

                      <div
                        className="rounded-md border bg-background/90 p-4 shadow-sm"
                        style={{ transform: "rotateY(-18deg) translateZ(24px)" }}
                      >
                        <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Layer 3 · Alerts
                        </p>
                        <div className="space-y-2">
                          {relationshipGraph.alertNodes.map((node) => (
                            <button
                              key={node.id}
                              type="button"
                              aria-label={`Graph node ${node.id}`}
                              className={cn(
                                "w-full rounded-md border bg-background px-3 py-2 text-left transition-colors",
                                activeEntityId === node.id
                                  ? "border-primary bg-primary/5"
                                  : "border-border hover:border-primary/50",
                              )}
                              onClick={() => setActiveEntityId(node.id)}
                            >
                              <div className="text-sm font-medium text-foreground">
                                {node.label}
                              </div>
                              <div className="text-xs text-muted-foreground">
                                Alert · {String(node.severity).toLowerCase()}
                              </div>
                            </button>
                          ))}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto_1fr] lg:items-start">
                    <div className="space-y-2">
                      {relationshipGraph.entityNodes.map((node) => (
                        <button
                          key={node.id}
                          type="button"
                          aria-label={`Graph node ${node.id}`}
                          className={cn(
                            "w-full rounded-md border bg-background px-3 py-2 text-left transition-colors",
                            activeEntityId === node.id
                              ? "border-primary bg-primary/5"
                              : "border-border hover:border-primary/50",
                          )}
                          onClick={() => setActiveEntityId(node.id)}
                        >
                          <div className="text-sm font-medium text-foreground">
                            {node.label}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Entity · page {node.page}
                          </div>
                        </button>
                      ))}
                    </div>

                    <div className="hidden items-center justify-center lg:flex">
                      <div className="h-full min-h-[120px] w-px bg-border" />
                    </div>

                    <div className="space-y-2">
                      {relationshipGraph.alertNodes.map((node) => (
                        <button
                          key={node.id}
                          type="button"
                          aria-label={`Graph node ${node.id}`}
                          className={cn(
                            "w-full rounded-md border bg-background px-3 py-2 text-left transition-colors",
                            activeEntityId === node.id
                              ? "border-primary bg-primary/5"
                              : "border-border hover:border-primary/50",
                          )}
                          onClick={() => setActiveEntityId(node.id)}
                        >
                          <div className="text-sm font-medium text-foreground">
                            {node.label}
                          </div>
                          <div className="text-xs text-muted-foreground">
                            Alert · {String(node.severity).toLowerCase()}
                          </div>
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              <div className="mt-6 rounded-md border bg-muted/20 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">
                      AI Relationship Explanation
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Backend-generated explanation grounded in evidence graph citations
                    </p>
                  </div>
                  <Badge variant="outline">Model-backed</Badge>
                </div>

                <div className="mt-4 space-y-3">
                  {relationshipExplanation ? (
                    <>
                      <p className="text-sm text-foreground">
                        {relationshipExplanation.summary}
                      </p>
                      <div className="grid gap-3 md:grid-cols-3">
                        <div className="rounded-md border bg-background p-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Strongest Cluster
                          </p>
                          <p className="mt-2 text-sm text-foreground">
                            {relationshipExplanation.strongestCluster}
                          </p>
                        </div>
                        <div className="rounded-md border bg-background p-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Review Priority
                          </p>
                          <p className="mt-2 text-sm text-foreground">
                            {relationshipExplanation.reviewPriority}
                          </p>
                        </div>
                        <div className="rounded-md border bg-background p-3">
                          <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                            Latest Signal
                          </p>
                          <p className="mt-2 text-sm text-foreground">
                            {relationshipExplanation.latestSignal}
                          </p>
                        </div>
                      </div>
                      <div className="rounded-md border bg-background p-3">
                        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                          Evidence Citations
                        </p>
                        <div className="mt-3 space-y-2">
                          {relationshipExplanation.citations.map((citation) => (
                            <div
                              key={`${citation.clauseId}-${citation.clauseCode}`}
                              className="rounded border border-border/70 bg-muted/20 p-2"
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

              <div className="mt-6 rounded-md border bg-muted/20 p-4">
                <div className="flex items-center justify-between gap-2">
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">
                      Evidence Evolution Timeline
                    </h3>
                    <p className="text-xs text-muted-foreground">
                      Persisted document lifecycle and alert history events
                    </p>
                  </div>
                  <Badge variant="outline">{evidenceTimeline.length} events</Badge>
                </div>

                <div className="mt-4 space-y-3">
                  {evidenceTimeline.length > 0 ? (
                    evidenceTimeline.map((event) => (
                      <div
                        key={event.id}
                        className="flex items-start gap-3 rounded-md border bg-background p-3"
                      >
                        <div className="mt-1 h-2.5 w-2.5 rounded-full bg-primary" />
                        <div className="min-w-0">
                          <p className="font-medium text-sm">{event.title}</p>
                          <p className="text-xs text-muted-foreground">
                            {formatEvidenceTimelineDate(event.occurredAt)}
                          </p>
                          <p className="mt-1 text-sm text-muted-foreground">
                            {event.detail}
                          </p>
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
            </CardContent>
          </Card>
        </ResizablePanel>
      </ResizablePanelGroup>

      <Dialog open={isTemplateOpen} onOpenChange={setIsTemplateOpen}>
        <DialogContent className="sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Start from an evidence template</DialogTitle>
            <DialogDescription>
              Use a guided review lens to focus the current evidence session.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
            <div className="space-y-2">
              {EVIDENCE_TEMPLATES.map((template) => (
                <Button
                  key={template.id}
                  type="button"
                  variant={selectedTemplate?.id === template.id ? "default" : "outline"}
                  className="w-full justify-start"
                  onClick={() => setSelectedTemplateId(template.id)}
                >
                  {template.name}
                </Button>
              ))}
            </div>

            {selectedTemplate ? (
              <div className="rounded-md border bg-muted/20 p-5">
                <div className="space-y-2">
                  <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Template Summary
                  </div>
                  <h3 className="text-lg font-semibold text-foreground">
                    {selectedTemplate.summary}
                  </h3>
                </div>

                <div className="mt-5 grid gap-5 md:grid-cols-2">
                  <div>
                    <div className="text-sm font-medium text-foreground">
                      Review focus
                    </div>
                    <ul className="mt-2 space-y-2 text-sm text-muted-foreground">
                      {selectedTemplate.reviewFocus.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                  <div>
                    <div className="text-sm font-medium text-foreground">Tags</div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selectedTemplate.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setIsTemplateOpen(false)}>
              Close
            </Button>
            <Button onClick={() => setIsTemplateOpen(false)}>Use Template</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

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

      <Dialog
        open={pendingAction !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPendingAction(null);
            setValidationNote("");
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirm evidence action</DialogTitle>
            <DialogDescription>{pendingActionDescription}</DialogDescription>
          </DialogHeader>
          {requiresValidationNote ? (
            <div className="space-y-2">
              <p className="text-sm text-amber-700">
                Confidence below 90% requires a validation note before
                approval.
              </p>
              <Label htmlFor="evidence-validation-note">Validation note</Label>
              <Textarea
                id="evidence-validation-note"
                value={validationNote}
                onChange={(event) => setValidationNote(event.target.value)}
                placeholder="Document why this low-confidence extraction is still acceptable."
                rows={3}
              />
            </div>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setPendingAction(null);
                setValidationNote("");
              }}
            >
              Cancel Action
            </Button>
            <Button
              type="button"
              onClick={() => void confirmPendingAction()}
              disabled={requiresValidationNote && !validationNote.trim()}
            >
              Confirm Action
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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

function extractAlertEvidenceLocation(alert: ProjectAlert): {
  page_number: number;
  bbox: [number, number, number, number];
  normalized?: boolean;
} | null {
  const evidence = (alert.evidence_json as { evidence_location?: {
    page_number: number;
    bbox: [number, number, number, number];
    normalized?: boolean;
  } } | undefined)?.evidence_location;

  if (!evidence || !Array.isArray(evidence.bbox)) {
    return null;
  }

  const normalized =
    evidence.normalized ??
    evidence.bbox.every((value) => value >= 0 && value <= 1);

  return {
    page_number: evidence.page_number,
    bbox: evidence.bbox,
    normalized,
  };
}

function mapAlertSeverityToPdfSeverity(
  severity: ProjectAlert["severity"],
): PdfHighlight["severity"] {
  switch (String(severity).toLowerCase()) {
    case "critical":
      return "critical";
    case "high":
      return "high";
    case "medium":
      return "medium";
    default:
      return "low";
  }
}

function buildDocumentDownloadUrl(documentId: string): string {
  return `${env.API_BASE_URL}/documents/${documentId}/download`;
}
