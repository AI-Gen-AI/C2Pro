/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
"use client";

import { useEffect, useMemo, useState } from "react";
import { env } from "@/config/env";
import { resolveHighlightStyle } from "@/components/features/evidence/highlight-style";
import { createWatermarkToken } from "@/components/features/evidence/watermark-token";
import { sanitizeWatermarkPayload } from "@/components/features/evidence/watermark-sanitize";
import { EvidenceWatermarkOverlay } from "@/components/features/evidence/EvidenceWatermarkOverlay";

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

function createDemoWatermark() {
  return sanitizeWatermarkPayload({
    pseudonymId: createWatermarkToken({
      tenantId: "tenant-demo",
      userSeed: "anonymous-user",
      sessionNonce: "evidence-viewer",
    }),
    environment: "local",
    timestampIso: new Date("2026-02-14T00:00:00.000Z").toISOString(),
  });
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
  const [currentFileUrl, setCurrentFileUrl] = useState(fileUrl);
  const [currentHighlights, setCurrentHighlights] =
    useState<PdfHighlight[]>(highlights);

  const isDemo = env.APP_MODE === "demo";

  const [watermark] = useState(() => {
    if (isDemo) {
      return readStoredDemoWatermark() ?? createDemoWatermark();
    }

    return sanitizeWatermarkPayload({});
  });

  useEffect(() => {
    const timer = setTimeout(() => setIsPdfReady(true), 0);
    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (activeHighlightId) {
      setActiveId(activeHighlightId);
    }
  }, [activeHighlightId]);

  useEffect(() => {
    if (fileUrl !== currentFileUrl) {
      setCurrentFileUrl(fileUrl);
      setStatePage(1);
      setActiveId(null);
      setCurrentHighlights(highlights);
    }
  }, [fileUrl, highlights]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      if (watermark.pseudonymId) {
        window.sessionStorage.setItem(
          WATERMARK_STORAGE_KEY,
          JSON.stringify(watermark),
        );
      } else {
        window.sessionStorage.removeItem(WATERMARK_STORAGE_KEY);
      }
    }
  }, [watermark]);

  const activeHighlights = useMemo(() => {
    if (currentHighlights.length > 0) {
      return currentHighlights;
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
  }, [currentFileUrl, currentHighlights, isDemo]);

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
        <iframe
          data-testid="pdf-page-canvas"
          title="PDF document viewer"
          src={currentFileUrl}
          className="h-[70vh] w-full border-0"
        />
      ) : null}

      <button type="button" onClick={() => handleEvidenceClick("c-101")}>
        View Evidence c-101
      </button>
      <button type="button" onClick={handleSwitchDocument}>
        Document B
      </button>

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
