import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

const fetchMock = vi.fn();
const getTokenMock = vi.hoisted(() => vi.fn());

vi.mock("@clerk/nextjs/server", () => ({
  auth: vi.fn(async () => ({ getToken: getTokenMock })),
}));

let GET: typeof import("./route").GET;
let buildBackendUrl: typeof import("./route-utils").buildBackendUrl;

describe("API proxy coherence routing", () => {
  beforeEach(async () => {
    // route-utils resolves the server-only backend URL during module import.
    vi.stubEnv("BACKEND_URL", "http://localhost:8000/api/v1");
    vi.stubGlobal("fetch", fetchMock);
    getTokenMock.mockReset();
    getTokenMock.mockResolvedValue(null);
    vi.resetModules();

    ({ GET } = await import("./route"));
    ({ buildBackendUrl } = await import("./route-utils"));
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("routes coherence paths to canonical backend namespace", () => {
    const request = new NextRequest(
      "http://localhost:3000/api/coherence/dashboard/proj-1?foo=bar",
    );

    const url = buildBackendUrl("coherence/dashboard/proj-1", request);

    expect(url).toBe(
      "http://localhost:8000/api/v1/coherence/dashboard/proj-1?foo=bar",
    );
  });

  it("routes /api/coherence/... paths (Orval legacy) to canonical backend namespace", () => {
    const request = new NextRequest(
      "http://localhost:3000/api/api/coherence/dashboard/proj-1",
    );

    const url = buildBackendUrl("api/coherence/dashboard/proj-1", request);

    expect(url).toBe("http://localhost:8000/api/v1/coherence/dashboard/proj-1");
  });

  it("keeps regular API paths on the standard v1 namespace", () => {
    const request = new NextRequest(
      "http://localhost:3000/api/projects/proj-1",
    );

    const url = buildBackendUrl("projects/proj-1", request);

    expect(url).toBe("http://localhost:8000/api/v1/projects/proj-1");
  });

  it("normalizes generated /api/v1/... proxy paths without duplicating the v1 namespace", () => {
    const request = new NextRequest(
      "http://localhost:3000/api/v1/projects?limit=20",
    );

    const url = buildBackendUrl("v1/projects", request);

    expect(url).toBe("http://localhost:8000/api/v1/projects?limit=20");
  });

  it("normalizes legacy /api/api/v1/... proxy paths from generated clients", () => {
    const request = new NextRequest(
      "http://localhost:3000/api/api/v1/projects/proj-1",
    );

    const url = buildBackendUrl("api/v1/projects/proj-1", request);

    expect(url).toBe("http://localhost:8000/api/v1/projects/proj-1");
  });

  it("injects the Clerk bearer server-side for SSE without putting it in the URL", async () => {
    getTokenMock.mockResolvedValue("server-clerk-token");
    fetchMock.mockResolvedValue(
      new Response("event: complete\ndata: {}\n\n", {
        status: 200,
        headers: { "content-type": "text/event-stream" },
      }),
    );

    const request = new NextRequest(
      "http://localhost:3000/api/v1/analysis/projects/proj-1/process/stream",
    );

    const response = await GET(request, {
      params: Promise.resolve({
        proxy: ["v1", "analysis", "projects", "proj-1", "process", "stream"],
      }),
    });

    expect(response.status).toBe(200);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "http://localhost:8000/api/v1/analysis/projects/proj-1/process/stream",
    );
    expect(url).not.toContain("access_token");
    expect(new Headers(init.headers).get("authorization")).toBe(
      "Bearer server-clerk-token",
    );
  });

  it("preserves backend 401 responses for the frontend auth handler", async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Unauthorized" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    );

    const request = new NextRequest(
      "http://localhost:3000/api/projects/proj-1",
    );

    const response = await GET(request, {
      params: Promise.resolve({ proxy: ["projects", "proj-1"] }),
    });

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ detail: "Unauthorized" });
  });
});
