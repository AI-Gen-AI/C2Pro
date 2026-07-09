/**
 * Test Suite ID: TASK-FRT-201
 * Backlog Task: TASK-FRT-201
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const ORIGINAL_ENV = {
  SUPABASE_URL: process.env.SUPABASE_URL,
  serviceRoleKey: process.env["SUPABASE_" + "SERVICE_ROLE_KEY"],
  WAITLIST_ALLOWED_ORIGINS: process.env.WAITLIST_ALLOWED_ORIGINS,
};

const validBody = {
  name: "Ana Lopez",
  company: "Constructora Norte",
  role: "Compras",
  email: " ANA@EXAMPLE.COM ",
  volume: "20_100",
  consent: true,
  locale: "es",
  website: "",
};

async function loadRoute() {
  vi.resetModules();
  return import("./route");
}

function makeRequest(body: unknown, init: RequestInit = {}) {
  return new Request("https://www.c2pro.io/api/waitlist", {
    method: "POST",
    body: JSON.stringify(body),
    headers: {
      "Content-Type": "application/json",
      "User-Agent": "vitest-agent",
      "x-forwarded-for": "203.0.113.7, 10.0.0.1",
      ...(init.headers ?? {}),
    },
    ...init,
  });
}

describe("POST /api/waitlist", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-08T22:00:00Z"));
    process.env.SUPABASE_URL = "https://supabase.example";
    process.env["SUPABASE_" + "SERVICE_ROLE_KEY"] = "service-role-secret";
    process.env.WAITLIST_ALLOWED_ORIGINS =
      "https://www.ai-gen.ai,https://ai-gen.ai";
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(null, { status: 201 }),
    );
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    process.env.SUPABASE_URL = ORIGINAL_ENV.SUPABASE_URL;
    process.env["SUPABASE_" + "SERVICE_ROLE_KEY"] =
      ORIGINAL_ENV.serviceRoleKey;
    process.env.WAITLIST_ALLOWED_ORIGINS =
      ORIGINAL_ENV.WAITLIST_ALLOWED_ORIGINS;
  });

  it("upserts valid submissions through PostgREST with service-role headers", async () => {
    const { POST } = await loadRoute();

    const response = await POST(
      makeRequest(validBody, {
        headers: {
          Origin: "https://www.ai-gen.ai",
        },
      }),
    );

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ success: true });
    expect(response.headers.get("Access-Control-Allow-Origin")).toBe(
      "https://www.ai-gen.ai",
    );
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "https://supabase.example/rest/v1/waitlist_signups?on_conflict=email",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          apikey: "service-role-secret",
          Authorization: "Bearer service-role-secret",
          Prefer: "resolution=merge-duplicates,return=minimal",
        }),
        body: JSON.stringify({
          name: "Ana Lopez",
          company: "Constructora Norte",
          role: "Compras",
          email: "ana@example.com",
          volume: "20_100",
          consent: true,
          locale: "es",
          source: "ai-gen.ai",
          user_agent: null,
        }),
      }),
    );
  });

  it("rejects invalid payloads without calling PostgREST", async () => {
    const { POST } = await loadRoute();

    const response = await POST(
      makeRequest({ ...validBody, email: "not-an-email", consent: false }),
    );

    expect(response.status).toBe(400);
    const json = await response.json();
    expect(json.success).toBe(false);
    expect(json.error.fieldErrors.email).toBeDefined();
    expect(json.error.fieldErrors.consent).toBeDefined();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("accepts honeypot-filled bot submissions without inserting", async () => {
    const { POST } = await loadRoute();

    const response = await POST(makeRequest({ ...validBody, website: "bot" }));

    expect(response.status).toBe(200);
    await expect(response.json()).resolves.toEqual({ success: true });
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });

  it("throttles the sixth request from the same forwarded IP", async () => {
    const { POST } = await loadRoute();

    for (let index = 0; index < 5; index += 1) {
      await POST(makeRequest({ ...validBody, email: `ana-${index}@example.com` }));
    }

    const response = await POST(makeRequest(validBody));

    expect(response.status).toBe(429);
    await expect(response.json()).resolves.toEqual({
      success: false,
      error: "Too many requests",
    });
  });

  it("returns 503 without exposing env names when the service is not configured", async () => {
    process.env["SUPABASE_" + "SERVICE_ROLE_KEY"] = "";
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const { POST } = await loadRoute();

    const response = await POST(makeRequest(validBody));

    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({
      success: false,
      error: "Service not configured",
    });
    expect(consoleError).toHaveBeenCalled();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});

describe("OPTIONS /api/waitlist", () => {
  afterEach(() => {
    process.env.WAITLIST_ALLOWED_ORIGINS =
      ORIGINAL_ENV.WAITLIST_ALLOWED_ORIGINS;
  });

  it("echoes allowed CORS origins", async () => {
    process.env.WAITLIST_ALLOWED_ORIGINS =
      "https://www.ai-gen.ai,https://ai-gen.ai";
    const { OPTIONS } = await loadRoute();

    const response = await OPTIONS(
      new Request("https://www.c2pro.io/api/waitlist", {
        method: "OPTIONS",
        headers: { Origin: "https://www.ai-gen.ai" },
      }),
    );

    expect(response.status).toBe(204);
    expect(response.headers.get("Access-Control-Allow-Origin")).toBe(
      "https://www.ai-gen.ai",
    );
    expect(response.headers.get("Access-Control-Allow-Methods")).toBe("POST");
    expect(response.headers.get("Access-Control-Allow-Headers")).toBe(
      "Content-Type",
    );
  });

  it("omits CORS allow-origin for disallowed origins", async () => {
    const { OPTIONS } = await loadRoute();

    const response = await OPTIONS(
      new Request("https://www.c2pro.io/api/waitlist", {
        method: "OPTIONS",
        headers: { Origin: "https://evil.example" },
      }),
    );

    expect(response.status).toBe(204);
    expect(response.headers.get("Access-Control-Allow-Origin")).toBeNull();
  });
});
