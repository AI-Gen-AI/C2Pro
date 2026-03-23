import type { NextRequest } from "next/server";

// BACKEND_URL is server-side only and preferred for the proxy to avoid leaking
// internal backend structure to the client-side bundle.
const BACKEND_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1";

function getBackendBaseUrl(): string {
  if (BACKEND_URL.startsWith("/")) {
    return "http://localhost:8000/api/v1";
  }

  return BACKEND_URL.replace(/\/+$/, "");
}

export function buildBackendUrl(path: string, request: NextRequest): string {
  const searchParams = request.nextUrl.searchParams.toString();
  const baseUrl = getBackendBaseUrl();
  const isCoherenceRoot = path.startsWith("coherence/");
  const isCoherenceApi = path.startsWith("api/coherence/");
  const isCoherence = isCoherenceRoot || isCoherenceApi;
  const cleanPath = isCoherenceRoot
    ? path.replace(/^coherence\//, "")
    : isCoherenceApi
      ? path.replace(/^api\/coherence\//, "")
      : path;
  const prefix = isCoherence ? "/api/v1/coherence" : "/api/v1";
  const normalizedBaseUrl = baseUrl
    .replace(/\/api\/v1\/?$/, "")
    .replace(/\/+$/, "");

  return `${normalizedBaseUrl}${prefix}/${cleanPath}${searchParams ? `?${searchParams}` : ""}`;
}
