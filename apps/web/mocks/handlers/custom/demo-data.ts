import { http, HttpResponse } from "msw";
import { db } from "../../data";

export const demoDataHandlers = [
  http.get("/api/v1/projects", () => {
    return HttpResponse.json(db.project.getAll());
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
  http.get("/api/v1/projects/:projectId/documents", ({ params }) => {
    const projectId = String(params.projectId);
    const documents = db.document.findMany({
      where: { projectId: { equals: projectId } },
    });

    return HttpResponse.json(documents);
  }),
  http.get("/api/v1/projects/:projectId/alerts", ({ params }) => {
    const projectId = String(params.projectId);
    const alerts = db.alert.findMany({
      where: { projectId: { equals: projectId } },
    });

    return HttpResponse.json(alerts);
  }),
  http.get("/api/v1/projects/:projectId/stakeholders", ({ params }) => {
    const projectId = String(params.projectId);
    const stakeholders = db.stakeholder.findMany({
      where: { projectId: { equals: projectId } },
    });

    return HttpResponse.json(stakeholders);
  }),
  http.get("/api/v1/projects/:projectId/wbs", ({ params }) => {
    const projectId = String(params.projectId);
    const items = db.wbsItem.findMany({
      where: { projectId: { equals: projectId } },
    });

    return HttpResponse.json(items);
  }),
  http.get("/api/v1/documents/:documentId/clauses", ({ params }) => {
    const documentId = String(params.documentId);
    const clauses = db.clause.findMany({
      where: { documentId: { equals: documentId } },
    });

    return HttpResponse.json(clauses);
  }),
];
