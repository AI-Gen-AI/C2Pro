/**
 * S4: the EXACT original Budget row / Schedule activity a finding rests on.
 *
 * The API re-checks, in the signed-in user's tenant, that the reference still names the stored bytes (SHA-256), that
 * the revision is still the document's current one and that the original file still hashes to that SHA-256, and only
 * then returns the row re-parsed from those bytes. A stale, missing or foreign reference is refused WITHOUT content:
 * this panel then says so and never shows a guess. Nothing here is read from model text.
 */
"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { orvalApiClient } from "@/lib/api/client";

export type StructuredSourceRow = {
  family: "budget" | "schedule";
  document_id: string;
  revision_id: string;
  rev_no: number;
  source_locator: string;
  blob_sha256: string;
  authority: "TRUSTED_CURRENT" | "UNTRUSTED_SINGLE_REVISION";
  row: Record<string, unknown>;
  source_assessment: "NOT_ASSESSED";
};

const FAMILY_LABEL = { budget: "Budget row", schedule: "Schedule activity" } as const;

const REFUSAL: Record<string, string> = {
  stale_reference:
    "This reference is stale: it names bytes other than the stored revision, or the revision is no longer the document's current source.",
  source_unavailable:
    "The original row cannot be verified: the locator names no single row of the stored file, or the file no longer matches its SHA-256.",
};

function refusalFrom(error: unknown): string {
  if (isAxiosError(error)) {
    if (error.response?.status === 404) return "No such source in this workspace.";
    const code = (error.response?.data as { detail?: { code?: string } } | undefined)?.detail?.code;
    if (code && REFUSAL[code]) return REFUSAL[code];
  }
  return "The source reference could not be verified. Nothing is shown.";
}

export function StructuredSourceRowPanel({
  documentId,
  revisionId,
  locator,
  expectedBlobHash,
}: {
  documentId: string;
  revisionId: string;
  locator: string;
  expectedBlobHash?: string | null;
}) {
  const { orgId, userId, isLoaded } = useAuth();
  const query = useQuery({
    queryKey: ["structured-source-row", orgId ?? null, userId ?? null, documentId, revisionId, locator, expectedBlobHash ?? null],
    queryFn: () =>
      orvalApiClient<StructuredSourceRow>({
        url: `/api/v1/documents/${encodeURIComponent(documentId)}/revisions/${encodeURIComponent(revisionId)}/structured-source-rows`,
        method: "GET",
        params: { locator, ...(expectedBlobHash ? { expected_blob_hash: expectedBlobHash } : {}) },
      }),
    enabled: Boolean(isLoaded && userId),
    retry: false,
    staleTime: 0,
    refetchOnMount: "always",
  });

  return (
    <section
      data-testid="structured-source-row"
      aria-label="Original source row"
      className="rounded-xl border bg-card p-4 text-sm"
    >
      <h2 className="font-semibold">Original source row · {locator}</h2>
      {query.isLoading ? <p className="mt-2 text-muted-foreground">Verifying the original file…</p> : null}
      {query.isError ? (
        <p role="alert" data-testid="structured-source-refused" className="mt-2 text-destructive">
          {refusalFrom(query.error)}
        </p>
      ) : null}
      {query.isSuccess ? (
        <div className="mt-2 space-y-2">
          <p data-testid="structured-source-family">
            {FAMILY_LABEL[query.data.family]} · revision {query.data.rev_no}
          </p>
          <p className="text-muted-foreground">
            Revision <span className="font-mono">{query.data.revision_id}</span>
          </p>
          <p className="text-muted-foreground" data-testid="structured-source-sha">
            SHA-256 <span className="break-all font-mono">{query.data.blob_sha256}</span>
          </p>
          <p data-testid="structured-source-authority">
            {query.data.authority === "TRUSTED_CURRENT"
              ? "Source authority: trusted by a human and current."
              : "Source authority: current revision, NOT explicitly trusted by a human."}
          </p>
          <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1" data-testid="structured-source-cells">
            {Object.entries(query.data.row)
              .filter(([key]) => key !== "source_locator")
              .map(([key, value]) => (
                <div key={key} className="contents">
                  <dt className="text-muted-foreground">{key}</dt>
                  <dd className="font-mono">{value === null || value === undefined ? "—" : String(value)}</dd>
                </div>
              ))}
          </dl>
          <p className="text-xs text-muted-foreground">
            Re-read from the original bytes. Source content: NOT ASSESSED.
          </p>
        </div>
      ) : null}
    </section>
  );
}
