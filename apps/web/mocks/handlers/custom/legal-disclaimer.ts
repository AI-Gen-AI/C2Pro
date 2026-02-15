import { HttpResponse, http } from "msw";

const DISCLAIMER_VERSION = "v1.0";
const acceptedScopes = new Set<string>();

function buildScope(projectId: string, request: Request): string {
  const tenantId = request.headers.get("x-tenant-id") ?? "tenant_demo";
  const userId = request.headers.get("x-user-id") ?? "user_demo";
  return `${tenantId}:${userId}:${DISCLAIMER_VERSION}:${projectId}`;
}

export const legalDisclaimerHandlers = [
  http.get("/api/v1/projects/:projectId/gates/gate-8/disclaimer/status", ({ params, request }) => {
    const projectId = String(params.projectId);
    const scope = buildScope(projectId, request);
    const accepted = acceptedScopes.has(scope);

    return HttpResponse.json({
      accepted,
      version: DISCLAIMER_VERSION,
      mustPrompt: !accepted,
      scope: scope.replace(`:${projectId}`, ""),
    });
  }),

  http.post("/api/v1/projects/:projectId/gates/gate-8/disclaimer/accept", async ({ params, request }) => {
    const projectId = String(params.projectId);
    const payload = (await request.json()) as { version?: string; forceError?: boolean };

    if (payload.forceError) {
      return HttpResponse.json(
        {
          code: "DISCLAIMER_PERSIST_FAILED",
          gateBlocked: true,
        },
        { status: 500 },
      );
    }

    const scope = buildScope(projectId, request);
    acceptedScopes.add(scope);

    return HttpResponse.json({
      accepted: true,
      gateBlocked: false,
      version: payload.version ?? DISCLAIMER_VERSION,
    });
  }),
];

