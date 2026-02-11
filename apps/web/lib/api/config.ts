import { OpenAPI } from "@/lib/api/generated/core/OpenAPI";
import { apiClient } from "@/lib/api/client";
import { useAuthStore } from "@/stores/auth";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

OpenAPI.BASE = API_BASE_URL;
OpenAPI.TOKEN = async () => {
  return useAuthStore.getState().token ?? "";
};

apiClient.defaults.baseURL = OpenAPI.BASE;
