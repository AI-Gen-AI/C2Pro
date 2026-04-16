const DEFAULT_API_BASE_URL = "/api";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function normalizeApiBaseUrl(rawValue: string | undefined): string {
  const value = rawValue?.trim();

  // If not provided, use the proxy endpoint
  if (!value) {
    return DEFAULT_API_BASE_URL;
  }

  // If provided as "/", also use the default proxy endpoint
  return value === "/" ? DEFAULT_API_BASE_URL : trimTrailingSlash(value);
}

const API_BASE_URL = normalizeApiBaseUrl(process.env.NEXT_PUBLIC_API_URL);

function getBackendOrigin(apiBaseUrl: string): string {
  if (apiBaseUrl.startsWith("http://") || apiBaseUrl.startsWith("https://")) {
    return new URL(apiBaseUrl).origin;
  }

  return "";
}

function getCoherenceBaseUrl(
  apiBaseUrl: string,
  backendOrigin: string,
): string {
  void apiBaseUrl;
  void backendOrigin;
  return "/coherence";
}

const BACKEND_ORIGIN = getBackendOrigin(API_BASE_URL);
const COHERENCE_BASE_URL = getCoherenceBaseUrl(API_BASE_URL, BACKEND_ORIGIN);

export const env = {
  APP_MODE: (process.env.NEXT_PUBLIC_APP_MODE ?? "production") as
    | "production"
    | "demo",
  API_BASE_URL,
  BACKEND_ORIGIN,
  COHERENCE_BASE_URL,
  IS_DEMO: process.env.NEXT_PUBLIC_APP_MODE === "demo",
  IS_DEV: process.env.NODE_ENV === "development",
  FEATURE_RACI_GENERATION:
    process.env.NEXT_PUBLIC_FEATURE_RACI_GENERATION === "true",
  SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
} as const;
