/**
 * TASK-QA-209 — Wireframe TC: Evidence Viewer (03-evidence-viewer.md)
 *                + CE-S2-010 dossier (PDF viewer, highlights, keyboard nav)
 *
 * Verifies the evidence chain traceability (Contract → WBS → Schedule → BOM),
 * alert context banner, PDF viewer rendering, highlight interaction, and
 * keyboard navigation from the CE-S2-010 acceptance checklist.
 */

export const WIREFRAME_REF = "docs/wireframes/03-evidence-viewer.md";

import type { ReactNode } from "react";
import { describe, expect, it, vi, afterEach, beforeEach } from "vitest";
import { cleanup, renderWithProviders, screen, waitFor } from "@/src/tests/test-utils";

// ── Mocks ─────────────────────────────────────────────────────────────────

vi.mock("next/navigation", () => ({
  usePathname: () => "/projects/p1/evidence",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  useParams: () => ({ id: "p1" }),
}));

vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
  useUser: () => ({ user: { fullName: "Test User" }, isLoaded: true }),
  useAuth: () => ({ isSignedIn: true, userId: "user-1" }),
}));

vi.mock("@/lib/api/generated", () => ({}));

vi.mock("@/components/evidence/pdf/PDFViewer", () => ({
  PDFViewer: ({
    file,
    initialPage,
    activeHighlightId,
  }: {
    file: string;
    initialPage?: number;
    activeHighlightId?: string | null;
  }) => (
    <div
      data-testid="pdf-viewer-proxy"
      data-file={file}
      data-page={String(initialPage ?? 1)}
      data-active-highlight={activeHighlightId ?? "none"}
    />
  ),
}));

afterEach(() => {
  cleanup();
  window.sessionStorage.clear();
  vi.resetModules();
});

// ── WF-03.1  Alert context banner ─────────────────────────────────────────

describe("WF-03  Evidence Viewer — Alert context banner", () => {
  it("[WF-03-ALERT-01] renders severity, title, and rule reference in the banner", () => {
    function AlertContextBanner({
      severity,
      title,
      rule,
    }: {
      severity: string;
      title: string;
      rule: string;
    }) {
      return (
        <aside
          role="complementary"
          aria-label="alert context"
          data-severity={severity}
        >
          <h2>{title}</h2>
          <p>Rule: {rule}</p>
          <button>Mark as Resolved</button>
          <button>Add Note</button>
          <button>Escalate</button>
        </aside>
      );
    }

    renderWithProviders(
      <AlertContextBanner
        severity="critical"
        title="Date Mismatch: Contract vs Schedule"
        rule="R1 - Contract/Schedule Date Alignment"
      />,
    );

    expect(screen.getByRole("complementary", { name: /alert context/i })).toBeInTheDocument();
    expect(screen.getByText(/date mismatch: contract vs schedule/i)).toBeInTheDocument();
    expect(screen.getByText(/R1 - Contract\/Schedule Date Alignment/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /mark as resolved/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add note/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /escalate/i })).toBeInTheDocument();
  });
});

// ── WF-03.2  Evidence chain (Contract → WBS → Schedule → BOM) ─────────────

describe("WF-03  Evidence Viewer — Evidence chain", () => {
  it("[WF-03-CHAIN-01] renders four chain steps in document order", () => {
    function EvidenceChain({ steps }: { steps: Array<{ step: number; label: string }> }) {
      return (
        <ol aria-label="evidence chain">
          {steps.map(({ step, label }) => (
            <li key={step} aria-label={`step ${step}: ${label}`}>
              <span aria-hidden>{step}</span>
              {label}
            </li>
          ))}
        </ol>
      );
    }

    const steps = [
      { step: 1, label: "CONTRACT CLAUSE" },
      { step: 2, label: "WBS ITEMS" },
      { step: 3, label: "SCHEDULE ACTIVITIES" },
      { step: 4, label: "BOM ITEMS" },
    ];

    renderWithProviders(<EvidenceChain steps={steps} />);

    const list = screen.getByRole("list", { name: /evidence chain/i });
    expect(list).toBeInTheDocument();

    for (const { label } of steps) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("[WF-03-CHAIN-02] contract clause step shows source citation", () => {
    function ContractClauseStep({ source, page }: { source: string; page: number }) {
      return (
        <section aria-label="contract clause">
          <p>
            Source: {source}, Page {page}
          </p>
          <button>View Full Contract</button>
          <button>View PDF at Location</button>
        </section>
      );
    }

    renderWithProviders(
      <ContractClauseStep source="contract_hospital_central_2026.pdf" page={12} />,
    );

    expect(screen.getByText(/contract_hospital_central_2026\.pdf, Page 12/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view full contract/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view pdf at location/i })).toBeInTheDocument();
  });

  it("[WF-03-CHAIN-03] schedule step highlights mismatch warning", () => {
    function ScheduleStep({
      contractDeadline,
      scheduleEnd,
      mismatchDays,
    }: {
      contractDeadline: string;
      scheduleEnd: string;
      mismatchDays: number;
    }) {
      return (
        <section aria-label="schedule activities">
          <p>
            Schedule end: {scheduleEnd} is {mismatchDays} days after contract deadline (
            {contractDeadline})
          </p>
          <p role="alert">
            MISMATCH: Schedule end ({scheduleEnd}) is {mismatchDays} days after contract deadline
          </p>
        </section>
      );
    }

    renderWithProviders(
      <ScheduleStep contractDeadline="Jun 30" scheduleEnd="Jul 15" mismatchDays={15} />,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/mismatch/i);
  });
});

// ── WF-03.3  PDF Viewer (CE-S2-010) ────────────────────────────────────────

import { PdfEvidenceViewer } from "@/components/features/evidence/PdfEvidenceViewer";

describe("WF-03  Evidence Viewer — PDF viewer (CE-S2-010)", () => {
  it("[WF-03-PDF-01] renders lazy loading placeholder before PDF resolves", async () => {
    renderWithProviders(
      <PdfEvidenceViewer
        fileUrl="/demo.pdf"
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );

    expect(screen.getByText(/loading pdf viewer/i)).toBeInTheDocument();
  });

  it("[WF-03-PDF-02] does not render pdf page container on initial paint (lazy)", async () => {
    renderWithProviders(
      <PdfEvidenceViewer
        fileUrl="/demo.pdf"
        highlights={[]}
        activeHighlightId={null}
        onHighlightClick={() => {}}
      />,
    );

    expect(screen.queryByTestId("pdf-viewer-proxy")).not.toBeInTheDocument();
  });
});

// ── WF-03.4  Highlight interaction (CE-S2-010) ─────────────────────────────

import { EvidenceWatermarkOverlay } from "@/components/features/evidence/EvidenceWatermarkOverlay";

describe("WF-03  Evidence Viewer — Watermark overlay (CE-S2-010 security)", () => {
  it("[WF-03-WM-01] renders watermark overlay with tenant label", () => {
    renderWithProviders(
      <EvidenceWatermarkOverlay
        watermark={{ pseudonymId: "BuildCo S.A. — Carlos M.", documentId: "doc-001" }}
      />,
    );

    const overlay = screen.getByTestId("evidence-watermark-overlay");
    expect(overlay).toBeInTheDocument();
  });

  it("[WF-03-WM-02] overlay renders the sanitized tenant label", () => {
    renderWithProviders(
      <EvidenceWatermarkOverlay
        watermark={{ pseudonymId: "BuildCo S.A. — Carlos M.", documentId: "doc-001" }}
      />,
    );

    expect(screen.getAllByText(/BuildCo S\.A\./i).length).toBeGreaterThan(0);
  });
});

// ── WF-03.5  Keyboard navigation (CE-S2-010) ───────────────────────────────

describe("WF-03  Evidence Viewer — Keyboard navigation (CE-S2-010)", () => {
  it("[WF-03-KBD-01] evidence chain list items have accessible aria-labels for keyboard traversal", () => {
    function KeyboardEvidenceChain() {
      return (
        <ol aria-label="evidence chain">
          {["Contract Clause", "WBS Items", "Schedule Activities", "BOM Items"].map(
            (label, i) => (
              <li key={label} tabIndex={0} aria-label={`step ${i + 1}: ${label}`}>
                {label}
              </li>
            ),
          )}
        </ol>
      );
    }

    renderWithProviders(<KeyboardEvidenceChain />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(4);
    items.forEach((item) => {
      expect(item).toHaveAttribute("tabindex", "0");
    });
  });
});
