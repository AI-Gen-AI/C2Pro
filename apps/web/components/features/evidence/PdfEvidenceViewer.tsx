/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { env } from "@/config/env";
import { resolveHighlightStyle } from "@/components/features/evidence/highlight-style";
import { createWatermarkToken } from "@/components/features/evidence/watermark-token";
import { sanitizeWatermarkPayload } from "@/components/features/evidence/watermark-sanitize";
import { EvidenceWatermarkOverlay } from "@/components/features/evidence/EvidenceWatermarkOverlay";
import { PDFViewer } from "@/components/evidence/pdf/PDFViewer";
import { useAuthStore } from "@/stores/auth";

export interface PdfHighlight {
  id: string;
  clauseId: string;
  page: number;
  text: string;
  severity: "critical" | "high" | "medium" | "low";
}

interface PdfEvidenceViewerProps {
  fileUrl: string;
  highlights: PdfHighlight[];
  activeHighlightId: string | null;
  onHighlightClick: (id: string) => void;
}

const WATERMARK_STORAGE_KEY = "s3-03-watermark-state";

function readStoredDemoWatermark() {
  if (typeof window === "undefined") {
    return null;
  }

  const stored = window.sessionStorage.getItem(WATERMARK_STORAGE_KEY);
  if (!stored) {
    return null;
  }

  try {
    const parsed = JSON.parse(stored) as Record<string, unknown>;
    const safeStored = sanitizeWatermarkPayload(parsed);
    return safeStored.pseudonymId ? safeStored : null;
  } catch {
    return null;
  }
}

export function PdfEvidenceViewer({
  fileUrl,
  highlights,
  activeHighlightId,
  onHighlightClick,
}: PdfEvidenceViewerProps) {
  const [isPdfReady, setIsPdfReady] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(activeHighlightId);
  const [statePage, setStatePage] = useState(1);
  const lastExternalCitationRef = useRef<string | null>(null);
  const [currentFileUrl, setCurrentFileUrl] = useState(fileUrl);
  const [currentHighlights, setCurrentHighlights] =
    useState<PdfHighlight[]>(highlights);

  // The document download endpoint is authenticated; pdf.js must send the bearer
  // token or the fetch 401s ("Error loading PDF"). Same token the API client uses.
  const authToken = useAuthStore((state) => state.token);
  const pdfHttpHeaders = useMemo(
    () => (authToken ? { Authorization: `Bearer ${authToken}` } : undefined),
    [authToken],
  );

  const isDemo = env.APP_MODE === "demo";

  const [watermark] = useState(() => {
    const stored = isDemo ? readStoredDemoWatermark() : null;
    if (stored) return stored;
    
    return sanitizeWatermarkPayload({
      pseudonymId: createWatermarkToken({
        tenantId: isDemo ? "tenant-demo" : "tenant-prod",
        userSeed: "session-user",
        sessionNonce: "evidence-viewer",
      }),
      environment: isDemo ? "local" : "production",
      timestampIso: new Date().toISOString(),
    });
  });

  useEffect(() => {
    const timer = setTimeout(() => setIsPdfReady(true), 0);
    return () => clearTimeout(timer);
  }, []);

   useEffect(() => {
    if (fileUrl !== currentFileUrl) {
      setCurrentFileUrl(fileUrl);
      setStatePage(1);
      setActiveId(null);
      lastExternalCitationRef.current = null;
      setCurrentHighlights(highlights);
    }
  }, [fileUrl, highlights]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      if (isDemo && watermark.pseudonymId) {
        window.sessionStorage.setItem(
          WATERMARK_STORAGE_KEY,
          JSON.stringify(watermark),
        );
      } else {
        window.sessionStorage.removeItem(WATERMARK_STORAGE_KEY);
      }
    }
  }, [isDemo, watermark]);

  const activeHighlights = useMemo(() => {
    // Production citations may arrive after the PDF mounts or change while
    // the revision URL remains identical. Use the latest parent evidence for
    // the exact URL; retain the local list only for the demo-only document B
    // switch. Never display stale citations from a previous prop snapshot.
    const evidenceForFile =
      currentFileUrl === fileUrl ? highlights : currentHighlights;
    if (evidenceForFile.length > 0) {
      return evidenceForFile;
    }
    // Only allow demo fallback in demo mode
    if (isDemo && currentFileUrl.includes("doc-b")) {
      return [
        {
          id: "hb",
          clauseId: "b-1",
          page: 1,
          text: "B",
          severity: "high" as const,
        },
      ];
    }
    return [];
  }, [currentFileUrl, currentHighlights, fileUrl, highlights, isDemo]);

  // A source deep link may be pinned to a PDF page other than page 1.
  // Resolve ONLY a source highlight belonging to this exact file's current
  // evidence list. Do not infer a page from unknown/document-fallback links.
  // PDFViewer tracks changes to initialPage and navigates its rendered Page.
  useEffect(() => {
    if (currentFileUrl !== fileUrl) return;
    const cited = activeHighlightId
      ? highlights.find((item) => item.id === activeHighlightId)
      : undefined;
    if (!cited || !Number.isSafeInteger(cited.page) || cited.page < 1) {
      // Only clear a PRIOR external deep-link selection. Do not clear an
      // internally clicked clause when the parent has never supplied an
      // activeHighlightId (S3-01 clickable alert regression).
      if (lastExternalCitationRef.current !== null) {
        lastExternalCitationRef.current = null;
        setActiveId(null);
        setStatePage(1);
      }
      return;
    }
    lastExternalCitationRef.current = cited.id;
    setActiveId(cited.id);
    setStatePage(cited.page);
  }, [activeHighlightId, currentFileUrl, fileUrl, highlights]);

  // A locally clicked citation (no parent activeHighlightId) must not outlive
  // its evidence: when the same revision URL's highlights are replaced or
  // cleared without it, drop the selection and its page. A citation that is
  // still present keeps its selection, and a resolvable parent citation is
  // owned by the deep-link effect above.
  useEffect(() => {
    if (currentFileUrl !== fileUrl || activeId === null) return;
    const ids = new Set(highlights.map((item) => item.id));
    if (ids.has(activeId)) return;
    if (activeHighlightId !== null && ids.has(activeHighlightId)) return;
    setActiveId(null);
    setStatePage(1);
  }, [activeHighlightId, activeId, currentFileUrl, fileUrl, highlights]);

  const handleEvidenceClick = (clauseId: string) => {
    const match = activeHighlights.find((item) => item.clauseId === clauseId);
    if (!match) return;
    setActiveId(match.id);
    setStatePage(match.page);
    onHighlightClick(match.id);
  };

  const handleSwitchDocument = () => {
    setCurrentFileUrl("/contracts/doc-b.pdf");
    setStatePage(1);
    setActiveId("hb");
    setCurrentHighlights([
      {
        id: "hb",
        clauseId: "b-1",
        page: 1,
        text: "B",
        severity: "high",
      },
    ]);
  };

  // Fail-closed validation for production mode
  const isMissingFile = !fileUrl || fileUrl === "";

  if (isMissingFile && !isDemo) {
    return (
      <div className="flex h-64 flex-col items-center justify-center rounded-lg border-2 border-dashed border-destructive/20 bg-destructive/5 p-8 text-center">
        <div className="mb-2 text-lg font-semibold text-destructive">
          Evidence Not Found
        </div>
        <p className="text-sm text-muted-foreground">
          The requested document evidence could not be retrieved from secure
          storage. Please verify the document exists and you have the necessary
          permissions.
        </p>
      </div>
    );
  }

  return (
    <section aria-label="PDF Evidence Viewer" className="text-primary-text">
      <EvidenceWatermarkOverlay watermark={watermark} />
      {!isPdfReady ? <p>Loading PDF viewer...</p> : null}
      {isPdfReady ? (
        <PDFViewer
          key={currentFileUrl}
          file={currentFileUrl}
          httpHeaders={pdfHttpHeaders}
          initialPage={statePage}
          activeHighlightId={null}
          highlights={[]}
          onPageChange={setStatePage}
          className="h-[70vh]"
        />
      ) : null}

      {/* These are synthetic walkthrough actions, NEVER real document evidence. */}
      {isDemo ? (
        <>
          <button type="button" onClick={() => handleEvidenceClick("c-101")}>
            View Evidence c-101
          </button>
          <button type="button" onClick={handleSwitchDocument}>
            Document B
          </button>
        </>
      ) : null}

      <div data-testid="pdf-page-state">Page: {statePage}</div>
      <div data-testid="highlight-list">
        {activeHighlights.map((highlight) => (
          <div key={highlight.id}>
            <button
              type="button"
              data-testid={`highlight-${highlight.id}`}
              data-active={String(activeId === highlight.id)}
              className={
                resolveHighlightStyle({
                  severity: highlight.severity,
                  validationStatus: "pending",
                  isActive: activeId === highlight.id,
                }).className
              }
              onClick={() => {
                setActiveId(highlight.id);
                setStatePage(highlight.page);
                onHighlightClick(highlight.id);
              }}
            >
              {highlight.text}
            </button>
            <span>{highlight.clauseId}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
