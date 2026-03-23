import { env } from "@/config/env";
import { apiClient } from "@/lib/api/client";

apiClient.defaults.baseURL = env.API_BASE_URL;
