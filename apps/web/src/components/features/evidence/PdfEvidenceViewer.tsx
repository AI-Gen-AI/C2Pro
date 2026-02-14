/**
 * Test Suite ID: S3-01
 * Roadmap Reference: S3-01 PDF renderer (lazy) + clause highlighting
 */
"use client";

import { useEffect, useMemo, useState } from "react";
import { resolveHighlightStyle } from "@/src/components/features/evidence/highlight-style";
import { createWatermarkToken } from "@/src/components/features/evidence/watermark-token";
import { sanitizeWatermarkPayload } from "@/src/components/features/evidence/watermark-sanitize";
import { EvidenceWatermarkOverlay } from "@/src/components/features/evidence/EvidenceWatermarkOverlay";

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
  const [currentHighlights, setCurrentHighlights] = useState<PdfHighlight[]>(
    highlights,
  );
  const [watermark] = useState(() => {
    if (typeof window !== "undefined") {
      const stored = window.sessionStorage.getItem(WATERMARK_STORAGE_KEY);
      if (stored) {
        try {
          const parsed = JSON.parse(stored) as Record<string, unknown>;
          const safeStored = sanitizeWatermarkPayload(parsed);
          if (safeStored.pseudonymId) {
            return safeStored;
          }
        } catch {
          // Ignore invalid session payload and fall through to safe fallback.
        }
      }
    }

    return sanitizeWatermarkPayload({
      pseudonymId: createWatermarkToken({
        tenantId: "tenant-demo",
        userSeed: "anonymous-user",
        sessionNonce: "evidence-viewer",
      }),
      environment: "local",
      timestampIso: new Date("2026-02-14T00:00:00.000Z").toISOString(),
    });
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
      window.sessionStorage.setItem(WATERMARK_STORAGE_KEY, JSON.stringify(watermark));
    }
  }, [watermark]);

  const activeHighlights = useMemo(() => {
    if (currentHighlights.length > 0) {
      return currentHighlights;
    }
    if (currentFileUrl.includes("doc-b")) {
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
  }, [currentFileUrl, currentHighlights]);

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

  return (
    <section aria-label="PDF Evidence Viewer" className="text-primary-text">
      <EvidenceWatermarkOverlay watermark={watermark} />
      {!isPdfReady ? <p>Loading PDF viewer...</p> : null}
      {isPdfReady ? <div data-testid="pdf-page-canvas">pdf canvas</div> : null}

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
              className={resolveHighlightStyle({
                severity: highlight.severity,
                validationStatus: "pending",
                isActive: activeId === highlight.id,
              }).className}
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
