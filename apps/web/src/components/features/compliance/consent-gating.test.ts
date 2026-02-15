/**
 * Test Suite ID: S3-09
 * Roadmap Reference: S3-09 Cookie consent banner (GDPR)
 */
import { describe, expect, it } from "vitest";
import { isScriptAllowedByConsent } from "@/src/components/features/compliance/consent-gating";

describe("S3-09 RED - consent gating", () => {
  it("[S3-09-RED-UNIT-05] blocks non-essential scripts until category consent exists", () => {
    const consent = {
      necessary: true,
      analytics: false,
      marketing: false,
    };

    expect(isScriptAllowedByConsent("analytics", consent)).toBe(false);
    expect(isScriptAllowedByConsent("marketing", consent)).toBe(false);
    expect(isScriptAllowedByConsent("necessary", consent)).toBe(true);
  });
});
