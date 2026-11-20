'use client';
import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { apiClient } from '@/lib/api/client';

type Finding = {
  finding_key: string; window_ordinal: number; title: string;
  clause_ref: string | null; source_quote: string | null;
  n2_quote_status: string; severity: string; review_state: string;
};
type WindowInfo = {
  ordinal: number; status: string; blocked_reason: string | null;
  unresolved_refs: string[]; has_result: boolean;
};
type N4Result = {
  status: string; total_findings: number | null; findings: Finding[];
  coverage: {total: number; windows_with_result: number; examined: number;
    blocked: number; windows: WindowInfo[]} | null;
};

export default function N4FindingsPage() {
  const {id: projectId, documentId} = useParams<{id:string; documentId:string}>();
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<N4Result | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(false);
    apiClient.get<N4Result>(
      `/projects/${projectId}/documents/${documentId}/n4-findings`,
      {params: {offset, limit: 100}},
    ).then(r => { if(active) setData(r.data); })
     .catch(() => { if(active) { setData(null); setError(true); } })
     .finally(() => { if(active) setLoading(false); });
    return () => { active = false; };
  }, [projectId, documentId, offset]);

  return <main className="mx-auto max-w-5xl space-y-6 p-6" data-testid="n4-findings-view">
    <Link href={`/projects/${projectId}/documents`} className="text-sm underline">Back to documents</Link>
    <h1 className="text-2xl font-semibold">N4 proposed findings</h1>
    <p className="text-sm text-muted-foreground">
      Read-only, not approved. N12 has not assessed these findings.
      N2 text matches do not certify the original PDF or contractual accuracy.
    </p>
    {loading ? <p role="status">Loading provisional findings…</p> :
      error ? <p role="alert">Findings unavailable or document revision superseded.</p> :
      data?.status === 'RESULTS_NOT_AVAILABLE' ?
        <p data-testid="n4-not-run">No N4 results are available. This does not mean zero risks.</p> :
      data ? <>
        <section className="space-y-3 rounded-xl border p-4" data-testid="n4-coverage">
          <Badge variant="outline">{data.status} — NOT APPROVABLE</Badge>
          <p>
            {data.coverage?.windows_with_result ?? 0}/{data.coverage?.total ?? 0} windows with persisted results;
            {' '}{data.coverage?.examined ?? 0} examined;
            {' '}{data.coverage?.blocked ?? 0} blocked.
          </p>
          <p className="text-xs text-muted-foreground">This is storage coverage, not verified contractual recall.</p>
          {data.coverage?.windows.filter(w => w.blocked_reason || w.unresolved_refs.length > 0).map(w =>
            <p key={w.ordinal} className="text-sm" data-testid="n4-unresolved">
              Window {w.ordinal + 1}: {w.blocked_reason || 'Unresolved reference'}.
              {' '}{w.unresolved_refs.join('; ')}
            </p>
          )}
        </section>
        <h2 className="text-lg font-medium">{data.total_findings ?? 'Uncounted'} proposed findings</h2>
        {data.findings.length === 0 && <p>No findings on this page. No zero-risk certification.</p>}
        {data.findings.map(f => <article key={f.finding_key} className="space-y-2 rounded-xl border p-4"
          data-testid="n4-proposed-finding">
          <div className="flex gap-2">
            <Badge variant="outline">PROPOSED</Badge>
            <Badge variant="outline">Severity: not assessed</Badge>
          </div>
          <h3 className="font-semibold">{f.title}</h3>
          <p className="text-sm">Clause: {f.clause_ref || 'not identified'} · Window {f.window_ordinal + 1}</p>
          {f.n2_quote_status === 'N2_EXACT_MATCH' && f.source_quote ?
            <blockquote className="border-l-2 pl-3 text-sm italic">{f.source_quote}</blockquote> :
            <p className="text-sm">Citation not located in the N2 text.</p>}
          <p className="text-xs text-muted-foreground">
            {f.n2_quote_status === 'N2_EXACT_MATCH'
              ? 'Quote located in N2; original PDF not verified.'
              : 'Source quotation not verified.'}
          </p>
        </article>)}
        <nav className="flex justify-between gap-4" aria-label="Finding pages">
          <Button variant="outline" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 100))}>
            Previous
          </Button>
          <Button variant="outline" disabled={data.total_findings === null || offset + 100 >= data.total_findings}
            onClick={() => setOffset(offset + 100)}>Next</Button>
        </nav>
      </> : null}
  </main>;
}
