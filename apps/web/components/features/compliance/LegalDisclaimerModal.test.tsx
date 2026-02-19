/**
 * Test Suite ID: S3-08
 * Roadmap Reference: S3-08 Legal disclaimer modal (Gate 8)
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { LegalDisclaimerModal } from "@/components/features/compliance/LegalDisclaimerModal";

describe("S3-08 RED - LegalDisclaimerModal", () => {
  it("[S3-08-RED-UNIT-01] blocks protected action until acceptance", () => {
    render(
      <LegalDisclaimerModal
        open
        gateId="GATE-8"
        version="v1.0"
        effectiveDate="2026-02-15"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );

    expect(screen.getByRole("button", { name: /confirm acceptance/i })).toBeDisabled();
    expect(screen.getByTestId("legal-gate-state")).toHaveTextContent(/blocked/i);
  });

  it("[S3-08-RED-UNIT-02] renders deterministic gate metadata", () => {
    render(
      <LegalDisclaimerModal
        open
        gateId="GATE-8"
        version="v1.2"
        effectiveDate="2026-03-01"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );

    expect(screen.getByTestId("legal-gate-id")).toHaveTextContent("GATE-8");
    expect(screen.getByTestId("legal-version")).toHaveTextContent("v1.2");
    expect(screen.getByTestId("legal-effective-date")).toHaveTextContent("2026-03-01");
  });

  it("[S3-08-RED-UNIT-03] requires explicit checkbox for acceptance", () => {
    let confirmed = 0;
    render(
      <LegalDisclaimerModal
        open
        gateId="GATE-8"
        version="v1.0"
        effectiveDate="2026-02-15"
        onConfirm={() => {
          confirmed += 1;
        }}
        onCancel={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /confirm acceptance/i }));
    expect(confirmed).toBe(0);

    fireEvent.click(screen.getByRole("checkbox", { name: /i have read/i }));
    fireEvent.click(screen.getByRole("button", { name: /confirm acceptance/i }));
    expect(confirmed).toBe(1);
  });

  it("[S3-08-RED-UNIT-04] exposes dialog semantics and supports escape cancel", () => {
    let canceled = 0;
    render(
      <LegalDisclaimerModal
        open
        gateId="GATE-8"
        version="v1.0"
        effectiveDate="2026-02-15"
        onConfirm={() => {}}
        onCancel={() => {
          canceled += 1;
        }}
      />,
    );

    const dialog = screen.getByRole("dialog", { name: /legal disclaimer/i });
    expect(dialog).toHaveAttribute("aria-modal", "true");

    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(canceled).toBe(1);
  });

  it("[S3-08-RED-UNIT-05] re-prompts when disclaimer version changes", () => {
    render(
      <LegalDisclaimerModal
        open
        gateId="GATE-8"
        version="v2.0"
        effectiveDate="2026-04-01"
        acceptedVersion="v1.0"
        onConfirm={() => {}}
        onCancel={() => {}}
      />,
    );

    expect(screen.getByTestId("legal-reprompt-required")).toHaveTextContent(/true/i);
  });
});
