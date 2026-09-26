"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock3, FileSearch, GitCompareArrows, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiClient } from "@/lib/api/client";

type ChangeItem = {
  event_id: string;
  occurred_at: string;
  event_type: string;
  state: "processing" | "ready" | "needs_review" | "error";
  change_cause: "BUSINESS_STATE_CHANGED" | "NEWLY_DISCOVERED" | null;
  confidence: number | null;
  document_id: string | null;
  provenance: { target_revision_id?: string; diff_engine_version?: string };
};

type Timeline = { items: ChangeItem[]; next_cursor: string | null };

function stateBadge(item: ChangeItem) {
  if (item.state === "processing") return <Badge variant="secondary"><Clock3 className="mr-1 h-3 w-3" />Processing</Badge>;
  if (item.state === "needs_review") return <Badge variant="warning"><AlertTriangle className="mr-1 h-3 w-3" />Needs review</Badge>;
  if (item.state === "error") return <Badge variant="destructive">Analysis error</Badge>;
  if (item.change_cause === "NEWLY_DISCOVERED") return <Badge variant="secondary"><Sparkles className="mr-1 h-3 w-3" />Newly discovered</Badge>;
  if (item.change_cause === "BUSINESS_STATE_CHANGED") return <Badge variant="success"><GitCompareArrows className="mr-1 h-3 w-3" />Business state changed</Badge>;
  return <Badge variant="outline"><CheckCircle2 className="mr-1 h-3 w-3" />No change</Badge>;
}

// An error, a pending review or an unfinished comparison is never "no material change":
// that title is reserved for a completed comparison that found no change cause.
function itemTitle(item: ChangeItem): string {
  if (item.state === "error") return "Revision analysis failed";
  if (item.state === "needs_review") return "Change needs review";
  if (item.state === "processing") return "Revision is being compared";
  if (item.change_cause === "NEWLY_DISCOVERED") return "C2Pro learned something new";
  if (item.change_cause === "BUSINESS_STATE_CHANGED") return "Project evidence changed";
  return "No material change found";
}

export default function ProjectChangesPage() {
  const { id: projectId } = useParams<{ id: string }>();
  const { data, isLoading, error } = useQuery({
    queryKey: ["project-timeline", projectId],
    queryFn: async () => (await apiClient.get<Timeline>(`/projects/${projectId}/timeline`)).data,
    enabled: Boolean(projectId),
    refetchInterval: (query) => query.state.data?.items.some((item) => item.state === "processing") ? 5000 : false,
  });

  if (isLoading) return <div className="py-24 text-center text-muted-foreground">Loading change history…</div>;
  if (error) return <div className="py-24 text-center text-destructive">We could not load this project’s change history.</div>;
  if (!data?.items.length) {
    return <EmptyState title="No history yet" body="Upload and analyse a baseline document, then upload a revision to see evidence-grounded changes here." />;
  }

  return (
    <div className="space-y-5" data-testid="project-changes-page">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">What Changed?</h1>
        <p className="mt-1 text-muted-foreground">A revision-by-revision record of what changed, when, why, and the source evidence.</p>
      </div>
      <div className="space-y-3">
        {data.items.map((item) => {
          const detailHref = item.document_id && item.provenance.target_revision_id
            ? `/projects/${projectId}/changes/${item.document_id}/${item.provenance.target_revision_id}`
            : null;
          return (
            <Card key={item.event_id} data-testid={`change-item-${item.event_id}`}>
              <CardHeader className="gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <CardTitle className="text-base">{itemTitle(item)}</CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">{new Date(item.occurred_at).toLocaleString()} · {item.provenance.diff_engine_version ?? "analysis pending"}</p>
                </div>
                {stateBadge(item)}
              </CardHeader>
              <CardContent className="flex flex-wrap items-center justify-between gap-3">
                <span className="text-sm text-muted-foreground">{item.confidence == null ? "Confidence unavailable" : `${Math.round(item.confidence * 100)}% confidence`}</span>
                {detailHref ? <Link className="text-sm font-medium text-primary hover:underline" href={detailHref}><FileSearch className="mr-1 inline h-4 w-4" />View before, after & evidence</Link> : null}
              </CardContent>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

function EmptyState({ title, body }: { title: string; body: string }) {
  return <Card className="mx-auto mt-12 max-w-2xl text-center"><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent className="text-muted-foreground">{body}</CardContent></Card>;
}
