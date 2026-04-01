import axios from "axios/dist/browser/axios.cjs";
import type {
  AxiosError,
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

export async function orvalApiClient<T>(
  config: AxiosRequestConfig,
): Promise<T> {
  const response = await apiClient.request<T>(config);
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

  const pathname = window.location.pathname ?? "/";
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
  showToast("Sesión expirada o inválida");
  window.location.href = "/sign-in";
};

export const resetAuthFailureStateForTests = () => {
  authRedirectInFlight = false;
};

export const handleAuthErrorStatus = (status: number | undefined) => {
  if (status === 401) {
    handleAuthFailure();
  }

  if (status === 403) {
    showToast("Sin permisos");
  }
};

apiClient.interceptors.request.use(attachAuthToken);

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    handleAuthErrorStatus(error.response?.status);

    return Promise.reject(error);
  },
);
