import { describe, expect, it } from "vitest";
import { db, seedDemoData } from "@/mocks/data";

describe("S2-01 MSW seed data", () => {
  it("provides deterministic demo data across the 8 core entities", () => {
    seedDemoData();

    const tenants = db.tenant.getAll();
    const users = db.user.getAll();
    const projects = db.project.getAll();
    const documents = db.document.getAll();
    const clauses = db.clause.getAll();
    const alerts = db.alert.getAll();
    const stakeholders = db.stakeholder.getAll();
    const wbsItems = db.wbsItem.getAll();

    expect(tenants).toHaveLength(1);
    expect(users).toHaveLength(1);
    expect(projects).toHaveLength(2);
    expect(documents).toHaveLength(2);
    expect(clauses).toHaveLength(3);
    expect(alerts).toHaveLength(2);
    expect(stakeholders).toHaveLength(2);
    expect(wbsItems).toHaveLength(2);

    const projectIds = new Set(projects.map((project) => project.id));
    const documentIds = new Set(documents.map((document) => document.id));

    expect(projects[0]?.id).toBe("proj_demo_001");
    expect(documents[0]?.projectId).toBe("proj_demo_001");

    expect(
      projects.every((project) => project.tenantId === tenants[0]?.id),
    ).toBe(true);
    expect(
      documents.every((document) => projectIds.has(document.projectId)),
    ).toBe(true);
    expect(
      clauses.every((clause) => documentIds.has(clause.documentId)),
    ).toBe(true);
    expect(alerts.every((alert) => projectIds.has(alert.projectId))).toBe(true);
    expect(
      stakeholders.every((stakeholder) => projectIds.has(stakeholder.projectId)),
    ).toBe(true);
    expect(wbsItems.every((item) => projectIds.has(item.projectId))).toBe(true);
  });
});
