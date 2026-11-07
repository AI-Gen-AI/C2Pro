"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useUser } from "@clerk/nextjs";
import { useParams, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { type ExtractedEntity } from "@/components/evidence";
import { EvidenceActionDialog } from "@/components/features/evidence/EvidenceActionDialog";
import { EvidenceDocumentsCard } from "@/components/features/evidence/EvidenceDocumentsCard";
import { EvidenceHeader } from "@/components/features/evidence/EvidenceHeader";
import { StructuredSourceRowPanel } from "@/components/features/evidence/StructuredSourceRowPanel";
import { EvidenceRevisionHistoryPanel } from "@/components/features/evidence/EvidenceRevisionHistoryPanel";
import { EvidenceTemplateDialog } from "@/components/features/evidence/EvidenceTemplateDialog";
import { EvidenceWorkspace } from "@/components/features/evidence/EvidenceWorkspace";
import { type PdfHighlight } from "@/components/features/evidence/PdfEvidenceViewer";
import {
  resolveEvidenceAddress,
  sourceEvidenceClausesFromDocumentDetail,
  type EvidenceTargetType,
} from "@/components/features/evidence/evidence-addressability";
import {
  EVIDENCE_TEMPLATES,
  downloadBlob,
  escapeXml,
  extractAlertEvidenceLocation,
  mapAlertSeverityToPdfSeverity,
  mapEntityTypeToApprovalResourceType,
  mapHighlightColorToSeverity,
  normalizeConfidence,
  normalizeEntityType,
  sanitizeFilename,
  technicalSourcePresentation,
  type EvidencePanelTab,
  type PendingEvidenceAction,
} from "@/components/features/evidence/evidence-page-utils";
import { useDocumentAlerts } from "@/hooks/useDocumentAlerts";
import { useDocumentEntities } from "@/hooks/useDocumentEntities";
import { useDocumentHistory } from "@/hooks/useDocumentHistory";
import { useDocumentRelationshipExplanation } from "@/hooks/useDocumentRelationshipExplanation";
import { useProject } from "@/hooks/useProject";
import { useProjectDocuments } from "@/hooks/useProjectDocuments";
import { useReviewResourceApiV1ApprovalsResourceTypeResourceIdPatch } from "@/lib/api/generated/approvals/approvals";
import {
  useResolveAlertApiV1AlertsAlertIdResolvePost,
  useReviewAlertApiV1AlertsAlertIdReviewPost,
} from "@/lib/api/generated/alerts/alerts";
import { useGetDocumentEndpointApiV1DocumentsDocumentIdGet } from "@/lib/api/generated/documents/documents";
import type { AlertResponse as BackendAlertResponse } from "@/types/backend";

function semanticTargetType(entityType: string): EvidenceTargetType {
  switch (entityType.toLowerCase()) {
    case "stakeholder":
      return "STAKEHOLDER";
    case "raci":
      return "RACI";
    case "wbs":
      return "WBS";
    case "clause":
      return "CLAUSE";
    case "change":
      return "CHANGE";
    default:
      return "OTHER";
  }
}

type SourceLinkNoticeKind =
  | "revision"
  | "document"
  | "highlight"
  | "source-clause"
  | "fallback"
  | null;

function selectSourceLinkNotice({
  revisionUnavailable,
  documentUnavailable,
  highlightUnavailable,
  hasSourceClause,
  documentFallback,
}: {
  revisionUnavailable: boolean;
  documentUnavailable: boolean;
  highlightUnavailable: boolean;
  hasSourceClause: boolean;
  documentFallback: boolean;
}): SourceLinkNoticeKind {
  if (revisionUnavailable) return "revision";
  if (documentUnavailable) return "document";
  if (highlightUnavailable) return "highlight";
  if (hasSourceClause) return "source-clause";
  if (documentFallback) return "fallback";
  return null;
}

export default function EvidencePage() {
  const { id } = useParams<{ id: string }>();
  const searchParams = useSearchParams();
  const requestedDocumentId = searchParams.get("documentId");
  const requestedHighlightId = searchParams.get("highlightId");
  const requestedRevisionId = searchParams.get("revisionId");
  // S4: a Budget row / Schedule activity reference (exact locator + the SHA-256 the finding was raised on).
  const requestedLocator = searchParams.get("locator");
  const requestedExpectedHash = searchParams.get("expectedHash");
  // Return path is constructed locally from the authenticated project scope,
  // never from a user-supplied full URL (no open redirects or cross-project jump).
  const returnReviewItemId = searchParams.get("returnReviewItemId");
  const requestedReturnAlertId = searchParams.get("returnAlertId");
  // No open redirect and no invented cross-project destination: alert identity
  // is a constrained local anchor in the currently authenticated project.
  const returnAlertId =
    searchParams.get("origin") === "alerts" &&
    requestedReturnAlertId &&
    /^[A-Za-z0-9_-]{1,128}$/.test(requestedReturnAlertId)
      ? requestedReturnAlertId
      : null;
  // Only report-generated anchors are accepted. The link is built against
  // the authenticated route project ID, never a user-provided URL or project.
  const requestedReturnDiscrepancy = searchParams.get("returnDiscrepancy");
  const returnDiscrepancy =
    requestedReturnDiscrepancy &&
    /^source-discrepancy-[0-9a-f]{12}-[0-9]{1,5}$/.test(requestedReturnDiscrepancy)
      ? requestedReturnDiscrepancy
      : null;
  // Health links cite the persisted source clause, not a semantic/alert alias.
  const requestedFromHealth = searchParams.get("origin") === "health";
  const revisionReadOnly = Boolean(requestedRevisionId);
  const { isLoaded: isUserLoaded, user } = useUser();
  const reviewerName = user?.primaryEmailAddress?.emailAddress ?? user?.id;
  const reviewerIdentityReady = isUserLoaded && Boolean(reviewerName);
  const { data: project } = useProject(id);
  const projectName = project?.name?.trim() || id;

  const [splitView, setSplitView] = useState(false);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(
    null,
  );
  const [activeEntityId, setActiveEntityId] = useState<string | null>(null);
  const [activePanelTab, setActivePanelTab] =
    useState<EvidencePanelTab>("entities");
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

    if (requestedDocumentId) {
      // A deep link names its document. If that document is not in this project, nothing else
      // is opened in its place: showing another document's evidence would be a wrong answer.
      setSelectedDocumentId(
        documents.some((doc) => doc.id === requestedDocumentId) ? requestedDocumentId : null,
      );
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
  } = useDocumentEntities(revisionReadOnly ? null : selectedDocumentId);
  const {
    alerts,
    loading: alertsLoading,
    error: alertsError,
    refetch: refetchAlerts,
  } = useDocumentAlerts(revisionReadOnly ? null : selectedDocumentId);
  const {
    items: evidenceTimeline,
  } = useDocumentHistory(revisionReadOnly ? null : selectedDocumentId);
  const {
    explanation: relationshipExplanation,
  } = useDocumentRelationshipExplanation(revisionReadOnly ? null : selectedDocumentId);
  const shouldResolveSourceEvidence = Boolean(
    selectedDocumentId &&
      requestedDocumentId === selectedDocumentId &&
      requestedHighlightId,
  );
  const {
    data: documentDetail,
    isLoading: documentDetailLoading,
  } = useGetDocumentEndpointApiV1DocumentsDocumentIdGet(
    selectedDocumentId ?? "",
    requestedRevisionId ? { revision_id: requestedRevisionId } : undefined,
    { query: { enabled: shouldResolveSourceEvidence } },
  );
  const [alertsState, setAlertsState] = useState(alerts);
  const [actionError, setActionError] = useState<string | null>(null);
  const reviewResource = useReviewResourceApiV1ApprovalsResourceTypeResourceIdPatch();
  const reviewProjectAlert = useReviewAlertApiV1AlertsAlertIdReviewPost();
  const resolveProjectAlert = useResolveAlertApiV1AlertsAlertIdResolvePost();

  const sourceClauses = useMemo(() => {
    // The cited document must be the fetched one and belong to this project.
    // A stale or mismatched detail response must never lend a clause to another source.
    if (!documentDetail || documentDetail.id !== selectedDocumentId ||
        (documentDetail.project_id && documentDetail.project_id !== id)) {
      return [];
    }
    return sourceEvidenceClausesFromDocumentDetail(documentDetail.clauses);
  }, [documentDetail, id, selectedDocumentId]);
  // The generated document-detail type does not guarantee an immutable
  // PDF revision identity yet. An absent/incorrect server binding must
  // block a revision-pinned link rather than display today's PDF as history.
  const documentRevisionId =
    typeof (documentDetail as unknown as Record<string, unknown> | undefined)?.revision_id === "string"
      ? String((documentDetail as unknown as Record<string, unknown>).revision_id)
      : null;
  // Block pinned PDF navigation from the first render through the entire
  // asynchronous revision check. Never fetch the unpinned current PDF.
  const requestedRevisionUnavailable = Boolean(
    requestedRevisionId &&
    selectedDocumentId === requestedDocumentId &&
    (
      documentDetailLoading ||
      documentRevisionId !== requestedRevisionId ||
      documentDetail?.id !== selectedDocumentId ||
      documentDetail?.project_id !== id
    ),
  );
  const semanticEvidenceTargets = useMemo(
    () => [
      ...apiEntities.map((entity) => ({
        id: entity.id,
        label: entity.text,
        type: semanticTargetType(entity.type),
      })),
      ...alertsState.map((alert) => ({
        id: alert.id,
        label: alert.title,
        type: "ALERT" as const,
      })),
    ],
    [alertsState, apiEntities],
  );
  const requestedHighlightKey =
    requestedDocumentId && requestedHighlightId
      ? `${requestedDocumentId}:${requestedRevisionId ?? "current"}:${requestedHighlightId}`
      : null;
  const requestedEvidenceResolution = useMemo(() => {
    if (
      !requestedHighlightId ||
      selectedDocumentId !== requestedDocumentId
    ) {
      return null;
    }

    return resolveEvidenceAddress({
      evidenceId: requestedHighlightId,
      semanticTargets: semanticEvidenceTargets,
      sourceClauses,
      preferSourceClause: requestedFromHealth,
      revisionId: requestedRevisionId,
      documentRevisionId,
    });
  }, [
    requestedDocumentId,
    requestedHighlightId,
    requestedRevisionId,
    requestedFromHealth,
    documentRevisionId,
    selectedDocumentId,
    semanticEvidenceTargets,
    sourceClauses,
  ]);

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

    const sourceClauseHighlight =
      requestedEvidenceResolution?.kind === "raw-clause" &&
      requestedEvidenceResolution.target.page !== null
        ? [
            {
              id: `source-clause-${requestedEvidenceResolution.target.id}`,
              clauseId: requestedEvidenceResolution.target.id,
              page: requestedEvidenceResolution.target.page,
              text: requestedEvidenceResolution.target.label,
              severity: "low" as const,
            },
          ]
        : [];

    // A revision-pinned PDF must never receive current entity/alert overlays.
    // Only the clause verified against the requested revision is addressable.
    return revisionReadOnly
      ? sourceClauseHighlight
      : [...mappedEntityHighlights, ...alertHighlights, ...sourceClauseHighlight];
  }, [
    apiEntities,
    entityHighlights,
    alertsState,
    requestedEvidenceResolution,
    revisionReadOnly,
  ]);

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
      (revisionReadOnly ? [] : apiEntities).map((entity) => ({
        id: entity.id,
        type: normalizeEntityType(entity.type),
        text: entity.text,
        approvalResourceType: mapEntityTypeToApprovalResourceType(entity.type),
        confidence: normalizeConfidence(entity.confidence),
        page: entity.page,
        ...technicalSourcePresentation(entity.metadata),
        validationStatus: "pending",
      })),
    [apiEntities, revisionReadOnly],
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

  const syncPanelSelection = useCallback(
    (targetId: string) => {
      setActiveEntityId(targetId);
      if (alertsState.some((alert) => alert.id === targetId)) {
        setActivePanelTab("alerts");
        return;
      }

      if (entities.some((entity) => entity.id === targetId)) {
        setActivePanelTab("entities");
      }
    },
    [alertsState, entities],
  );

  // Health → Evidence: activate the linked target once semantic and source evidence load.
  const [appliedHighlightKey, setAppliedHighlightKey] = useState<string | null>(null);
  useEffect(() => {
    if (!requestedHighlightKey || appliedHighlightKey === requestedHighlightKey) return;
    if (
      selectedDocumentId !== requestedDocumentId ||
      entitiesLoading ||
      alertsLoading ||
      documentDetailLoading
    ) {
      return;
    }
    if (requestedEvidenceResolution?.kind === "semantic" && requestedHighlightId) {
      syncPanelSelection(requestedHighlightId);
      setAppliedHighlightKey(requestedHighlightKey);
    } else if (requestedEvidenceResolution?.kind === "raw-clause") {
      setActiveEntityId(requestedEvidenceResolution.target.id);
      setActivePanelTab("search");
      setAppliedHighlightKey(requestedHighlightKey);
    } else if (requestedEvidenceResolution?.kind === "document-fallback") {
      setActiveEntityId(null);
      setAppliedHighlightKey(requestedHighlightKey);
    }
  }, [
    appliedHighlightKey,
    alertsLoading,
    documentDetailLoading,
    entitiesLoading,
    requestedDocumentId,
    requestedHighlightId,
    requestedHighlightKey,
    requestedEvidenceResolution,
    selectedDocumentId,
    syncPanelSelection,
  ]);

  const requestedDocumentUnavailable =
    Boolean(requestedDocumentId) &&
    !documentsLoading &&
    !documents.some((doc) => doc.id === requestedDocumentId);
  const requestedHighlightUnavailable =
    Boolean(requestedHighlightKey) &&
    !requestedDocumentUnavailable &&
    selectedDocumentId === requestedDocumentId &&
    !entitiesLoading &&
    !alertsLoading &&
    !documentDetailLoading &&
    requestedEvidenceResolution?.kind === "unresolved";
  const requestedSourceClause =
    requestedEvidenceResolution?.kind === "raw-clause"
      ? requestedEvidenceResolution.target
      : null;
  const requestedDocumentFallback =
    requestedEvidenceResolution?.kind === "document-fallback"
      ? requestedEvidenceResolution.target
      : null;
  const exactSourceClause = requestedSourceClause ?? requestedDocumentFallback;

  // One authoritative decision flow (the card's single confirmation). It resolves only after the server answered
  // and shows the status the SERVER reports; every failure throws so the dialog stays open with the reason.
  const persistEntityDecision = useCallback(
    async (
      entityId: string,
      status: "APPROVED" | "REJECTED",
      comment: string | null,
    ) => {
      const entity = entities.find((item) => item.id === entityId);
      if (!entity) {
        throw new Error("This item is no longer in the list. Nothing was changed.");
      }
      if (!entity.approvalResourceType) {
        // Defensive: unsupported types render no actions, so this must never look like a success.
        throw new Error(
          `${entity.type} items have no individual approval. Nothing was saved.`,
        );
      }

      setActionError(null);
      let confirmed: { status?: string } | undefined;
      try {
        confirmed = (await reviewResource.mutateAsync({
          resourceType: entity.approvalResourceType,
          resourceId: entityId,
          data: { status, correction_data: undefined, feedback_comment: comment },
        })) as { status?: string } | undefined;
      } catch {
        throw new Error("The server did not save the decision. Nothing was changed; try again.");
      }

      // Trust the persisted record the server returned, not the click.
      const serverStatus = String(confirmed?.status ?? "").toUpperCase();
      if (serverStatus !== status) {
        throw new Error(
          `The server answered ${serverStatus || "no status"} instead of ${status}. The decision is not recorded.`,
        );
      }
      setEntities((prev) =>
        prev.map((item) =>
          item.id === entityId
            ? {
                ...item,
                validationStatus: status === "APPROVED" ? "approved" : "rejected",
                validated: status === "APPROVED",
                rejectionReason: status === "REJECTED" ? (comment ?? undefined) : undefined,
              }
            : item,
        ),
      );
    },
    [entities, reviewResource],
  );

  const handleApproveEntity = useCallback(
    (entityId: string, note?: string) =>
      persistEntityDecision(entityId, "APPROVED", note?.trim() || null),
    [persistEntityDecision],
  );

  const handleRejectEntity = useCallback(
    (entityId: string, reason: string) => persistEntityDecision(entityId, "REJECTED", reason),
    [persistEntityDecision],
  );

  const handleEntityClick = useCallback(
    (entity: ExtractedEntity) => {
      syncPanelSelection(entity.id);
    },
    [syncPanelSelection],
  );

  const handleHighlightClick = useCallback(
    (id: string) => {
      const mappedHighlight = highlights.find((highlight) => highlight.id === id);
      syncPanelSelection(mappedHighlight?.clauseId ?? id);
    },
    [highlights, syncPanelSelection],
  );

  const handleRefresh = useCallback(async () => {
    await Promise.all([refetchDocuments(), refetchEntities(), refetchAlerts()]);
  }, [refetchDocuments, refetchEntities, refetchAlerts]);

  const handleRefreshClick = useCallback(() => {
    setActionError(null);
    handleRefresh().catch(() => {
      setActionError("Unable to refresh evidence.");
    });
  }, [handleRefresh]);

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
    if (!reviewerName) {
      return;
    }

    setActionError(null);
    const updatedAlert = await resolveProjectAlert.mutateAsync({
      alertId,
      data: {
        resolution: "Resolved from evidence viewer",
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
  }, [resolveProjectAlert, reviewerName]);

  const handleResolveAlertClick = useCallback(
    (alertId: string) => {
      handleResolveAlert(alertId).catch(() => {
        setActionError("Unable to resolve alert.");
      });
    },
    [handleResolveAlert],
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
    if (!pendingAction || pendingAction.kind !== "alert-review") {
      return;
    }

    await handleReviewAlert(pendingAction.alertId, pendingAction.decision);

    setPendingAction(null);
    setValidationNote("");
  }, [handleReviewAlert, pendingAction]);

  const handleConfirmPendingActionClick = useCallback(() => {
    confirmPendingAction().catch(() => {
      setActionError("Unable to complete evidence action.");
    });
  }, [confirmPendingAction]);

  const requiresValidationNote = useMemo(
    () =>
      pendingAction?.kind === "entity-approve" &&
      (pendingAction.confidence === null || pendingAction.confidence < 90),
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
        String(entity.page ?? ""),
        entity.approvalResourceType ? (entity.validationStatus ?? "pending") : "inspection_only",
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
          )}</td><td>${entity.page ?? ""}</td><td>${escapeXml(
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

  const sourceLinkNotice = selectSourceLinkNotice({
    revisionUnavailable: requestedRevisionUnavailable,
    documentUnavailable: requestedDocumentUnavailable,
    highlightUnavailable: requestedHighlightUnavailable,
    hasSourceClause: Boolean(requestedSourceClause),
    documentFallback: Boolean(requestedDocumentFallback),
  });

  return (
    <div className="space-y-6">
      <EvidenceHeader
        projectName={projectName}
        documentCount={documents.length}
        entityCount={revisionReadOnly ? 0 : entities.length}
        alertCount={revisionReadOnly ? 0 : alertsState.length}
        readOnlyRevision={revisionReadOnly}
        splitView={splitView}
        onRefresh={handleRefreshClick}
        onExportJson={handleExportJson}
        onExportCsv={handleExportCsv}
        onExportPdf={handleExportPdf}
        onOpenTemplates={() => setIsTemplateOpen(true)}
        onToggleSplitView={() => setSplitView((value) => !value)}
      />

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

      {sourceLinkNotice === "revision" && (
        <Alert data-testid="evidence-link-revision-unavailable">
          <AlertDescription>
            This source revision cannot be verified against the PDF currently
            available. No document or highlight was opened for this revision-bound link.
          </AlertDescription>
        </Alert>
      )}
      {sourceLinkNotice === "document" && (
        <Alert data-testid="evidence-link-unavailable">
          <AlertDescription>
            The linked document is not available in this project, so no other document was opened.
          </AlertDescription>
        </Alert>
      )}
      {sourceLinkNotice === "highlight" && (
        <Alert data-testid="evidence-link-unavailable">
          <AlertDescription>
            The linked evidence was not found in this document. Nothing else was selected.
          </AlertDescription>
        </Alert>
      )}
      {sourceLinkNotice === "source-clause" && requestedSourceClause && (
        <Alert data-testid="evidence-link-source-clause">
          <AlertDescription>
            Showing source clause {requestedSourceClause.clauseCode ?? requestedSourceClause.id} on page {requestedSourceClause.page}. Exact highlight unavailable when source geometry is not persisted.
          </AlertDescription>
        </Alert>
      )}
      {sourceLinkNotice === "fallback" && (
        <Alert data-testid="evidence-link-document-fallback">
          <AlertDescription>
            Exact highlight unavailable. The linked source evidence has no resolvable page span, so its source document is shown without inventing a page.
          </AlertDescription>
        </Alert>
      )}

      {exactSourceClause && selectedDocument && !requestedRevisionUnavailable && (
        <section
          data-testid="evidence-exact-source"
          data-source-document-id={selectedDocumentId ?? ""}
          data-source-clause-id={exactSourceClause.id}
          aria-label="Verified source clause"
          className="rounded-xl border bg-card p-4 text-sm"
        >
          <h2 className="font-semibold">Source clause {exactSourceClause.clauseCode ?? exactSourceClause.id}</h2>
          <p className="mt-1 text-muted-foreground" data-testid="evidence-source-document">
            From {selectedDocument.name}
            {exactSourceClause.page !== null ? ` · Page ${exactSourceClause.page}` : " · Page not verified"}
          </p>
          {exactSourceClause.excerpt ? (
            <blockquote
              data-testid="evidence-source-excerpt"
              className="mt-3 whitespace-pre-wrap border-l-2 pl-3 text-foreground"
            >
              {exactSourceClause.excerpt}
            </blockquote>
          ) : (
            <p data-testid="evidence-source-text-unavailable" className="mt-2 text-muted-foreground">
              Original clause text is not available in this document response; no text was invented.
            </p>
          )}
        </section>
      )}

      {returnReviewItemId ? (
        <Link
          data-testid="evidence-return-to-review"
          href={`/projects/${encodeURIComponent(id)}/review?itemId=${encodeURIComponent(returnReviewItemId)}`}
          className="inline-flex rounded-md border px-3 py-2 text-sm font-medium text-primary hover:underline"
        >
          Back to this review
        </Link>
      ) : null}

      {returnDiscrepancy && !returnReviewItemId ? (
        <Link
          data-testid="evidence-return-to-discrepancy"
          href={`/projects/${encodeURIComponent(id)}/report?mode=current-state#${returnDiscrepancy}`}
          className="inline-flex rounded-md border px-3 py-2 text-sm font-medium text-primary hover:underline"
        >
          Back to this Current State finding
        </Link>
      ) : null}

      {returnAlertId && !returnReviewItemId && !returnDiscrepancy ? (
        <Link
          data-testid="evidence-return-to-alert"
          href={"/projects/" + encodeURIComponent(id) + "/alerts#alert-" + returnAlertId}
          className="inline-flex rounded-md border px-3 py-2 text-sm font-medium text-primary hover:underline"
        >
          Back to this alert
        </Link>
      ) : null}

      {requestedDocumentId && requestedRevisionId && requestedLocator ? (
        <StructuredSourceRowPanel
          documentId={requestedDocumentId}
          revisionId={requestedRevisionId}
          locator={requestedLocator}
          expectedBlobHash={requestedExpectedHash}
        />
      ) : null}

      <EvidenceRevisionHistoryPanel documentId={selectedDocumentId} projectId={id} />

      <EvidenceWorkspace
        splitView={splitView}
        readOnlyRevision={revisionReadOnly}
        selectedDocument={requestedRevisionUnavailable ? null : selectedDocument}
        selectedDocumentId={requestedRevisionUnavailable ? null : selectedDocumentId}
        highlights={requestedRevisionUnavailable ? [] : highlights}
        selectedRevisionId={requestedRevisionUnavailable ? null : requestedRevisionId}
        activeHighlightId={activeHighlightId}
        activePanelTab={activePanelTab}
        entities={revisionReadOnly ? [] : entities}
        entitiesLoading={entitiesLoading}
        entitiesError={entitiesError}
        alertsState={revisionReadOnly ? [] : alertsState}
        alertsLoading={alertsLoading}
        alertsError={alertsError}
        activeEntityId={activeEntityId}
        highlightSearchQuery={highlightSearchQuery}
        filteredHighlightResults={filteredHighlightResults}
        relationshipViewMode={relationshipViewMode}
        relationshipGraph={relationshipGraph}
        relationshipExplanation={relationshipExplanation}
        evidenceTimeline={evidenceTimeline}
        reviewerIdentityReady={reviewerIdentityReady}
        onHighlightClick={handleHighlightClick}
        onActivePanelTabChange={setActivePanelTab}
        onApproveEntity={handleApproveEntity}
        onRejectEntity={handleRejectEntity}
        onEntityClick={handleEntityClick}
        onSearchQueryChange={setHighlightSearchQuery}
        onSelectPanelItem={syncPanelSelection}
        onRelationshipViewModeChange={setRelationshipViewMode}
        onReviewAlert={requestReviewAlert}
        onResolveAlert={handleResolveAlertClick}
      />

      <EvidenceTemplateDialog
        open={isTemplateOpen}
        templates={EVIDENCE_TEMPLATES}
        selectedTemplate={selectedTemplate}
        onOpenChange={setIsTemplateOpen}
        onSelectTemplate={setSelectedTemplateId}
      />

      <EvidenceDocumentsCard
        documents={documents}
        documentsLoading={documentsLoading}
        selectedDocumentId={selectedDocumentId}
        onSelectDocument={setSelectedDocumentId}
      />

      <EvidenceActionDialog
        pendingAction={pendingAction}
        pendingActionDescription={pendingActionDescription}
        requiresValidationNote={requiresValidationNote}
        validationNote={validationNote}
        onValidationNoteChange={setValidationNote}
        onCancel={() => {
          setPendingAction(null);
          setValidationNote("");
        }}
        onConfirm={handleConfirmPendingActionClick}
      />
    </div>
  );
}
