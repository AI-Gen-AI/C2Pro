import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { showToast } from "@/lib/ui/toast";
import { useAuthStore } from "@/stores/auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

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
  useAuthStore.getState().clear();
  if (typeof window !== "undefined") {
    window.location.href = "/login";
  }
};

apiClient.interceptors.request.use(attachAuthToken);

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status;

    if (status === 401) {
      handleAuthFailure();
    }

    if (status === 403) {
      showToast("Sin permisos");
    }

    return Promise.reject(error);
  }
);
