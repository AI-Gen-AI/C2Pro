/**
 * TS-UT-PJ01-STATUS-001 — what the user sees vs. what the backend knows.
 *
 * PJ-01 processing assertions compare the browser-visible document label with the
 * backend stage of the same document. The polling API folds stored `parsed` and
 * `analyzed` into `status=parsed`; only `status_detail` (or `lifecycle_status` where
 * shipped) tells a finished analysis from a document whose analysis never started.
 */
import { describe, expect, it } from "vitest";

import {
  classifyBackendDocument,
  classifyUiDocumentLabel,
  extractStatusLabel,
  isTerminalStage,
} from "./status-model";

describe("extractStatusLabel", () => {
  it("finds the status label inside a whole documents-table row", () => {
    expect(extractStatusLabel("contract-a.pdf 5f0c… Contract Processing 3.9 KB 14/09/2026")).toBe("Processing");
    expect(extractStatusLabel("contract-a.pdf Contract Analysis pending 3.9 KB")).toBe("Analysis pending");
    expect(extractStatusLabel("contract-a.pdf\nContract\nAnalyzed\n3.9 KB")).toBe("Analyzed");
  });

  it("prefers the longest label so 'Analysis pending' is not read as something shorter", () => {
    expect(extractStatusLabel("Awaiting Analysis")).toBe("Awaiting Analysis");
  });

  it("returns null when the row carries no known status label", () => {
    expect(extractStatusLabel("contract-a.pdf Contract 3.9 KB")).toBeNull();
  });
});

describe("classifyUiDocumentLabel", () => {
  it.each([
    ["Analyzed", "success"],
    ["analysed", "success"],
    ["Uploaded", "in_flight"],
    ["Queued", "in_flight"],
    ["Processing", "in_flight"],
    ["Awaiting Analysis", "in_flight"],
    ["Analysis pending", "in_flight"],
    ["Parsed", "in_flight"],
    ["Error", "error"],
    ["Failed", "error"],
    ["", "unknown"],
    ["Something new", "unknown"],
  ] as const)("%j is %s", (label, expected) => {
    expect(classifyUiDocumentLabel(label)).toBe(expected);
  });
});

describe("classifyBackendDocument", () => {
  it("prefers lifecycle_status when the API ships it", () => {
    expect(classifyBackendDocument({ id: "d", status: "parsed", lifecycle_status: "analysis_pending" })).toBe(
      "parsed_pending_analysis",
    );
    expect(classifyBackendDocument({ id: "d", status: "parsed", lifecycle_status: "analyzed" })).toBe("analyzed");
  });

  it("separates a finished analysis from parsed-only using status_detail", () => {
    expect(
      classifyBackendDocument({ id: "d", status: "parsed", status_detail: "Document analysis completed." }),
    ).toBe("analyzed");
    expect(
      classifyBackendDocument({
        id: "d",
        status: "parsed",
        status_detail: "Document parsing and RAG ingestion completed. Analysis must be triggered separately.",
      }),
    ).toBe("parsed_pending_analysis");
  });

  it("maps the remaining polling statuses", () => {
    expect(classifyBackendDocument({ id: "d", status: "queued" })).toBe("queued");
    expect(classifyBackendDocument({ id: "d", status: "processing" })).toBe("processing");
    expect(classifyBackendDocument({ id: "d", status: "error" })).toBe("error");
    expect(classifyBackendDocument({ id: "d", status: "weird" })).toBe("unknown");
  });

  it("treats only analyzed and error as terminal", () => {
    expect(isTerminalStage("analyzed")).toBe(true);
    expect(isTerminalStage("error")).toBe(true);
    expect(isTerminalStage("parsed_pending_analysis")).toBe(false);
    expect(isTerminalStage("processing")).toBe(false);
  });
});
