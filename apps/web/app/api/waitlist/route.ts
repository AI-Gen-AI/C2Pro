/**
 * Test Suite ID: TASK-FRT-201
 * Backlog Task: TASK-FRT-201
 */
import { NextResponse } from "next/server";
import { waitlistSchema } from "@/components/landing/waitlist-schema";

const DEFAULT_ALLOWED_ORIGINS = "https://www.ai-gen.ai,https://ai-gen.ai";
const REQUEST_LIMIT = 5;
const WINDOW_MS = 10 * 60 * 1000;

const requestLog = new Map<string, number[]>();

function getAllowedOrigins() {
  return (process.env.WAITLIST_ALLOWED_ORIGINS ?? DEFAULT_ALLOWED_ORIGINS)
    .split(",")
    .map((origin) => origin.trim())
    .filter(Boolean);
}

function corsHeaders(request: Request) {
  const origin = request.headers.get("origin");
  const headers = new Headers();

  if (origin && getAllowedOrigins().includes(origin)) {
    headers.set("Access-Control-Allow-Origin", origin);
    headers.set("Vary", "Origin");
  }

  return headers;
}

function jsonResponse(
  request: Request,
  body: unknown,
  init: ResponseInit = {},
) {
  const headers = corsHeaders(request);
  headers.set("Content-Type", "application/json");

  for (const [key, value] of new Headers(init.headers)) {
    headers.set(key, value);
  }

  return NextResponse.json(body, { ...init, headers });
}

function firstForwardedIp(request: Request) {
  const forwardedFor = request.headers.get("x-forwarded-for");

  if (forwardedFor) {
    return forwardedFor.split(",")[0]?.trim() || "unknown";
  }

  return request.headers.get("x-real-ip") ?? "unknown";
}

function isThrottled(request: Request) {
  const ip = firstForwardedIp(request);
  const now = Date.now();
  const windowStart = now - WINDOW_MS;
  const recent = (requestLog.get(ip) ?? []).filter(
    (timestamp) => timestamp > windowStart,
  );

  if (recent.length >= REQUEST_LIMIT) {
    requestLog.set(ip, recent);
    return true;
  }

  recent.push(now);
  requestLog.set(ip, recent);
  return false;
}

function getSource(request: Request) {
  const origin = request.headers.get("origin");

  if (origin === "https://www.ai-gen.ai" || origin === "https://ai-gen.ai") {
    return "ai-gen.ai";
  }

  return "c2pro.io";
}

function supabaseConfig() {
  const url = process.env.SUPABASE_URL?.replace(/\/+$/, "");
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

  if (!url || !serviceRoleKey) {
    return null;
  }

  return { url, serviceRoleKey };
}

export async function OPTIONS(request: Request) {
  const headers = corsHeaders(request);
  headers.set("Access-Control-Allow-Methods", "POST");
  headers.set("Access-Control-Allow-Headers", "Content-Type");

  return new NextResponse(null, { status: 204, headers });
}

export async function POST(request: Request) {
  let payload: unknown;

  try {
    payload = await request.json();
  } catch {
    return jsonResponse(
      request,
      { success: false, error: { fieldErrors: { body: ["Invalid JSON"] } } },
      { status: 400 },
    );
  }

  if (
    payload &&
    typeof payload === "object" &&
    "website" in payload &&
    typeof payload.website === "string" &&
    payload.website.length > 0
  ) {
    return jsonResponse(request, { success: true });
  }

  const parsed = waitlistSchema.safeParse(payload);

  if (!parsed.success) {
    return jsonResponse(
      request,
      { success: false, error: parsed.error.flatten() },
      { status: 400 },
    );
  }

  // Best-effort per-instance throttle. This is not a distributed rate limit.
  if (isThrottled(request)) {
    return jsonResponse(
      request,
      { success: false, error: "Too many requests" },
      { status: 429 },
    );
  }

  const config = supabaseConfig();

  if (!config) {
    console.error("Waitlist service is not configured.");
    return jsonResponse(
      request,
      { success: false, error: "Service not configured" },
      { status: 503 },
    );
  }

  const row = {
    name: parsed.data.name,
    company: parsed.data.company,
    role: parsed.data.role,
    email: parsed.data.email,
    volume: parsed.data.volume,
    consent: parsed.data.consent,
    locale: parsed.data.locale,
    source: getSource(request),
    user_agent: request.headers.get("user-agent"),
  };

  const response = await fetch(
    `${config.url}/rest/v1/waitlist_signups?on_conflict=email`,
    {
      method: "POST",
      headers: {
        apikey: config.serviceRoleKey,
        Authorization: `Bearer ${config.serviceRoleKey}`,
        "Content-Type": "application/json",
        Prefer: "resolution=merge-duplicates,return=minimal",
      },
      body: JSON.stringify(row),
    },
  );

  if (!response.ok) {
    console.error("Waitlist insert failed.", { status: response.status });
    return jsonResponse(
      request,
      { success: false, error: "Unable to register request" },
      { status: 500 },
    );
  }

  return jsonResponse(request, { success: true });
}
