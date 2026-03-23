import { NextRequest, NextResponse } from "next/server";
import { buildBackendUrl } from "./route-utils";

type RouteContext = {
  params: Promise<{ proxy: string[] }>;
};

async function getProxyPath(context: RouteContext): Promise<string> {
  const resolvedParams = await context.params;
  return resolvedParams.proxy.join("/");
}

function buildHeaders(request: NextRequest): HeadersInit {
  const headers: Record<string, string> = {};

  const authorization = request.headers.get("authorization");
  const tenantId = request.headers.get("x-tenant-id");
  const contentType = request.headers.get("content-type");

  if (authorization) {
    headers.Authorization = authorization;
  }

  if (tenantId) {
    headers["X-Tenant-ID"] = tenantId;
  }

  if (contentType) {
    headers["Content-Type"] = contentType;
  }

  return headers;
}

async function proxyRequest(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  try {
    const path = await getProxyPath(context);
    const url = buildBackendUrl(path, request);
    const headers = buildHeaders(request);
    const init: RequestInit = {
      method,
      headers,
    };

    if (method !== "GET" && method !== "DELETE") {
      init.body = await request.arrayBuffer();
    }

    const response = await fetch(url, init);
    const responseBody = await response.arrayBuffer();

    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    return new NextResponse(responseBody, {
      status: response.status,
      headers: response.headers,
    });
  } catch (error) {
    console.error("API Proxy Error:", error);
    return NextResponse.json(
      { error: "Internal Server Error" },
      { status: 500 },
    );
  }
}

export async function GET(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  return proxyRequest("GET", request, context);
}

export async function POST(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  return proxyRequest("POST", request, context);
}

export async function PUT(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  return proxyRequest("PUT", request, context);
}

export async function PATCH(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  return proxyRequest("PATCH", request, context);
}

export async function DELETE(
  request: NextRequest,
  context: RouteContext,
): Promise<NextResponse> {
  return proxyRequest("DELETE", request, context);
}
