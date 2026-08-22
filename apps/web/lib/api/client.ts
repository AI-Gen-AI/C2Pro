import axios from "axios/dist/browser/axios.cjs";
import type {
  AxiosError,
  AxiosResponse,
  AxiosRequestConfig,
  InternalAxiosRequestConfig,
} from "axios";
import { env } from "@/config/env";
import { showToast } from "@/lib/ui/toast";
import { isExplicitDemoRoute } from "@/stores/app-mode";
import { useAuthStore } from "@/stores/auth";

export const apiClient = axios.create({
  baseURL: env.API_BASE_URL,
});

interface BrowserLocationAdapter {
  getPathname(): string;
  redirectToSignIn(): void;
}

const defaultBrowserLocationAdapter: BrowserLocationAdapter = {
  getPathname() {
    return window.location.pathname ?? "/";
  },
  redirectToSignIn() {
    window.location.assign("/sign-in");
  },
};

let browserLocationAdapter: BrowserLocationAdapter = defaultBrowserLocationAdapter;

export async function orvalApiClient<T>(
  config: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.request<T>({
    ...config,
    url: normalizeGeneratedApiUrl(config.url),
  });
  return response.data;
}

let authRedirectInFlight = false;

const attachAuthToken = (config: InternalAxiosRequestConfig) => {
  const { token, tenantId } = useAuthStore.getState();
  const headers = config.headers ?? {};

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (tenantId) {
    headers["X-Tenant-ID"] = tenantId;
  }

  config.headers = headers;

  return config;
};

const handleAuthFailure = () => {
  // Clear local store
  useAuthStore.getState().clear();

  if (typeof window === "undefined") return;

  const pathname = browserLocationAdapter.getPathname();
  const isAuthPage =
    pathname.startsWith("/sign-in") ||
    pathname.startsWith("/sign-up") ||
    pathname.startsWith("/login") ||
    pathname.startsWith("/register");
  const isDemoRoute = env.APP_MODE === "demo" && isExplicitDemoRoute(pathname);

  if (isAuthPage || isDemoRoute) {
    authRedirectInFlight = false;
    return;
  }

  if (authRedirectInFlight) {
    return;
  }

  authRedirectInFlight = true;
  showToast("Session expired or invalid");
  browserLocationAdapter.redirectToSignIn();
};

export const resetAuthFailureStateForTests = () => {
  authRedirectInFlight = false;
};

export const setBrowserLocationAdapterForTests = (
  adapter: BrowserLocationAdapter | null,
) => {
  browserLocationAdapter = adapter ?? defaultBrowserLocationAdapter;
};

export const handleAuthErrorStatus = (status: number | undefined) => {
  if (status === 401) {
    handleAuthFailure();
  }

  if (status === 403) {
    showToast("Access denied");
  }
};

export function normalizeGeneratedApiUrl(
  url: AxiosRequestConfig["url"],
): AxiosRequestConfig["url"] {
  if (typeof url !== "string") {
    return url;
  }

  // apiClient.baseURL ("/api") is the SINGLE authoritative owner of the API prefix. Generated
  // clients emit either "/api/v1/..." or the coherence-scoped "/api/coherence/..."; strip a
  // leading "/api" (optionally followed by "/v1") so the prefix is applied exactly once. The
  // previous regex matched only "/api/v1", so "/api/coherence/..." was left intact and doubled
  // to "/api/api/coherence/...".
  const normalizedUrl = url.replace(/^\/?api(?:\/v1)?(?=\/|$)/, "");
  return normalizedUrl.length > 0 ? normalizedUrl : "/";
}

apiClient.interceptors.request.use(attachAuthToken);

apiClient.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    handleAuthErrorStatus(error.response?.status);

    return Promise.reject(error);
  },
);
