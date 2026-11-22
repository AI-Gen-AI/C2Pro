"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api/client";

/** A21: read-only N4 proposal. This endpoint is NOT the authorized HITL decision ledger. */
type Finding = {
  finding_key: string;
  window_ordinal: number;
  title: string;
  interpretation: string;
  clause_ref: string | null;
  source_quote: string | null;
  n2_quote_status: string;
  severity: string;
  review_state: string;
  dimension?: string | null;
  category?: string | null;
  page_number?: number | null;
  page_start?: number | null;
  page_end?: number | null;
  consequences?: string | null;
  consequence?: string | null;
};
type WindowInfo = {
  ordinal: number;
  status: string;
  blocked_reason: string | null;
  unresolved_refs: string[];
  has_result: boolean;
};
type N4Result = {
  status: string;
  total_findings: number | null;
  findings: Finding[];
  coverage: {
    total: number;
    windows_with_result: number;
    examined: number;
    blocked: number;
    windows: WindowInfo[];
  } | null;
};

const AREA_LABELS: Record<string, string> = {
  TIME: "Schedule",
  SCHEDULE: "Schedule",
  BUDGET: "Budget",
  COST: "Budget",
  SCOPE: "Scope",
  QUALITY: "Quality",
  LEGAL: "Contract conditions",
  CONTRACTUAL: "Contract conditions",
  SUPPLY_CHAIN: "Supply chain",
  PROCUREMENT: "Supply chain",
};

function businessArea(finding: Finding): string {
  const key = (finding.dimension || finding.category || "").trim().toUpperCase();
  return AREA_LABELS[key] ?? "Area not evaluated";
}

function brief(text: string | null | undefined): string {
  if (!text) return "The business impact has not been evaluated.";
  const normalized = text.replace(/\s+/g, " ").trim();
  if (normalized.length <= 190) return normalized;
  const stop = normalized.slice(0, 190).lastIndexOf(" ");
  return normalized.slice(0, Math.max(100, stop)).trimEnd() + "…";
}

function pageReference(finding: Finding): string {
  const start = finding.page_start ?? finding.page_number;
  const end = finding.page_end ?? start;
  if (typeof start !== "number" || !Number.isSafeInteger(start) || start < 1) {
    return "Page not established";
  }
  if (typeof end === "number" && Number.isSafeInteger(end) && end > start) {
    return "Pages " + start + "–" + end + " (not independently verified)";
  }
  return "Page " + start + " (not independently verified)";
}

function groupByBusinessArea(findings: Finding[]): Array<[string, Finding[]]> {
  const grouped = new Map<string, Finding[]>();
  for (const finding of findings) {
    const area = businessArea(finding);
    grouped.set(area, [...(grouped.get(area) ?? []), finding]);
  }
  return [...grouped.entries()].sort(([left], [right]) => left.localeCompare(right));
}

export default function N4FindingsPage() {
  const { id: projectId, documentId } = useParams<{ id: string; documentId: string }>();
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<N4Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);
    setData(null);
    apiClient.get<N4Result>(
      "/projects/" + projectId + "/documents/" + documentId + "/n4-findings",
      { params: { offset, limit: 100 } },
    ).then((response) => { if (active) setData(response.data); })
      .catch(() => { if (active) { setData(null); setError(true); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [projectId, documentId, offset]);

  const blocked = data?.coverage?.blocked ?? 0;
  const gaps = data?.coverage?.windows.filter((window) =>
    Boolean(window.blocked_reason || window.unresolved_refs.length > 0),
  ) ?? [];

  return (
    <main className="mx-auto max-w-5xl space-y-6 p-6" data-testid="n4-findings-view">
      <Link href={"/projects/" + projectId + "/documents"} className="text-sm underline">
        Back to documents
      </Link>
      <h1 className="text-2xl font-semibold">Contract findings requiring review</h1>
      <p className="text-sm text-muted-foreground">
        These are unapproved AI proposals, not confirmed contractual risks.
        A quotation found in extracted text does not verify the original PDF, its page, or the interpretation.
        Individual decisions must be made through the authorized review workflow.
      </p>

      {loading ? (
        <p role="status">Loading provisional findings…</p>
      ) : error ? (
        <p role="alert">Findings unavailable or document revision superseded. Access may also be restricted.</p>
      ) : data?.status === "RESULTS_NOT_AVAILABLE" ? (
        <p data-testid="n4-not-run">
          No analysis results are available. This does not mean zero risks; the document remains not evaluated.
        </p>
      ) : data ? (
        <>
          <section className="space-y-3 rounded-xl border p-4" data-testid="n4-coverage" aria-label="Analysis coverage and missing sections">
            <Badge variant="outline">Review required — analysis not validated</Badge>
            <p>
              {data.coverage?.examined ?? 0} sections examined; {blocked} sections blocked;
              {" "}{data.coverage?.windows_with_result ?? 0} of {data.coverage?.total ?? 0} sections with saved results.
            </p>
            <p className="text-xs text-muted-foreground">
              Saved results do not prove complete contractual coverage. Missing or unassessed sections remain open.
            </p>
            {gaps.length > 0 ? (
              <div className="space-y-2" role="status">
                <h2 className="font-medium">Sections requiring attention</h2>
                {gaps.map((window) => (
                  <p key={window.ordinal} className="text-sm" data-testid="n4-unresolved">
                    Section {window.ordinal + 1}: {window.blocked_reason ? "Analysis blocked" : "Reference pending"}.
                    {" "}{window.unresolved_refs.join("; ") || "Details not available"}.
                  </p>
                ))}
              </div>
            ) : null}
            <div className="flex flex-wrap gap-2">
              <Button type="button" variant="outline" disabled aria-disabled="true">
                Retry failed sections
              </Button>
              <Button type="button" variant="outline" disabled aria-disabled="true">
                Close gap manually
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              These actions require a verified server workflow and reviewer authorization. They cannot be completed from this read-only view.
            </p>
          </section>

          <section className="space-y-4" aria-label="Proposed findings by business area">
            <h2 className="text-lg font-medium">
              {data.total_findings ?? "Uncounted"} proposed findings
            </h2>
            {data.findings.length === 0 ? (
              <p>No findings on this page. The analysis has not certified zero risk.</p>
            ) : null}
            {groupByBusinessArea(data.findings).map(([area, findings]) => (
              <section key={area} className="space-y-3" aria-label={"Proposed findings: " + area}>
                <h3 className="text-base font-semibold">{area}</h3>
                <ul className="space-y-3">
                  {findings.map((finding) => {
                    const consequences = finding.consequences || finding.consequence;
                    const exact = finding.n2_quote_status === "N2_EXACT_MATCH" &&
                      typeof finding.source_quote === "string" && finding.source_quote.trim().length > 0;
                    return (
                      <li key={finding.finding_key}>
                        <article className="space-y-2 rounded-xl border p-4" data-testid="n4-proposed-finding">
                          <div className="flex flex-wrap gap-2">
                            <Badge variant="outline">Proposed, not approved</Badge>
                            <Badge variant="outline">Severity not evaluated</Badge>
                          </div>
                          <h4 className="font-semibold">{finding.title}</h4>
                          <p className="text-sm" data-testid="n4-risk-interpretation">
                            <span className="font-medium">Business summary (AI proposal): </span>
                            {brief(finding.interpretation)}
                          </p>
                          <p className="text-sm">
                            <span className="font-medium">Possible consequences (not validated): </span>
                            {consequences || "Not assessed."}
                          </p>
                          <p className="text-sm">
                            Clause {finding.clause_ref?.trim() || "not established"} · {pageReference(finding)}
                          </p>
                          <details className="rounded border border-dashed p-3 text-sm">
                            <summary className="cursor-pointer font-medium">
                              Review full analysis, clause and source evidence
                            </summary>
                            <div className="mt-3 space-y-2">
                              <p className="whitespace-pre-wrap">Full AI interpretation: {finding.interpretation || "Not assessed."}</p>
                              {exact ? (
                                <>
                                  <blockquote className="border-l-2 pl-3 italic">{finding.source_quote}</blockquote>
                                  <p className="text-xs text-muted-foreground">
                                    Quote located in extracted text only; original PDF and page not verified.
                                  </p>
                                </>
                              ) : (
                                <p>Source quotation not verified. No unverified candidate text is presented as an exact quote.</p>
                              )}
                            </div>
                          </details>
                        </article>
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
          </section>

          <nav className="flex justify-between gap-4" aria-label="Finding pages">
            <Button variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>
              Previous
            </Button>
            <Button variant="outline" disabled={data.total_findings === null || offset + 100 >= data.total_findings}
              onClick={() => setOffset(offset + 100)}>Next</Button>
          </nav>
        </>
      ) : null}
    </main>
  );
}
