/**
 * Test Suite ID: TASK-FRT-170
 * Purpose: expose the direct backend API base URL to browser-only upload flows.
 */

import { NextResponse } from "next/server";

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function normalizeAbsoluteApiBaseUrl(rawValue: string | undefined): string | null {
  const value = rawValue?.trim();

  if (!value || value.startsWith("/")) {
    return null;
  }

  const normalized = trimTrailingSlash(value);

  if (normalized.endsWith("/api/v1")) {
    return normalized;
  }

  if (normalized.endsWith("/api")) {
    return `${normalized}/v1`;
  }

  return `${normalized}/api/v1`;
}

export async function GET(): Promise<NextResponse> {
  const apiBaseUrl = normalizeAbsoluteApiBaseUrl(
    process.env.BACKEND_URL ?? process.env.NEXT_PUBLIC_API_URL,
  );

  return NextResponse.json(
    { apiBaseUrl },
    {
      headers: {
        "Cache-Control": "no-store",
      },
    },
  );
}
