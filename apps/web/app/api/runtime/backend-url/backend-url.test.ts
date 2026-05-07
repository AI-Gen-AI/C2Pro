/**
 * Test Suite ID: TS-FRT-COV-001
 * Backlog: TASK-FRT-132..135
 * Purpose: Coverage-improvement tests for backend runtime URL normalization.
 */

import { afterEach, describe, expect, it } from "vitest";

import {
  GET,
  normalizeAbsoluteApiBaseUrl,
  trimTrailingSlash,
} from "./route";

const ORIGINAL_BACKEND_URL = process.env.BACKEND_URL;
const ORIGINAL_PUBLIC_API_URL = process.env.NEXT_PUBLIC_API_URL;

describe("backend runtime URL route", () => {
  afterEach(() => {
    process.env.BACKEND_URL = ORIGINAL_BACKEND_URL;
    process.env.NEXT_PUBLIC_API_URL = ORIGINAL_PUBLIC_API_URL;
  });

  it("normalizes configured absolute backend URLs to the API v1 base", () => {
    expect(trimTrailingSlash("https://api.example.com///")).toBe(
      "https://api.example.com",
    );
    expect(normalizeAbsoluteApiBaseUrl(" https://api.example.com ")).toBe(
      "https://api.example.com/api/v1",
    );
    expect(normalizeAbsoluteApiBaseUrl("https://api.example.com/api")).toBe(
      "https://api.example.com/api/v1",
    );
    expect(normalizeAbsoluteApiBaseUrl("https://api.example.com/api/v1/")).toBe(
      "https://api.example.com/api/v1",
    );
  });

  it("rejects empty and relative API base values", () => {
    expect(normalizeAbsoluteApiBaseUrl(undefined)).toBeNull();
    expect(normalizeAbsoluteApiBaseUrl("")).toBeNull();
    expect(normalizeAbsoluteApiBaseUrl(" /api ")).toBeNull();
  });

  it("returns a no-store response using BACKEND_URL before public fallback", async () => {
    process.env.BACKEND_URL = "https://backend.example.com";
    process.env.NEXT_PUBLIC_API_URL = "https://public.example.com";

    const response = await GET();

    expect(response.headers.get("Cache-Control")).toBe("no-store");
    await expect(response.json()).resolves.toEqual({
      apiBaseUrl: "https://backend.example.com/api/v1",
    });
  });

  it("falls back to NEXT_PUBLIC_API_URL when BACKEND_URL is missing", async () => {
    process.env.BACKEND_URL = "";
    process.env.NEXT_PUBLIC_API_URL = "https://public.example.com/api";

    const response = await GET();

    await expect(response.json()).resolves.toEqual({
      apiBaseUrl: "https://public.example.com/api/v1",
    });
  });
});
