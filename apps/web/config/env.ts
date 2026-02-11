export const env = {
  APP_MODE: (process.env.NEXT_PUBLIC_APP_MODE ?? "production") as
    | "production"
    | "demo",
  API_BASE_URL:
    process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1",
  IS_DEMO: process.env.NEXT_PUBLIC_APP_MODE === "demo",
  IS_DEV: process.env.NODE_ENV === "development",
  SENTRY_DSN: process.env.NEXT_PUBLIC_SENTRY_DSN,
} as const;
