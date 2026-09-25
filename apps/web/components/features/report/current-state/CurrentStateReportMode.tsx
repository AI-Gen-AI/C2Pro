/**
 * Test Suite ID: TS-P0D-REPORT-UI-002
 * Current State Report container: fetches the backend projection, renders it,
 * and exports exactly the report on screen.
 */
"use client";

import { Download, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useGetCurrentStateReportApiV1ProjectsProjectIdReportsCurrentStateGet } from "@/lib/api/generated/project-reports/project-reports";
import { CurrentStateReportView } from "./CurrentStateReportView";
import {
  buildCurrentStateCsv,
  buildCurrentStateJson,
  currentStateExportFilename,
  downloadTextFile,
} from "./current-state-export";
import { formatDateTime } from "./current-state-format";

function httpStatusOf(error: unknown): number | undefined {
  if (typeof error !== "object" || error === null) {
    return undefined;
  }
  const response = (error as { response?: { status?: unknown } }).response;
  return typeof response?.status === "number" ? response.status : undefined;
}

export function CurrentStateReportMode({ projectId }: { projectId: string }) {
  // A report states what was known when it was generated, so it is only
  // regenerated when the user asks for it.
  const query = useGetCurrentStateReportApiV1ProjectsProjectIdReportsCurrentStateGet(projectId, {
    query: {
      enabled: Boolean(projectId),
      staleTime: Infinity,
      refetchOnWindowFocus: false,
      refetchOnReconnect: false,
    },
  });

  if (!projectId) {
    return (
      <p data-testid="current-state-no-project" className="text-sm text-muted-foreground">
        No project selected.
      </p>
    );
  }

  if (query.isLoading) {
    return (
      <div
        role="status"
        data-testid="current-state-loading"
        className="flex items-center justify-center py-24 text-muted-foreground"
      >
        <Loader2 className="mr-2 h-5 w-5 animate-spin" aria-hidden="true" />
        Generating current state report...
      </div>
    );
  }

  const report = query.data;

  if (!report) {
    if (!query.isError) {
      return null;
    }
    const notFound = httpStatusOf(query.error) === 404;
    return (
      <div
        role="alert"
        data-testid="current-state-error"
        className="space-y-3 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive"
      >
        <p>
          {notFound
            ? "This project was not found, or you do not have access to it."
            : "The current state report could not be generated."}
        </p>
        {notFound ? null : (
          <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
            Try again
          </Button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-end gap-2 print:hidden">
        <Button variant="outline" onClick={() => void query.refetch()} disabled={query.isFetching}>
          <RefreshCw className={query.isFetching ? "mr-2 h-4 w-4 animate-spin" : "mr-2 h-4 w-4"} aria-hidden="true" />
          Regenerate
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            downloadTextFile(
              currentStateExportFilename(report, "json"),
              buildCurrentStateJson(report),
              "application/json;charset=utf-8",
            )
          }
        >
          <Download className="mr-2 h-4 w-4" aria-hidden="true" />
          Download JSON
        </Button>
        <Button
          variant="outline"
          onClick={() =>
            downloadTextFile(
              currentStateExportFilename(report, "csv"),
              buildCurrentStateCsv(report),
              "text/csv;charset=utf-8",
            )
          }
        >
          <Download className="mr-2 h-4 w-4" aria-hidden="true" />
          Download CSV
        </Button>
      </div>
      {query.isError ? (
        <div
          role="alert"
          data-testid="regenerate-failed"
          className="rounded-md border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200"
        >
          Could not regenerate the report; showing the report generated {formatDateTime(report.generated_at)}.
        </div>
      ) : null}
      <CurrentStateReportView report={report} />
    </div>
  );
}
