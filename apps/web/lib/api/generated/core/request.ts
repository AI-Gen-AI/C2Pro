import { apiClient } from "@/lib/api/client";
import { OpenAPI } from "@/lib/api/generated/core/OpenAPI";

type RequestOptions = {
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  url: string;
  body?: unknown;
  query?: Record<string, unknown>;
};

const buildHeaders = async () => {
  const headers: Record<string, string> = {};
  if (OpenAPI.TOKEN) {
    const token =
      typeof OpenAPI.TOKEN === "string" ? OpenAPI.TOKEN : await OpenAPI.TOKEN();
    if (token) {
      headers.Authorization = `Bearer ${token}`;
    }
  }
  return headers;
};

export const request = async <T>({ method, url, body, query }: RequestOptions) => {
  const headers = await buildHeaders();
  const response = await apiClient.request<T>({
    method,
    url,
    data: body,
    params: query,
    headers,
    baseURL: OpenAPI.BASE || apiClient.defaults.baseURL,
  });

  return response.data;
};
