import { db } from "./db";

let seeded = false;

export const DEMO_TENANT_ID = "tenant_demo";
export const DEMO_USER_ID = "user_demo";
export const DEMO_PROJECT_ID = "proj_demo_001";

export function seedDemoData() {
  if (seeded) return;
  seeded = true;

  // --- Tenant & User ---

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

  // --- Projects (6) ---

  db.project.create({
    id: DEMO_PROJECT_ID,
    tenantId: DEMO_TENANT_ID,
    name: "Petrochemical Plant EPC",
    status: "active",
  });

  db.project.create({
    id: "proj_demo_002",
    tenantId: DEMO_TENANT_ID,
    name: "Refinery Modernization",
    status: "active",
  });

  db.project.create({
    id: "proj_demo_003",
    tenantId: DEMO_TENANT_ID,
    name: "Gas Pipeline Extension",
    status: "on_hold",
  });

  db.project.create({
    id: "proj_demo_004",
    tenantId: DEMO_TENANT_ID,
    name: "Solar Farm Installation",
    status: "active",
  });

  db.project.create({
    id: "proj_demo_005",
    tenantId: DEMO_TENANT_ID,
    name: "LNG Terminal Phase 2",
    status: "completed",
  });

  db.project.create({
    id: "proj_demo_006",
    tenantId: DEMO_TENANT_ID,
    name: "Water Treatment Facility",
    status: "active",
  });

  // --- Documents ---

  db.document.create({
    id: "doc_demo_001",
    projectId: DEMO_PROJECT_ID,
    name: "Contract - Petrochemical Plant.pdf",
    status: "analyzed",
  });

  db.document.create({
    id: "doc_demo_002",
    projectId: "proj_demo_002",
    name: "Spec Sheet - Refinery Modernization.pdf",
    status: "processing",
  });

  // --- Clauses ---

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

  // --- Alerts (8) ---

  db.alert.create({
    id: "alert_demo_001",
    projectId: DEMO_PROJECT_ID,
    category: "LEGAL",
    severity: "critical",
    status: "open",
    message: "Contract Penalty Clause Violation Risk — Clause 4.2.1 specifies 30-day delay penalty, current trajectory shows 45-day delay.",
  });

  db.alert.create({
    id: "alert_demo_002",
    projectId: DEMO_PROJECT_ID,
    category: "BUDGET",
    severity: "critical",
    status: "open",
    message: "Budget Overrun Threshold Exceeded — Equipment procurement costs 23% above baseline estimates.",
  });

  db.alert.create({
    id: "alert_demo_003",
    projectId: "proj_demo_002",
    category: "TECHNICAL",
    severity: "critical",
    status: "open",
    message: "Equipment Compatibility Issue — New compressor specifications conflict with existing infrastructure.",
  });

  db.alert.create({
    id: "alert_demo_004",
    projectId: DEMO_PROJECT_ID,
    category: "TIME",
    severity: "high",
    status: "open",
    message: "Critical Path Delay — Foundation completion delayed by 12 days due to ground conditions.",
  });

  db.alert.create({
    id: "alert_demo_005",
    projectId: "proj_demo_004",
    category: "SCOPE",
    severity: "high",
    status: "open",
    message: "Grid Connection Requirements Changed — Utility company issued new interconnection requirements.",
  });

  db.alert.create({
    id: "alert_demo_006",
    projectId: "proj_demo_002",
    category: "BUDGET",
    severity: "medium",
    status: "open",
    message: "Material Cost Variance — Steel prices increased 8% above budgeted rates.",
  });

  db.alert.create({
    id: "alert_demo_007",
    projectId: "proj_demo_006",
    category: "LEGAL",
    severity: "medium",
    status: "open",
    message: "Permit Renewal Pending — Environmental permit expires in 45 days.",
  });

  db.alert.create({
    id: "alert_demo_008",
    projectId: "proj_demo_003",
    category: "TIME",
    severity: "low",
    status: "resolved",
    message: "Weather Delay — Expected 3-day delay due to adverse weather conditions.",
  });

  // --- Stakeholders (7) ---

  db.stakeholder.create({
    id: "stk_demo_001",
    projectId: DEMO_PROJECT_ID,
    name: "John Mitchell",
    role: "Project Sponsor",
    power: 9,
    interest: 9,
  });

  db.stakeholder.create({
    id: "stk_demo_002",
    projectId: DEMO_PROJECT_ID,
    name: "Sarah Chen",
    role: "Project Manager",
    power: 8,
    interest: 10,
  });

  db.stakeholder.create({
    id: "stk_demo_003",
    projectId: DEMO_PROJECT_ID,
    name: "Robert Williams",
    role: "CFO",
    power: 9,
    interest: 4,
  });

  db.stakeholder.create({
    id: "stk_demo_004",
    projectId: DEMO_PROJECT_ID,
    name: "Maria Garcia",
    role: "Legal Counsel",
    power: 7,
    interest: 3,
  });

  db.stakeholder.create({
    id: "stk_demo_005",
    projectId: DEMO_PROJECT_ID,
    name: "David Kim",
    role: "Lead Engineer",
    power: 4,
    interest: 9,
  });

  db.stakeholder.create({
    id: "stk_demo_006",
    projectId: DEMO_PROJECT_ID,
    name: "Lisa Brown",
    role: "QA Manager",
    power: 3,
    interest: 8,
  });

  db.stakeholder.create({
    id: "stk_demo_007",
    projectId: DEMO_PROJECT_ID,
    name: "James Taylor",
    role: "Equipment Supplier",
    power: 3,
    interest: 4,
  });

  // --- WBS Items ---

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
