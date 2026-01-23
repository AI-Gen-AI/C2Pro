import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import { showToast } from "@/lib/ui/toast";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

const ACCESS_TOKEN_KEY = "c2pro_access_token";
const REFRESH_TOKEN_KEY = "c2pro_refresh_token";
const USER_DATA_KEY = "c2pro_user_data";
const TENANT_DATA_KEY = "c2pro_tenant_data";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
});

const attachAuthToken = (config: InternalAxiosRequestConfig) => {
  if (typeof window === "undefined") {
    return config;
  }

  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (token) {
    const headers = config.headers ?? {};
    headers.Authorization = `Bearer ${token}`;
    config.headers = headers;
  }

  return config;
};

const handleAuthFailure = () => {
  if (typeof window === "undefined") {
    return;
  }

  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_DATA_KEY);
  localStorage.removeItem(TENANT_DATA_KEY);
  window.location.href = "/login";
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
