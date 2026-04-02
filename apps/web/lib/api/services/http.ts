/**
 * Test Suite ID: TASK-021
 * Purpose: build-safe fetch helpers for frontend page data loading.
 */

import { handleAuthErrorStatus } from "@/lib/api/client";
import { useAuthStore } from "@/stores/auth";

type ApiScope = "default" | "coherence";

type ApiRequestOptions = RequestInit & {
  server?: boolean;
  scope?: ApiScope;
};

const DEFAULT_BACKEND_BASE_URL =
  process.env.BACKEND_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000/api/v1";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function normalizeBackendBaseUrl(): string {
  if (DEFAULT_BACKEND_BASE_URL.startsWith("/")) {
    return "http://localhost:8000/api/v1";
  }

  return trimTrailingSlash(DEFAULT_BACKEND_BASE_URL);
}

function buildApiUrl(
  path: string,
  { server = false, scope = "default" }: Pick<ApiRequestOptions, "server" | "scope">,
): string {
  const normalizedPath = path.replace(/^\/+/, "");
  const prefix = scope === "coherence" ? "/api/coherence" : "/api/v1";

  if (!server) {
    return `${prefix}/${normalizedPath}`;
  }

  const backendBaseUrl = normalizeBackendBaseUrl()
    .replace(/\/api\/v1\/?$/, "")
    .replace(/\/+$/, "");
  const backendPrefix = scope === "coherence" ? "/api/v1/coherence" : "/api/v1";

  return `${backendBaseUrl}${backendPrefix}/${normalizedPath}`;
}

function buildBrowserAuthHeaders(headersInit: HeadersInit | undefined): HeadersInit | undefined {
  const { token, tenantId } = useAuthStore.getState();
  const headers = new Headers(headersInit);

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  if (tenantId) {
    headers.set("X-Tenant-ID", tenantId);
  }

  return headers.entries().next().done ? undefined : Object.fromEntries(headers.entries());
}

async function parseError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string; error?: string };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
    if (typeof payload.error === "string" && payload.error.trim()) {
      return payload.error;
    }
  } catch {
    // Ignore non-JSON error bodies and fall back to status text.
  }

  return response.statusText || "Request failed";
}

export async function fetchApiJson<T>(
  path: string,
  options?: ApiRequestOptions,
): Promise<T> {
  const { server, scope, headers, ...init } = options ?? {};
  const requestInit: RequestInit = { ...init };

  if (!server) {
    const mergedHeaders = buildBrowserAuthHeaders(headers);
    if (mergedHeaders) {
      requestInit.headers = mergedHeaders;
    }
  } else if (headers) {
    requestInit.headers = headers;
  }

  const response = await fetch(buildApiUrl(path, { server, scope }), requestInit);

  if (!response.ok) {
    if (!server) {
      handleAuthErrorStatus(response.status);
    }
    throw new Error(await parseError(response));
  }

  return (await response.json()) as T;
}
