import type { AlertStructuredSource } from "@/components/features/alerts/AlertReviewCenter";

export interface StructuredSourceWire {
  family: string;
  document_id: string;
  revision_id: string;
  source_locator: string;
  blob_sha256?: string | null;
}

/**
 * S4: the pointers an alert carries to the ORIGINAL Budget rows / Schedule activities it rests on. Only well-formed
 * pointers survive (a structured family, a document, a revision and an exact locator); a malformed one is dropped,
 * never repaired or invented. The API re-verifies each one (tenant, bytes, authority) before showing any cell.
 */
export function structuredSourcesOf(raw: StructuredSourceWire[] | null | undefined): AlertStructuredSource[] {
  return (raw ?? [])
    .filter(
      (ref) =>
        (ref.family === "budget" || ref.family === "schedule") &&
        Boolean(ref.document_id && ref.revision_id && ref.source_locator),
    )
    .map((ref) => ({
      family: ref.family as "budget" | "schedule",
      documentId: ref.document_id,
      revisionId: ref.revision_id,
      sourceLocator: ref.source_locator,
      ...(ref.blob_sha256 ? { blobSha256: ref.blob_sha256 } : {}),
    }));
}
