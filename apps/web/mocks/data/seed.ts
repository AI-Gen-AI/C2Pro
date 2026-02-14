import { db } from "./db";

let seeded = false;

export const DEMO_TENANT_ID = "tenant_demo";
export const DEMO_USER_ID = "user_demo";
export const DEMO_PROJECT_ID = "proj_demo_001";

export function seedDemoData() {
  if (seeded) return;
  seeded = true;

  db.tenant.create({
    id: DEMO_TENANT_ID,
    name: "C2Pro Demo Tenant",
  });

  db.user.create({
    id: DEMO_USER_ID,
    tenantId: DEMO_TENANT_ID,
    name: "Jordan Demo",
    email: "demo@c2pro.io",
    role: "analyst",
  });

  db.project.create({
    id: DEMO_PROJECT_ID,
    tenantId: DEMO_TENANT_ID,
    name: "Torre Skyline",
    status: "active",
  });

  db.project.create({
    id: "proj_demo_002",
    tenantId: DEMO_TENANT_ID,
    name: "Atlas Plaza",
    status: "processing",
  });

  db.document.create({
    id: "doc_demo_001",
    projectId: DEMO_PROJECT_ID,
    name: "Contract - Torre Skyline.pdf",
    status: "analyzed",
  });

  db.document.create({
    id: "doc_demo_002",
    projectId: "proj_demo_002",
    name: "Spec Sheet - Atlas Plaza.pdf",
    status: "processing",
  });

  db.clause.create({
    id: "clause_demo_001",
    documentId: "doc_demo_001",
    text: "The contractor shall provide monthly progress reports.",
    clauseType: "reporting",
  });

  db.clause.create({
    id: "clause_demo_002",
    documentId: "doc_demo_001",
    text: "Liquidated damages apply after 15 days of delay.",
    clauseType: "legal",
  });

  db.clause.create({
    id: "clause_demo_003",
    documentId: "doc_demo_002",
    text: "All steel must meet ASTM A36 standards.",
    clauseType: "technical",
  });

  db.alert.create({
    id: "alert_demo_001",
    projectId: DEMO_PROJECT_ID,
    category: "TIME",
    severity: "high",
    status: "open",
    message: "Schedule exceeds contractual completion date by 12 days.",
  });

  db.alert.create({
    id: "alert_demo_002",
    projectId: DEMO_PROJECT_ID,
    category: "LEGAL",
    severity: "medium",
    status: "open",
    message: "Penalty clause referenced without milestone mapping.",
  });

  db.stakeholder.create({
    id: "stk_demo_001",
    projectId: DEMO_PROJECT_ID,
    name: "Lina Ortega",
    role: "Owner Rep",
    power: 9,
    interest: 8,
  });

  db.stakeholder.create({
    id: "stk_demo_002",
    projectId: DEMO_PROJECT_ID,
    name: "Marco Diaz",
    role: "General Contractor",
    power: 8,
    interest: 7,
  });

  db.wbsItem.create({
    id: "wbs_demo_001",
    projectId: DEMO_PROJECT_ID,
    code: "1.1",
    name: "Site Preparation",
    level: 2,
  });

  db.wbsItem.create({
    id: "wbs_demo_002",
    projectId: DEMO_PROJECT_ID,
    code: "1.2",
    name: "Foundation",
    level: 2,
  });
}
