/**
 * Test Suite ID: S3-09
 * Roadmap Reference: S3-09 Cookie consent banner (GDPR)
 */
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@/src/tests/test-utils";
import { CookieConsentBanner } from "@/components/features/compliance/CookieConsentBanner";

describe("S3-09 RED - CookieConsentBanner", () => {
  it("[S3-09-RED-UNIT-01] renders first-visit banner with required categories and actions", () => {
    render(<CookieConsentBanner policyVersion="2026-02" />);

    expect(screen.getByRole("region", { name: /cookie consent/i })).toBeInTheDocument();
    expect(screen.getByText(/necessary/i)).toBeInTheDocument();
    expect(screen.getByText(/analytics/i)).toBeInTheDocument();
    expect(screen.getByText(/marketing/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /accept all/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject optional/i })).toBeInTheDocument();
  });

  it("[S3-09-RED-UNIT-02] accept-all persists full consent payload", () => {
    render(<CookieConsentBanner policyVersion="2026-02" />);

    fireEvent.click(screen.getByRole("button", { name: /accept all/i }));

    expect(screen.getByTestId("cookie-consent-payload")).toHaveTextContent(/"analytics":true/);
    expect(screen.getByTestId("cookie-consent-payload")).toHaveTextContent(/"marketing":true/);
    expect(screen.getByTestId("cookie-consent-payload")).toHaveTextContent(/"version":"2026-02"/);
  });

  it("[S3-09-RED-UNIT-03] reject-optional keeps only necessary cookies", () => {
    render(<CookieConsentBanner policyVersion="2026-02" />);

    fireEvent.click(screen.getByRole("button", { name: /reject optional/i }));

    expect(screen.getByTestId("cookie-consent-payload")).toHaveTextContent(/"necessary":true/);
    expect(screen.getByTestId("cookie-consent-payload")).toHaveTextContent(/"analytics":false/);
    expect(screen.getByTestId("cookie-consent-payload")).toHaveTextContent(/"marketing":false/);
  });

  it("[S3-09-RED-UNIT-04] preferences modal saves granular toggles", () => {
    render(<CookieConsentBanner policyVersion="2026-02" />);

    fireEvent.click(screen.getByRole("button", { name: /manage preferences/i }));
    fireEvent.click(screen.getByRole("checkbox", { name: /analytics cookies/i }));
    fireEvent.click(screen.getByRole("button", { name: /save preferences/i }));

    expect(screen.getByTestId("cookie-consent-payload")).toHaveTextContent(/"analytics":true/);
    expect(screen.getByTestId("cookie-consent-payload")).toHaveTextContent(/"marketing":false/);
  });

  it("[S3-09-RED-UNIT-06] banner and preferences modal expose accessible roles and keyboard close", () => {
    render(<CookieConsentBanner policyVersion="2026-02" />);

    expect(screen.getByRole("region", { name: /cookie consent/i })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /manage preferences/i }));

    const dialog = screen.getByRole("dialog", { name: /cookie preferences/i });
    fireEvent.keyDown(dialog, { key: "Escape" });

    expect(screen.queryByRole("dialog", { name: /cookie preferences/i })).not.toBeInTheDocument();
  });
});
