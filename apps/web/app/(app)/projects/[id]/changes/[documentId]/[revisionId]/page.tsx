"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, FileSearch, History, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";

type Change = { anchor?: string; semantic_summary?: string; needs_review?: boolean; match_rationale?: string | null; before?: Record<string, unknown> | null; after?: Record<string, unknown> | null; evidence_refs?: Array<{ locator?: string; source?: string }> };
type ImpactItem = { target: { entity_type: string; potentially_stale?: boolean | null }; status: "CONFIRMED" | "CANDIDATE" };
type ChangeImpact = { change_index: number; assessment: { status: "CONFIRMED" | "CANDIDATE" | "UNKNOWN"; items: ImpactItem[]; reason?: string | null } };
type Projection = { status: "none" | "provisional" | "unavailable"; projected_score?: number | null; projected_delta?: number | null; qualification?: string | null; reason?: string | null };
type Lineage = { event_id?: string; occurred_at?: string; event_type?: string; state?: string; derivation?: "original" | "recomputed" | "reinterpreted" | null; derived_from_event_id?: string | null; effective?: boolean | null; superseded_by_event_id?: string | null; matcher_status?: string | null; provenance?: { diff_engine_version?: string; recomputed_from_engine?: string } };
type Materialization = { state: string; scope?: string | null; qualifications: string[]; deferred_effects?: Record<string, unknown> };
type RevisionStatus = { status: "available" | "unavailable"; rev_no?: number | null; trust_state?: "proposed" | "trusted" | "rejected" | "superseded" | null; is_current: boolean; current_revision_id?: string | null; materialization?: Materialization | null };
type Detail = Lineage & { changes: Change[]; state: string; change_cause: string | null; confidence: number | null; evidence_refs: Array<{ locator?: string; source?: string }>; qualification_reason?: string | null; impacts?: ChangeImpact[]; projection?: Projection | null; history?: Lineage[]; revision_status?: RevisionStatus | null };

export default function ChangeDetailPage() {
  const { id: projectId, documentId, revisionId } = useParams<{ id: string; documentId: string; revisionId: string }>();
  // ?event=<id> reads one specific (possibly historical) comparison of this revision.
  const eventId = useSearchParams()?.get("event") ?? null;
  const base = `/projects/${projectId}/changes/${documentId}/${revisionId}`;
  const { data, isLoading, error } = useQuery({
    queryKey: ["revision-change", projectId, documentId, revisionId, eventId],
    queryFn: async () => (await apiClient.get<Detail>(`/projects/${projectId}/documents/${documentId}/changes/${revisionId}`, eventId ? { params: { event_id: eventId } } : undefined)).data,
  });
  if (isLoading) return <div className="py-24 text-center text-muted-foreground">Loading evidence…</div>;
  if (error || !data) return <div className="py-24 text-center text-destructive">This change detail is unavailable.</div>;
  return <div className="space-y-5" data-testid="change-detail-page">
    <Link className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground" href={`/projects/${projectId}/changes`}><ArrowLeft className="mr-1 h-4 w-4" />Back to What Changed?</Link>
    <div><h1 className="text-3xl font-bold tracking-tight">Change evidence</h1>{data.state === "needs_review" ? <ReviewBadge testId="change-detail-state" /> : null}<p className="text-muted-foreground">{data.change_cause ?? "No material change"} · {data.confidence == null ? "confidence unavailable" : `${Math.round(data.confidence * 100)}% confidence`}</p>{data.qualification_reason ? <p className="text-sm text-muted-foreground" data-testid="change-detail-qualification">{data.qualification_reason}</p> : null}</div>
    <LineageNote detail={data} currentHref={base} />
    <RevisionStatusCard status={data.revision_status} />
    <ProjectionNote projection={data.projection} />
    {data.changes.length === 0 ? <Card><CardContent className="pt-6 text-muted-foreground">The comparison completed with no material differences.</CardContent></Card> : data.changes.map((change, index) => <Card key={`${change.anchor ?? "change"}-${index}`} data-testid={`change-${index}`}><CardHeader><CardTitle className="text-base">{change.anchor ?? "Revision change"}</CardTitle><p className="text-sm text-muted-foreground">{change.semantic_summary ?? "Structural change detected"}</p>{change.needs_review ? <div className="space-y-1"><ReviewBadge /><p className="text-sm text-muted-foreground">{change.match_rationale ?? "This pairing of clauses across revisions is not established."}</p></div> : null}</CardHeader><CardContent className="grid gap-4 md:grid-cols-2"><EvidenceSide title="Before" value={change.before} /><EvidenceSide title="After" value={change.after} /><ImpactPanel index={index} impact={data.impacts?.find((entry) => entry.change_index === index)} /><div className="md:col-span-2 text-sm text-muted-foreground"><FileSearch className="mr-1 inline h-4 w-4" />{(change.evidence_refs ?? data.evidence_refs).map((ref) => `${ref.source ?? "source"}: ${ref.locator ?? "anchor"}`).join(" · ") || "Source evidence unavailable"}</div></CardContent></Card>)}
    <OutcomeHistory history={data.history} shown={data.event_id} base={base} />
  </div>;
}

// A superseded comparison stays inspectable but is never presented as the current result.
function LineageNote({ detail, currentHref }: { detail: Detail; currentHref: string }) {
  if (detail.effective === false) {
    // A failed newer analysis leaves no current comparison: say so instead of linking back here.
    const failed = detail.history?.find((entry) => entry.event_id === detail.superseded_by_event_id)?.event_type === "revision.analysis_failed";
    return <Card data-testid="change-detail-historical"><CardContent className="flex flex-wrap items-center gap-2 pt-6 text-sm">
      <Badge variant="outline"><History className="mr-1 h-3 w-3" />Historical — superseded</Badge>
      {failed
        ? <span className="text-muted-foreground">A newer analysis of this revision failed, so there is no current comparison; this one is kept as history only.</span>
        : <><span className="text-muted-foreground">A newer result replaces this comparison; it is kept as history only.</span>
          <Link className="font-medium text-primary hover:underline" href={currentHref}>View the current result</Link></>}
    </CardContent></Card>;
  }
  if (detail.derivation === "recomputed") {
    return <Card data-testid="change-detail-recomputed"><CardContent className="flex flex-wrap items-center gap-2 pt-6 text-sm">
      <Badge variant="secondary">Recomputed · current matcher</Badge>
      <span className="text-muted-foreground">Recomputed from an earlier comparison{detail.provenance?.recomputed_from_engine ? ` made by ${detail.provenance.recomputed_from_engine}` : ""}, over the same revision evidence. The original stays in the history.</span>
    </CardContent></Card>;
  }
  return null;
}

const TRUST_LABEL = {
  trusted: "Trusted",
  proposed: "Awaiting review — the previously trusted revision stays current",
  rejected: "Rejected — kept as history",
  superseded: "Superseded — kept as history",
} as const;

const MATERIALIZATION_LABEL: Record<string, string> = {
  materialized: "All effects currently authorized by governance were applied.",
  pending: "Approved — applying the effects governance authorizes.",
  operator_required: "Approved — applying its effects needs operator attention.",
  obsolete: "Not applied — a newer trusted revision superseded it first.",
};

const QUALIFICATION_LABEL: Record<string, string> = {
  WBS_GOVERNANCE_REQUIRED: "WBS proposal awaiting governed review — not part of the canonical WBS.",
  RISK_ALERT_RECONCILIATION_REQUIRED: "Risk alerts are not reconciled across revisions.",
};

// Trust, currency and materialization come from their own authorities; this card only reports them.
function RevisionStatusCard({ status }: { status: RevisionStatus | null | undefined }) {
  if (!status) return null;
  if (status.status === "unavailable") {
    return <Card data-testid="revision-status"><CardContent className="pt-6 text-sm text-muted-foreground">Revision status unavailable.</CardContent></Card>;
  }
  const materialization = status.materialization;
  const outcome = materialization ? MATERIALIZATION_LABEL[materialization.state] : undefined;
  return <Card data-testid="revision-status"><CardContent className="space-y-2 pt-6 text-sm">
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant={status.is_current ? "success" : "outline"} data-testid="revision-currency">{status.is_current ? <><ShieldCheck className="mr-1 h-3 w-3" />Current revision</> : "Not the current revision"}</Badge>
      <span className="text-muted-foreground" data-testid="revision-trust">{status.trust_state ? TRUST_LABEL[status.trust_state] : "No analysis result is bound to this revision."}</span>
    </div>
    {outcome ? <p data-testid="revision-materialization">{outcome}</p> : null}
    {materialization?.qualifications.map((code) => <p key={code} className="text-muted-foreground" data-testid={`revision-qualification-${code}`}>{QUALIFICATION_LABEL[code] ?? code}</p>)}
  </CardContent></Card>;
}

const DERIVATION_LABEL = { original: "Comparison", recomputed: "Recomputed comparison", reinterpreted: "Reinterpretation" } as const;

function OutcomeHistory({ history, shown, base }: { history: Lineage[] | undefined; shown: string | undefined; base: string }) {
  if (!history || history.length < 2) return null;
  return <Card data-testid="change-history"><CardHeader><CardTitle className="text-base">Result history</CardTitle></CardHeader><CardContent className="space-y-2 text-sm">
    {history.map((entry) => <div key={entry.event_id} className="flex flex-wrap items-center gap-2" data-testid={`history-${entry.event_id}`}>
      <span>{entry.event_type === "revision.analysis_failed" ? "Failed analysis" : DERIVATION_LABEL[entry.derivation ?? "original"]}</span>
      <span className="text-muted-foreground">{entry.occurred_at ? new Date(entry.occurred_at).toLocaleString() : ""}{entry.provenance?.diff_engine_version ? ` · ${entry.provenance.diff_engine_version}` : ""}</span>
      {entry.effective ? <Badge variant="success">Current result</Badge> : <Badge variant="outline">Historical</Badge>}
      {entry.event_id === shown ? <span className="text-muted-foreground">(shown)</span> : entry.event_type !== "revision.analysis_failed" ? <Link className="text-primary hover:underline" href={`${base}?event=${entry.event_id}`}>View</Link> : null}
    </div>)}
  </CardContent></Card>;
}

// A change that needs review is a proposal: its clause pairing across revisions is not established.
function ReviewBadge({ testId }: { testId?: string }) {
  return <Badge variant="warning" data-testid={testId}><AlertTriangle className="mr-1 h-3 w-3" />Needs review</Badge>;
}

function EvidenceSide({ title, value }: { title: string; value: Record<string, unknown> | null | undefined }) {
  return <section className="rounded-md border p-3"><h2 className="mb-2 text-sm font-semibold">{title}</h2><pre className="whitespace-pre-wrap break-words text-xs text-muted-foreground">{value ? String(value.full_text ?? JSON.stringify(value, null, 2)) : "Not present"}</pre></section>;
}

const IMPACT_LABEL = { CONFIRMED: "Confirmed impact", CANDIDATE: "Candidate impact", UNKNOWN: "Impact unknown" } as const;

// Derived from persisted links only; UNKNOWN never lists targets. Stale alerts are flagged, never changed.
function ImpactPanel({ index, impact }: { index: number; impact: ChangeImpact | undefined }) {
  if (!impact) return null;
  const { status, items, reason } = impact.assessment;
  const stale = items.filter((item) => item.target.entity_type === "alert" && item.target.potentially_stale).length;
  return <div className="md:col-span-2 flex flex-wrap items-center gap-2 text-sm" data-testid={`change-impact-${index}`}>
    <Badge variant={status === "CONFIRMED" ? "secondary" : "outline"}>{IMPACT_LABEL[status]}</Badge>
    {status === "UNKNOWN" ? <span className="text-muted-foreground">{reason ?? "No persisted relationship is known."}</span> : <span className="text-muted-foreground">{items.length} linked {items.length === 1 ? "entity" : "entities"}</span>}
    {stale ? <span className="text-muted-foreground">· {stale} {stale === 1 ? "alert" : "alerts"} may be stale</span> : null}
  </div>;
}

// A projection is hypothetical: it never replaces the trusted Coherence score.
function ProjectionNote({ projection }: { projection: Projection | null | undefined }) {
  if (!projection || projection.status === "none") return null;
  const unverified = projection.qualification === "provisional_unverified_temporal_identity";
  return <Card data-testid="change-detail-projection"><CardContent className="pt-6 text-sm text-muted-foreground">
    {projection.status === "provisional" && projection.projected_score != null
      ? <>Projected Coherence (provisional): {projection.projected_score}{projection.projected_delta != null ? ` (${projection.projected_delta > 0 ? "+" : ""}${projection.projected_delta})` : ""} — if this revision is approved.</>
      : <>Projected Coherence unavailable{projection.reason ? `: ${projection.reason}` : "."}</>}
    {unverified ? <span> Based on an unverified temporal identity.</span> : null}
  </CardContent></Card>;
}
