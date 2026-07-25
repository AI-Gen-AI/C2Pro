/**
 * Test Suite ID: TASK-FRT-188
 * Project Audit Report export route.
 */
"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Loader2 } from "lucide-react";
import { AuditReportView } from "@/components/features/report/AuditReportView";
import {
  composeAuditReport,
  downloadAuditReportJson,
} from "@/components/features/report/report-data";
import { useProject } from "@/hooks/useProject";
import { useProjectDocuments } from "@/hooks/useProjectDocuments";
import { useListProjectAlertsApiV1AlertsProjectsProjectIdGet } from "@/lib/api/generated/alerts/alerts";
import { useListReviewQueueApiV1HitlQueueGet } from "@/lib/api/generated/hitl/hitl";
import { getDashboardSummary } from "@/lib/api/services/dashboard";

export default function ProjectReportPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [includeOpenFindings, setIncludeOpenFindings] = useState(true);
  const [includeRejectedFindings, setIncludeRejectedFindings] = useState(false);

  const projectQuery = useProject(projectId);
  const documentsQuery = useProjectDocuments(projectId);
  const alertsQuery = useListProjectAlertsApiV1AlertsProjectsProjectIdGet(
    projectId,
    undefined,
  );
  const reviewItemsQuery = useListReviewQueueApiV1HitlQueueGet(
    { project_id: projectId, limit: 200 },
    { query: { enabled: Boolean(projectId) } },
  );
  const dashboardQuery = useQuery({
    queryKey: ["audit-report-dashboard", projectId],
    queryFn: () => getDashboardSummary(projectId),
    enabled: Boolean(projectId),
  });

  const isLoading =
    projectQuery.isLoading ||
    documentsQuery.loading ||
    alertsQuery.isLoading ||
    reviewItemsQuery.isLoading ||
    dashboardQuery.isLoading;
  const error =
    projectQuery.error ||
    documentsQuery.error ||
    alertsQuery.error ||
    reviewItemsQuery.error ||
    dashboardQuery.error;

  const payload = useMemo(() => {
    if (!projectQuery.data) return null;

    // TODO(TASK-BCK backend report endpoint): replace client-side composition
    // when the backend exposes a signed audit-report payload endpoint.
    return composeAuditReport({
      project: projectQuery.data,
      dashboard: dashboardQuery.data ?? null,
      alerts: alertsQuery.data?.items ?? [],
      documents: documentsQuery.documents,
      reviewItems: reviewItemsQuery.data?.items,
      reviewItemsProjectScoped: true,
      generatedAt: new Date().toISOString(),
    });
  }, [
    alertsQuery.data?.items,
    dashboardQuery.data,
    documentsQuery.documents,
    projectQuery.data,
    reviewItemsQuery.data?.items,
  ]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24 text-muted-foreground">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        Loading audit report...
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
        {error instanceof Error ? error.message : "Could not load audit report."}
      </div>
    );
  }

  if (!payload) {
    return (
      <div className="rounded-md border border-dashed bg-card p-6 text-sm text-muted-foreground">
        Project identity is not available for this report.
      </div>
    );
  }

  return (
    <AuditReportView
      payload={payload}
      includeOpenFindings={includeOpenFindings}
      includeRejectedFindings={includeRejectedFindings}
      onIncludeOpenFindingsChange={setIncludeOpenFindings}
      onIncludeRejectedFindingsChange={setIncludeRejectedFindings}
      onDownloadJson={() => downloadAuditReportJson(payload)}
      onPrint={() => window.print()}
    />
  );
}
