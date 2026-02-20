import { http, HttpResponse } from "msw";
import { db, DEMO_TENANT_ID, DEMO_USER_ID } from "../../data";

export const demoDataHandlers = [
  // ── Projects ──────────────────────────────────────────────
  http.get("/api/v1/projects", () => {
    const items = db.project.getAll();
    return HttpResponse.json({
      items,
      total: items.length,
      page: 1,
      page_size: items.length,
      total_pages: 1,
      has_next: false,
      has_prev: false,
    });
  }),

  http.get("/api/v1/projects/:projectId", ({ params }) => {
    const project = db.project.findFirst({
      where: { id: { equals: String(params.projectId) } },
    });

    if (!project) {
      return new HttpResponse(null, { status: 404 });
    }

    return HttpResponse.json(project);
  }),

  // ── Documents ─────────────────────────────────────────────
  http.get("/api/v1/projects/:projectId/documents", ({ params }) => {
    const projectId = String(params.projectId);
    const documents = db.document.findMany({
      where: { projectId: { equals: projectId } },
    });

    return HttpResponse.json(documents);
  }),

  http.get("/api/v1/documents/:documentId/clauses", ({ params }) => {
    const documentId = String(params.documentId);
    const clauses = db.clause.findMany({
      where: { documentId: { equals: documentId } },
    });

    return HttpResponse.json(clauses);
  }),

  // ── Alerts ────────────────────────────────────────────────
  // Nested route used by project detail views
  http.get("/api/v1/projects/:projectId/alerts", ({ params }) => {
    const projectId = String(params.projectId);
    const alerts = db.alert.findMany({
      where: { projectId: { equals: projectId } },
    });

    return HttpResponse.json(alerts);
  }),

  // Flat route used by useDocumentAlerts → GET /alerts?document_id=...
  http.get("/api/v1/alerts", ({ request }) => {
    const url = new URL(request.url);
    const documentId = url.searchParams.get("document_id");

    if (documentId) {
      // Map document → project, then return that project's alerts
      const doc = db.document.findFirst({
        where: { id: { equals: documentId } },
      });
      if (!doc) return HttpResponse.json([]);

      const alerts = db.alert.findMany({
        where: { projectId: { equals: doc.projectId } },
      });
      return HttpResponse.json(alerts);
    }

    return HttpResponse.json(db.alert.getAll());
  }),

  // ── Stakeholders ──────────────────────────────────────────
  // Nested route used by project detail views
  http.get("/api/v1/projects/:projectId/stakeholders", ({ params }) => {
    const projectId = String(params.projectId);
    const stakeholders = db.stakeholder.findMany({
      where: { projectId: { equals: projectId } },
    });

    return HttpResponse.json(stakeholders);
  }),

  // Flat route used by useStakeholders → GET /stakeholders?project_id=...
  http.get("/api/v1/stakeholders", ({ request }) => {
    const url = new URL(request.url);
    const projectId = url.searchParams.get("project_id");

    if (projectId) {
      const stakeholders = db.stakeholder.findMany({
        where: { projectId: { equals: projectId } },
      });
      return HttpResponse.json(stakeholders);
    }

    return HttpResponse.json(db.stakeholder.getAll());
  }),

  // PATCH used by useUpdateStakeholder
  http.patch("/api/v1/stakeholders/:stakeholderId", async ({ params, request }) => {
    const stakeholderId = String(params.stakeholderId);
    const body = (await request.json()) as Record<string, unknown>;

    const existing = db.stakeholder.findFirst({
      where: { id: { equals: stakeholderId } },
    });

    if (!existing) {
      return new HttpResponse(null, { status: 404 });
    }

    const updated = db.stakeholder.update({
      where: { id: { equals: stakeholderId } },
      data: body,
    });

    return HttpResponse.json(updated);
  }),

  // ── WBS ───────────────────────────────────────────────────
  http.get("/api/v1/projects/:projectId/wbs", ({ params }) => {
    const projectId = String(params.projectId);
    const items = db.wbsItem.findMany({
      where: { projectId: { equals: projectId } },
    });

    return HttpResponse.json(items);
  }),

  // ── Auth ──────────────────────────────────────────────────
  http.post("/api/v1/auth/login", async ({ request }) => {
    const body = (await request.json()) as { email?: string; password?: string };

    if (!body.email || !body.password) {
      return HttpResponse.json(
        { detail: "Email and password are required" },
        { status: 422 }
      );
    }

    const user = db.user.findFirst({
      where: { email: { equals: body.email } },
    });
    const tenant = db.tenant.findFirst({
      where: { id: { equals: DEMO_TENANT_ID } },
    });

    return HttpResponse.json({
      access_token: "msw_demo_access_token",
      refresh_token: "msw_demo_refresh_token",
      token_type: "bearer",
      user: user ?? {
        id: DEMO_USER_ID,
        email: body.email,
        first_name: "Demo",
        last_name: "User",
        role: "analyst",
        is_active: true,
        tenant_id: DEMO_TENANT_ID,
        created_at: new Date().toISOString(),
      },
      tenant: tenant ?? { id: DEMO_TENANT_ID, name: "C2Pro Demo Tenant" },
    });
  }),

  http.post("/api/v1/auth/register", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;

    return HttpResponse.json(
      {
        access_token: "msw_demo_access_token",
        refresh_token: "msw_demo_refresh_token",
        token_type: "bearer",
        user: {
          id: "user_new",
          email: body.email ?? "new@c2pro.io",
          first_name: body.first_name ?? "New",
          last_name: body.last_name ?? "User",
          role: "analyst",
          is_active: true,
          tenant_id: DEMO_TENANT_ID,
          created_at: new Date().toISOString(),
        },
        tenant: { id: DEMO_TENANT_ID, name: String(body.company_name ?? "New Tenant") },
      },
      { status: 201 }
    );
  }),

  http.post("/api/v1/auth/refresh", () => {
    return HttpResponse.json({
      access_token: "msw_demo_access_token_refreshed",
      refresh_token: "msw_demo_refresh_token_refreshed",
      token_type: "bearer",
    });
  }),

  http.get("/api/v1/auth/me", () => {
    const user = db.user.findFirst({
      where: { id: { equals: DEMO_USER_ID } },
    });
    const tenant = db.tenant.findFirst({
      where: { id: { equals: DEMO_TENANT_ID } },
    });

    return HttpResponse.json({ user, tenant });
  }),

  http.post("/api/v1/auth/logout", () => {
    return new HttpResponse(null, { status: 204 });
  }),
];
