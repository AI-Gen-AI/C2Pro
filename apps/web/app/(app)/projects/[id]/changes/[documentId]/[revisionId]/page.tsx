"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, FileSearch } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";

type Change = { anchor?: string; semantic_summary?: string; before?: Record<string, unknown> | null; after?: Record<string, unknown> | null; evidence_refs?: Array<{ locator?: string; source?: string }> };
type Detail = { changes: Change[]; state: string; change_cause: string | null; confidence: number | null; evidence_refs: Array<{ locator?: string; source?: string }> };

export default function ChangeDetailPage() {
  const { id: projectId, documentId, revisionId } = useParams<{ id: string; documentId: string; revisionId: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["revision-change", projectId, documentId, revisionId],
    queryFn: async () => (await apiClient.get<Detail>(`/projects/${projectId}/documents/${documentId}/changes/${revisionId}`)).data,
  });
  if (isLoading) return <div className="py-24 text-center text-muted-foreground">Loading evidence…</div>;
  if (error || !data) return <div className="py-24 text-center text-destructive">This change detail is unavailable.</div>;
  return <div className="space-y-5" data-testid="change-detail-page">
    <Link className="inline-flex items-center text-sm text-muted-foreground hover:text-foreground" href={`/projects/${projectId}/changes`}><ArrowLeft className="mr-1 h-4 w-4" />Back to What Changed?</Link>
    <div><h1 className="text-3xl font-bold tracking-tight">Change evidence</h1><p className="text-muted-foreground">{data.change_cause ?? "No material change"} · {data.confidence == null ? "confidence unavailable" : `${Math.round(data.confidence * 100)}% confidence`}</p></div>
    {data.changes.length === 0 ? <Card><CardContent className="pt-6 text-muted-foreground">The comparison completed with no material differences.</CardContent></Card> : data.changes.map((change, index) => <Card key={`${change.anchor ?? "change"}-${index}`}><CardHeader><CardTitle className="text-base">{change.anchor ?? "Revision change"}</CardTitle><p className="text-sm text-muted-foreground">{change.semantic_summary ?? "Structural change detected"}</p></CardHeader><CardContent className="grid gap-4 md:grid-cols-2"><EvidenceSide title="Before" value={change.before} /><EvidenceSide title="After" value={change.after} /><div className="md:col-span-2 text-sm text-muted-foreground"><FileSearch className="mr-1 inline h-4 w-4" />{(change.evidence_refs ?? data.evidence_refs).map((ref) => `${ref.source ?? "source"}: ${ref.locator ?? "anchor"}`).join(" · ") || "Source evidence unavailable"}</div></CardContent></Card>)}
  </div>;
}

function EvidenceSide({ title, value }: { title: string; value: Record<string, unknown> | null | undefined }) {
  return <section className="rounded-md border p-3"><h2 className="mb-2 text-sm font-semibold">{title}</h2><pre className="whitespace-pre-wrap break-words text-xs text-muted-foreground">{value ? String(value.full_text ?? JSON.stringify(value, null, 2)) : "Not present"}</pre></section>;
}
