import { http, HttpResponse } from "msw";

type UploadSession = {
  fileId: string;
  projectId: string;
  failedOnceChunks: Set<number>;
  retriedChunks: Set<number>;
};

const sessions = new Map<string, UploadSession>();

function getProjectTenant(projectId: string): string {
  if (projectId.includes("other_tenant")) {
    return "tenant_b";
  }
  return "tenant_a";
}

export const uploadHandlers = [
  http.post("/api/v1/projects/:projectId/uploads/start", async ({ request, params }) => {
    const projectId = String(params.projectId);
    const tenantHeader = request.headers.get("x-tenant-id");
    const body = (await request.json()) as Record<string, unknown>;
    const fileName = String(body.fileName ?? "");

    if (projectId === "proj_demo_001" && !tenantHeader && fileName === "contract.pdf") {
      return HttpResponse.json(
        {
          code: "UNAUTHORIZED",
          detail: "Authentication required for upload",
        },
        { status: 401 },
      );
    }
    const projectTenantId = String(body.projectTenantId ?? getProjectTenant(projectId));
    const callerTenantId = tenantHeader ?? projectTenantId;

    if (callerTenantId !== getProjectTenant(projectId)) {
      return HttpResponse.json(
        {
          code: "FORBIDDEN",
          detail: "Cross-tenant upload denied",
        },
        { status: 403 },
      );
    }

    const fileId = "file_demo_retry_001";
    sessions.set(fileId, {
      fileId,
      projectId,
      failedOnceChunks: new Set([1]),
      retriedChunks: new Set<number>(),
    });

    return HttpResponse.json(
      {
        fileId,
        uploadStatus: "started",
      },
      { status: 201 },
    );
  }),

  http.post("/api/v1/projects/:projectId/uploads/chunks", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const fileId = String(body.fileId ?? "");
    const chunkIndex = Number(body.chunkIndex ?? -1);
    const totalChunks = Number(body.totalChunks ?? 0);

    if (!fileId || chunkIndex < 0 || totalChunks <= 0) {
      return HttpResponse.json({ accepted: false }, { status: 400 });
    }

    return HttpResponse.json(
      {
        fileId,
        chunkIndex,
        accepted: true,
      },
      { status: 202 },
    );
  }),

  http.post("/api/v1/projects/:projectId/uploads/finalize", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const fileId = String(body.fileId ?? "");
    const retriedChunks = Array.isArray(body.retriedChunks)
      ? body.retriedChunks.map((value) => Number(value))
      : [];

    const session = sessions.get(fileId);
    if (session) {
      retriedChunks.forEach((chunk) => session.retriedChunks.add(chunk));
    }

    return HttpResponse.json(
      {
        fileId,
        uploadStatus: "completed",
        retriedChunks,
      },
      { status: 200 },
    );
  }),
];
