import { HttpResponse, http } from "msw";

interface ConsentRecord {
  tenantId: string;
  userId: string;
  version: string;
  categories: {
    necessary: boolean;
    analytics: boolean;
    marketing: boolean;
  };
}

const consentStore = new Map<string, ConsentRecord>();

function keyFor(tenantId: string, userId: string, version: string): string {
  return `${tenantId}:${userId}:${version}`;
}

function trackersBlockedFor(categories: ConsentRecord["categories"]): string[] {
  const blocked: string[] = [];
  if (!categories.analytics) blocked.push("analytics");
  if (!categories.marketing) blocked.push("marketing");
  return blocked;
}

export const cookieConsentHandlers = [
  http.post("/api/v1/compliance/cookies/consent", async ({ request }) => {
    const payload = (await request.json()) as {
      tenantId: string;
      userId: string;
      version: string;
      forceError?: boolean;
      categories?: ConsentRecord["categories"];
    };

    if (payload.forceError) {
      return HttpResponse.json(
        {
          code: "COOKIE_CONSENT_PERSIST_FAILED",
          showBanner: true,
        },
        { status: 500 },
      );
    }

    const categories = payload.categories ?? {
      necessary: true,
      analytics: false,
      marketing: false,
    };

    const key = keyFor(payload.tenantId, payload.userId, payload.version);
    consentStore.set(key, {
      tenantId: payload.tenantId,
      userId: payload.userId,
      version: payload.version,
      categories,
    });

    return HttpResponse.json({
      saved: true,
      categories,
      showBanner: false,
    });
  }),

  http.get("/api/v1/compliance/cookies/consent", ({ request }) => {
    const url = new URL(request.url);
    const tenantId = url.searchParams.get("tenantId") ?? "";
    const userId = url.searchParams.get("userId") ?? "";
    const version = url.searchParams.get("version") ?? "";
    const key = keyFor(tenantId, userId, version);
    const record = consentStore.get(key);

    return HttpResponse.json({
      hasConsent: Boolean(record),
      showBanner: !record,
      requiredVersion: version,
      categories: record?.categories ?? null,
    });
  }),

  http.patch("/api/v1/compliance/cookies/consent", async ({ request }) => {
    const payload = (await request.json()) as {
      tenantId: string;
      userId: string;
      version: string;
      categories: ConsentRecord["categories"];
    };
    const key = keyFor(payload.tenantId, payload.userId, payload.version);

    consentStore.set(key, {
      tenantId: payload.tenantId,
      userId: payload.userId,
      version: payload.version,
      categories: payload.categories,
    });

    return HttpResponse.json({
      categories: payload.categories,
      trackersBlocked: trackersBlockedFor(payload.categories),
    });
  }),
];

