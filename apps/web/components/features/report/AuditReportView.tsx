/**
 * Test Suite ID: TASK-FRT-188
 * Printable Audit Report export view.
 */
"use client";

import { Download, Printer } from "lucide-react";
import { CategoryV2Panel } from "@/components/coherence/CategoryV2Panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AuditReportPayload, ReportAlert } from "./report-data";

type AuditReportViewProps = {
  payload: AuditReportPayload;
  includeOpenFindings: boolean;
  includeRejectedFindings: boolean;
  onIncludeOpenFindingsChange: (checked: boolean) => void;
  onIncludeRejectedFindingsChange: (checked: boolean) => void;
  onDownloadJson: () => void;
  onPrint: () => void;
};

export function AuditReportView({
  payload,
  includeOpenFindings,
  includeRejectedFindings,
  onIncludeOpenFindingsChange,
  onIncludeRejectedFindingsChange,
  onDownloadJson,
  onPrint,
}: AuditReportViewProps) {
  const visibleAlerts = [
    ...(includeOpenFindings ? payload.alertGroups.open : []),
    ...payload.alertGroups.approved,
    ...(includeRejectedFindings ? payload.alertGroups.rejected : []),
  ];

  return (
    <div className="mx-auto max-w-5xl space-y-6 print:max-w-none print:space-y-4">
      <style>{printStyles}</style>

      <div className="flex flex-wrap items-start justify-between gap-4 print:hidden">
        <div>
          <h1 className="text-2xl font-semibold">Audit Report</h1>
          <p className="text-sm text-muted-foreground">
            Browser print is the PDF path for this report version.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={onDownloadJson}>
            <Download className="mr-2 h-4 w-4" />
            Download JSON
          </Button>
          <Button onClick={onPrint}>
            <Printer className="mr-2 h-4 w-4" />
            Export report
          </Button>
        </div>
      </div>

      <section className="report-sheet space-y-6 rounded-lg border bg-card p-6 print:rounded-none print:border-0 print:p-0">
        <header className="border-b pb-4">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">
            Generated {formatDateTime(payload.generatedAt)}
          </p>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="text-3xl font-semibold leading-tight">
                {payload.project.name}
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Project ID {payload.project.id}
                {payload.project.code ? ` · ${payload.project.code}` : ""}
              </p>
            </div>
            {payload.project.status ? (
              <Badge variant="outline">{payload.project.status}</Badge>
            ) : null}
          </div>
        </header>

        <section className="grid gap-4 md:grid-cols-3 print:grid-cols-3">
          <MetricCard
            label="Coherence Score"
            value={payload.score.label}
            detail={payload.score.scoreVersion ?? "Score version unavailable"}
          />
          <MetricCard
            label="Open Findings"
            value={String(payload.alertGroups.open.length)}
            detail="From project alert records"
          />
          <MetricCard
            label="Document Register"
            value={String(payload.documents.length)}
            detail="Uploaded project documents"
          />
        </section>

        {payload.score.reason ? (
          <p className="rounded-md bg-muted/40 p-3 text-sm">
            <span className="font-medium">Score reason: </span>
            {payload.score.reason}
          </p>
        ) : null}

        <Card className="print:break-inside-avoid">
          <CardHeader>
            <CardTitle>Coherence categories</CardTitle>
          </CardHeader>
          <CardContent>
            {payload.categoriesV2 ? (
              <CategoryV2Panel payload={payload.categoriesV2} />
            ) : (
              <p className="text-sm text-muted-foreground">
                Evidence-aware category detail is not available for this report.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="print:hidden">
          <CardHeader>
            <CardTitle>Report contents</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-5 text-sm">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeOpenFindings}
                onChange={(event) =>
                  onIncludeOpenFindingsChange(event.currentTarget.checked)
                }
              />
              Include open findings
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeRejectedFindings}
                onChange={(event) =>
                  onIncludeRejectedFindingsChange(event.currentTarget.checked)
                }
              />
              Include rejected findings
            </label>
          </CardContent>
        </Card>

        <Card className="print:break-inside-avoid">
          <CardHeader>
            <CardTitle>Findings</CardTitle>
          </CardHeader>
          <CardContent>
            {visibleAlerts.length > 0 ? (
              <div className="space-y-3">
                {visibleAlerts.map((alert) => (
                  <FindingRow key={alert.id} alert={alert} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No findings selected for this report.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="print:break-inside-avoid">
          <CardHeader>
            <CardTitle>Document register</CardTitle>
          </CardHeader>
          <CardContent>
            {payload.documents.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b text-xs uppercase text-muted-foreground">
                    <tr>
                      <th className="py-2 pr-3 font-medium">File</th>
                      <th className="py-2 pr-3 font-medium">Type</th>
                      <th className="py-2 pr-3 font-medium">Uploaded</th>
                      <th className="py-2 pr-3 font-medium">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {payload.documents.map((document) => (
                      <tr key={document.id} className="border-b last:border-b-0">
                        <td className="py-2 pr-3">{document.name}</td>
                        <td className="py-2 pr-3">{document.type}</td>
                        <td className="py-2 pr-3">
                          {document.uploadedAt
                            ? formatDateTime(document.uploadedAt)
                            : "Upload date unavailable"}
                        </td>
                        <td className="py-2 pr-3">
                          {document.status ?? "Status unavailable"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                No project documents are available for this report.
              </p>
            )}
          </CardContent>
        </Card>

        <Card className="print:break-inside-avoid">
          <CardHeader>
            <CardTitle>HITL decisions</CardTitle>
          </CardHeader>
          <CardContent>
            {payload.reviewDecisions.length > 0 ? (
              <div className="space-y-3">
                {payload.reviewDecisions.map((decision) => (
                  <div key={decision.id} className="rounded-md border p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{decision.status}</Badge>
                      <span>{decision.reviewer}</span>
                      <span className="text-muted-foreground">
                        {formatDateTime(decision.reviewedAt)}
                      </span>
                    </div>
                    {decision.summary ? (
                      <p className="mt-2 text-muted-foreground">{decision.summary}</p>
                    ) : null}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                HITL decisions require a project-scoped queue; the current client
                does not expose one for this report.
              </p>
            )}
          </CardContent>
        </Card>
      </section>
    </div>
  );
}

function MetricCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-md border bg-background p-4 print:break-inside-avoid">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-2 text-2xl font-semibold">{value}</p>
      <p className="mt-1 text-xs text-muted-foreground">{detail}</p>
    </div>
  );
}

function FindingRow({ alert }: { alert: ReportAlert }) {
  return (
    <article className="rounded-md border p-3 text-sm print:break-inside-avoid">
      <div className="flex flex-wrap items-center gap-2">
        <Badge variant="outline">{alert.status}</Badge>
        <Badge variant="secondary">{alert.severity}</Badge>
        <span className="font-medium">{alert.category}</span>
        <span className="text-muted-foreground">{formatDateTime(alert.createdAt)}</span>
      </div>
      <p className="mt-2">{alert.message}</p>
      {alert.evidenceReferences.length > 0 ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Evidence: {alert.evidenceReferences.join(" · ")}
        </p>
      ) : null}
      {alert.reviewedBy ? (
        <p className="mt-2 text-xs text-muted-foreground">
          Reviewed by {alert.reviewedBy}
          {alert.reviewedAt ? ` on ${formatDateTime(alert.reviewedAt)}` : ""}
        </p>
      ) : null}
    </article>
  );
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

const printStyles = `
@media print {
  @page {
    size: A4;
    margin: 16mm;
  }

  html, body {
    background: white !important;
  }

  body * {
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }

  .report-sheet {
    box-shadow: none !important;
  }
}
`;
