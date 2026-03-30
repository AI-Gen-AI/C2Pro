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

function normalizeProxyPath(path: string): string {
  if (path.startsWith("api/v1/")) {
    return path.replace(/^api\/v1\//, "");
  }

  if (path === "api/v1") {
    return "";
  }

  if (path.startsWith("v1/")) {
    return path.replace(/^v1\//, "");
  }

  if (path === "v1") {
    return "";
  }

  return path;
}

export function buildBackendUrl(path: string, request: NextRequest): string {
  const searchParams = request.nextUrl.searchParams.toString();
  const baseUrl = getBackendBaseUrl();
  const normalizedPath = normalizeProxyPath(path);
  const isCoherenceRoot = normalizedPath.startsWith("coherence/");
  const isCoherenceApi = normalizedPath.startsWith("api/coherence/");
  const isCoherence = isCoherenceRoot || isCoherenceApi;
  const cleanPath = isCoherenceRoot
    ? normalizedPath.replace(/^coherence\//, "")
    : isCoherenceApi
      ? normalizedPath.replace(/^api\/coherence\//, "")
      : normalizedPath;
  const prefix = isCoherence ? "/api/v1/coherence" : "/api/v1";
  const normalizedBaseUrl = baseUrl
    .replace(/\/api\/v1\/?$/, "")
    .replace(/\/+$/, "");

  return `${normalizedBaseUrl}${prefix}/${cleanPath}${searchParams ? `?${searchParams}` : ""}`;
}
