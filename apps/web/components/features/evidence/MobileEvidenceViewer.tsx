/**
 * Test Suite ID: S3-02
 * Roadmap Reference: S3-02 Mobile Evidence Viewer (tab interface)
 */
"use client";

import { useMemo, useState } from "react";

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

export function MobileEvidenceViewer({
  pdfState,
  highlights,
  alerts,
  onSelectAlert,
}: MobileEvidenceViewerProps) {
  const [activeTab, setActiveTab] = useState<ViewerTab>("pdf");
  const [activeClauseId, setActiveClauseId] = useState<string | null>(null);

  const orderedTabs: ViewerTab[] = ["pdf", "alerts"];

  const handleTabKeyDown = (current: ViewerTab, key: string) => {
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
    return highlights.find((highlight) => highlight.clauseId === activeClauseId) ?? null;
  }, [activeClauseId, highlights]);

  return (
    <section aria-label="Mobile Evidence Viewer" className="text-primary-text">
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
          {activeHighlight?.clauseId ?? "none"}
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
        ) : (
          <ul>
            {alerts.map((alert) => (
              <li key={alert.id}>
                <button
                  type="button"
                  onClick={() => {
                    setActiveClauseId(alert.clauseId);
                    onSelectAlert(alert.id);
                  }}
                >
                  {alert.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
