import { apiClient } from "@/lib/api/client";
import { OpenAPI } from "@/lib/api/generated/core/OpenAPI";
import axios from "axios";

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

export const formatRequestError = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    if (error.response) {
      const status = error.response.status;
      const statusText = error.response.statusText || "API Error";
      return `API request failed (${status} ${statusText})`;
    }

    if (error.message) {
      return `API request failed: ${error.message}`;
    }
  }

  if (error instanceof AggregateError) {
    const causes = error.errors
      .map((entry) => (entry instanceof Error ? entry.message : String(entry)))
      .filter(Boolean)
      .join("; ");
    return causes
      ? `API request failed: ${causes}`
      : "API request failed: network error";
  }

  if (error instanceof Error && error.message) {
    return `API request failed: ${error.message}`;
  }

  return "API request failed: unknown error";
};

export const request = async <T>({ method, url, body, query }: RequestOptions) => {
  try {
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
  } catch (error) {
    throw new Error(formatRequestError(error), { cause: error });
  }
};
