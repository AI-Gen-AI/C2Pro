/**
 * PJ-01 document status model: what the user sees vs. what the backend knows.
 *
 * Pure (no Playwright): shared by the browser harness and its unit tests.
 */

/** How a browser-visible document status label reads to a user. */
export type UiDocumentState = "in_flight" | "success" | "error" | "unknown";

/** The backend stage of one document, recovered from the documents list API. */
export type BackendDocumentStage =
  | "queued"
  | "processing"
  | "parsed_pending_analysis"
  | "analyzed"
  | "error"
  | "unknown";

/** One item of `GET /api/v1/projects/{id}/documents`, as far as PJ-01 reads it. */
export interface PolledDocument {
  id: string;
  status?: string | null;
  status_detail?: string | null;
  /** Additive, honest lifecycle (F-DOC-1); absent on builds that do not ship it. */
  lifecycle_status?: string | null;
}

const SUCCESS_LABEL = /^analy[sz]ed$/i;
const IN_FLIGHT_LABEL = /^(uploaded|queued|processing|parsing|awaiting analysis|analysis pending)$/i;
const ERROR_LABEL = /^(error|failed)$/i;

export function classifyUiDocumentLabel(label: string): UiDocumentState {
  const text = label.trim();
  if (SUCCESS_LABEL.test(text)) return "success";
  if (IN_FLIGHT_LABEL.test(text)) return "in_flight";
  if (ERROR_LABEL.test(text)) return "error";
  return "unknown";
}

const LIFECYCLE_STAGE: Record<string, BackendDocumentStage> = {
  uploaded: "queued",
  queued: "queued",
  processing: "processing",
  parsing: "processing",
  parsed: "parsed_pending_analysis",
  analysis_pending: "parsed_pending_analysis",
  analyzed: "analyzed",
  error: "error",
};

/**
 * The polling `status` folds stored `parsed` AND `analyzed` into `parsed`
 * (`_normalize_document_status_for_polling`); only `status_detail` distinguishes a finished
 * analysis ("Document analysis completed.") from a parse whose analysis never started.
 */
const ANALYSIS_COMPLETED_DETAIL = /analysis completed/i;

export function classifyBackendDocument(document: PolledDocument): BackendDocumentStage {
  const lifecycle = document.lifecycle_status?.trim().toLowerCase();
  if (lifecycle && lifecycle in LIFECYCLE_STAGE) return LIFECYCLE_STAGE[lifecycle];

  switch (document.status?.trim().toLowerCase()) {
    case "queued":
    case "uploaded":
      return "queued";
    case "processing":
    case "parsing":
      return "processing";
    case "error":
      return "error";
    case "analyzed":
      return "analyzed";
    case "parsed":
      return ANALYSIS_COMPLETED_DETAIL.test(document.status_detail ?? "") ? "analyzed" : "parsed_pending_analysis";
    default:
      return "unknown";
  }
}

export function isTerminalStage(stage: BackendDocumentStage): boolean {
  return stage === "analyzed" || stage === "error";
}
