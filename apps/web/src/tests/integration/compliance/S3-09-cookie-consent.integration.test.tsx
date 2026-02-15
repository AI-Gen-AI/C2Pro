/**
 * Test Suite ID: S3-09
 * Roadmap Reference: S3-09 Cookie consent banner (GDPR)
 */
import { describe, expect, it } from "vitest";

describe("S3-09 RED - cookie consent integration", () => {
  it("[S3-09-RED-INT-01] consent persists and suppresses banner for same version", async () => {
    const save = await fetch("/api/v1/compliance/cookies/consent", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        tenantId: "tenant_demo",
        userId: "user_demo",
        version: "2026-02",
        categories: { necessary: true, analytics: true, marketing: false },
      }),
    });

    expect(save.status).toBe(200);

    const status = await fetch("/api/v1/compliance/cookies/consent?tenantId=tenant_demo&userId=user_demo&version=2026-02");
    expect(status.status).toBe(200);
    expect(await status.json()).toMatchObject({
      hasConsent: true,
      showBanner: false,
    });
  });

  it("[S3-09-RED-INT-02] version bump invalidates prior consent and re-prompts", async () => {
    const status = await fetch("/api/v1/compliance/cookies/consent?tenantId=tenant_demo&userId=user_demo&version=2026-03");

    expect(status.status).toBe(200);
    expect(await status.json()).toMatchObject({
      hasConsent: false,
      showBanner: true,
      requiredVersion: "2026-03",
    });
  });

  it("[S3-09-RED-INT-03] withdraw/update consent re-gates optional trackers immediately", async () => {
    const response = await fetch("/api/v1/compliance/cookies/consent", {
      method: "PATCH",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        tenantId: "tenant_demo",
        userId: "user_demo",
        version: "2026-02",
        categories: { necessary: true, analytics: false, marketing: false },
      }),
    });

    expect(response.status).toBe(200);
    expect(await response.json()).toMatchObject({
      categories: { necessary: true, analytics: false, marketing: false },
      trackersBlocked: ["analytics", "marketing"],
    });
  });

  it("[S3-09-RED-INT-04] backend sync failure returns deterministic error contract", async () => {
    const response = await fetch("/api/v1/compliance/cookies/consent", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        tenantId: "tenant_demo",
        userId: "user_demo",
        version: "2026-02",
        forceError: true,
      }),
    });

    expect(response.status).toBe(500);
    expect(await response.json()).toMatchObject({
      code: "COOKIE_CONSENT_PERSIST_FAILED",
      showBanner: true,
    });
  });
});
