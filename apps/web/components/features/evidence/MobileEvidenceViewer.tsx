/**
 * Test Suite ID: S3-02
 * Roadmap Reference: S3-02 Mobile Evidence Viewer (tab interface)
 */
"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

type ViewerTab = "pdf" | "alerts";

interface PdfState {
  page: number;
  zoom: number;
}

interface HighlightItem {
  id: string;
  clauseId: string;
  text: string;
  page: number;
}

interface AlertItem {
  id: string;
  clauseId: string;
  title: string;
}

interface MobileEvidenceViewerProps {
  pdfState: PdfState;
  highlights: HighlightItem[];
  alerts: AlertItem[];
  onSelectAlert: (alertId: string) => void;
}

const SESSION_KEY = "s3-02-mobile-evidence-state";
const VIRTUAL_THRESHOLD = 500;
const VIRTUAL_WINDOW_SIZE = 40;

function readSession(): { tab: ViewerTab; clauseId: string | null } | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && (parsed.tab === "pdf" || parsed.tab === "alerts")) {
      return { tab: parsed.tab, clauseId: parsed.clauseId ?? null };
    }
  } catch {
    // ignore
  }
  return null;
}

function writeSession(tab: ViewerTab, clauseId: string | null) {
  try {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ tab, clauseId }));
  } catch {
    // ignore
  }
}

export function MobileEvidenceViewer({
  pdfState,
  highlights,
  alerts,
  onSelectAlert,
}: MobileEvidenceViewerProps) {
  const saved = useMemo(() => readSession(), []);
  const preferredInitialClauseId = highlights[0]?.clauseId ?? saved?.clauseId ?? null;
  const [activeTab, setActiveTab] = useState<ViewerTab>(saved?.tab ?? "pdf");
  const [activeClauseId, setActiveClauseId] = useState<string | null>(
    preferredInitialClauseId,
  );
  const [viewportWidth, setViewportWidth] = useState(
    typeof window !== "undefined" ? window.innerWidth : 0,
  );

  // --- Virtualization state ---
  const useVirtual = alerts.length >= VIRTUAL_THRESHOLD;
  const pageSize = useVirtual ? VIRTUAL_WINDOW_SIZE : alerts.length;
  const initialVirtualStart = useMemo(() => {
    if (!useVirtual) return 0;

    const preferredClauseId = preferredInitialClauseId;
    if (!preferredClauseId) return 0;

    const preferredIndex = alerts.findIndex(
      (alert) => alert.clauseId === preferredClauseId,
    );
    if (preferredIndex === -1) return 0;

    return Math.max(
      0,
      Math.min(
        preferredIndex - Math.floor(VIRTUAL_WINDOW_SIZE / 2),
        Math.max(0, alerts.length - VIRTUAL_WINDOW_SIZE),
      ),
    );
  }, [alerts, preferredInitialClauseId, useVirtual]);
  const [virtualStart, setVirtualStart] = useState(initialVirtualStart);
  const [activeAlertIndex, setActiveAlertIndex] = useState<number | null>(null);
  const virtualRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  // --- Viewport tracking ---
  useEffect(() => {
    const handler = () => setViewportWidth(window.innerWidth);
    window.addEventListener("resize", handler);
    return () => window.removeEventListener("resize", handler);
  }, []);

  // --- Session persistence ---
  useEffect(() => {
    writeSession(activeTab, activeClauseId);
  }, [activeTab, activeClauseId]);

  const orderedTabs: ViewerTab[] = ["pdf", "alerts"];

  const handleTabKeyDown = (current: ViewerTab, key: string) => {
    if (key === "Tab") {
      sentinelRef.current?.focus();
      return;
    }
    if (key !== "ArrowRight" && key !== "ArrowLeft") return;

    const currentIndex = orderedTabs.indexOf(current);
    if (currentIndex === -1) return;

    const nextIndex =
      key === "ArrowRight"
        ? Math.min(currentIndex + 1, orderedTabs.length - 1)
        : Math.max(currentIndex - 1, 0);

    const nextTab = orderedTabs[nextIndex];
    if (!nextTab) return;
    setActiveTab(nextTab);
    const nextButton = document.querySelector<HTMLButtonElement>(
      `[data-tab-id="${nextTab}"]`,
    );
    nextButton?.focus();
  };

  const activeHighlight = useMemo(() => {
    if (!activeClauseId) return null;
    return highlights.find((h) => h.clauseId === activeClauseId) ?? null;
  }, [activeClauseId, highlights]);

  // --- Virtual keyboard handler ---
  const handleVirtualKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!useVirtual) return;
      if (e.key === "Home") {
        setVirtualStart(0);
        setActiveAlertIndex(0);
      } else if (e.key === "End") {
        const last = alerts.length - 1;
        setVirtualStart(Math.max(0, alerts.length - pageSize));
        setActiveAlertIndex(last);
      } else if (e.key === "PageDown") {
        setVirtualStart((s) =>
          Math.min(s + pageSize, Math.max(0, alerts.length - pageSize)),
        );
      } else if (e.key === "PageUp") {
        setVirtualStart((s) => Math.max(s - pageSize, 0));
      }
    },
    [useVirtual, alerts.length, pageSize],
  );

  // --- Compute visible alerts slice ---
  const visibleAlerts = useVirtual
    ? alerts.slice(virtualStart, virtualStart + pageSize)
    : alerts;

  const handleAlertClick = (alert: AlertItem) => {
    setActiveClauseId(alert.clauseId);
    onSelectAlert(alert.id);
    if (useVirtual) {
      const idx = alerts.indexOf(alert);
      if (idx >= 0) setActiveAlertIndex(idx);
    }
  };

  useEffect(() => {
    if (!useVirtual) {
      setVirtualStart(0);
      return;
    }

    setVirtualStart(initialVirtualStart);
  }, [initialVirtualStart, useVirtual]);

  return (
    <section aria-label="Mobile Evidence Viewer" className="text-primary-text">
      <div data-testid="mobile-viewport-state">width: {viewportWidth}</div>

      <div role="tablist" aria-label="Evidence mobile tabs">
        <button
          id="tab-pdf"
          data-tab-id="pdf"
          role="tab"
          aria-selected={activeTab === "pdf"}
          aria-controls="panel-pdf"
          type="button"
          onClick={() => setActiveTab("pdf")}
          onKeyDown={(event) => handleTabKeyDown("pdf", event.key)}
        >
          PDF
        </button>
        <button
          id="tab-alerts"
          data-tab-id="alerts"
          role="tab"
          aria-selected={activeTab === "alerts"}
          aria-controls="panel-alerts"
          type="button"
          onClick={() => setActiveTab("alerts")}
          onKeyDown={(event) => handleTabKeyDown("alerts", event.key)}
        >
          Alerts
        </button>
      </div>

      <section
        id="panel-pdf"
        role="tabpanel"
        aria-labelledby="tab-pdf"
        data-testid="mobile-panel-pdf"
        data-state={activeTab === "pdf" ? "active" : "inactive"}
        hidden={activeTab !== "pdf"}
      >
        <div data-testid="mobile-pdf-state">
          Page: {pdfState.page} | Zoom: {pdfState.zoom}
        </div>

        {highlights.length === 0 ? (
          <p>No highlights for this document</p>
        ) : (
          <ul>
            {highlights.map((highlight) => (
              <li key={highlight.id}>
                <button
                  type="button"
                  data-testid={`mobile-highlight-${highlight.id}`}
                  onClick={() => setActiveClauseId(highlight.clauseId)}
                >
                  {highlight.text}
                </button>
              </li>
            ))}
          </ul>
        )}

        <div data-testid="mobile-active-highlight">
          {activeHighlight?.clauseId ?? activeClauseId ?? "none"}
        </div>
      </section>

      <section
        id="panel-alerts"
        role="tabpanel"
        aria-labelledby="tab-alerts"
        data-testid="mobile-panel-alerts"
        data-state={activeTab === "alerts" ? "active" : "inactive"}
        hidden={activeTab !== "alerts"}
      >
        {alerts.length === 0 ? (
          <p>No alerts available</p>
        ) : useVirtual ? (
          <div
            data-testid="mobile-alert-virtual-window"
            ref={virtualRef}
            tabIndex={0}
            onKeyDown={handleVirtualKeyDown}
          >
            <div data-testid="mobile-alert-active-index">
              {activeAlertIndex ?? ""}
            </div>
            <ul>
              {visibleAlerts.map((alert) => (
                <li key={alert.id}>
                  <button
                    type="button"
                    onClick={() => handleAlertClick(alert)}
                  >
                    {alert.title}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : (
          <ul>
            {alerts.map((alert) => (
              <li key={alert.id}>
                <button
                  type="button"
                  onClick={() => handleAlertClick(alert)}
                >
                  {alert.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div
        ref={sentinelRef}
        data-testid="mobile-focus-exit-sentinel"
        tabIndex={0}
        aria-hidden="true"
        style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0,0,0,0)" }}
      />
    </section>
  );
}
