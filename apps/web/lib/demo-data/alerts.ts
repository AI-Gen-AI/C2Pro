import type { ReviewAlert } from "@/components/features/alerts/AlertReviewCenter";

export const demoAlertsCenter = [
  {
    id: "AL-001",
    severity: "Critical",
    type: "Legal",
    title: "Contract Penalty Clause Violation Risk",
    description:
      "Clause 4.2.1 specifies 30-day delay penalty. Current trajectory shows 45-day delay.",
    project: "Petrochemical Plant EPC",
    status: "Open",
  },
  {
    id: "AL-002",
    severity: "Critical",
    type: "Financial",
    title: "Budget Overrun Threshold Exceeded",
    description: "Equipment procurement costs 25% above baseline estimates.",
    project: "Petrochemical Plant EPC",
    status: "Open",
  },
  {
    id: "AL-003",
    severity: "Critical",
    type: "Technical",
    title: "Equipment Compatibility Issue",
    description:
      "New compressor specifications conflict with existing infrastructure.",
    project: "Refinery Modernization",
    status: "In Progress",
  },
  {
    id: "AL-004",
    severity: "High",
    type: "Schedule",
    title: "Critical Path Delay - Foundation Work",
    description:
      "Foundation completion delayed by 12 days due to ground conditions.",
    project: "Petrochemical Plant EPC",
    status: "Open",
  },
  {
    id: "AL-005",
    severity: "High",
    type: "Scope",
    title: "Grid Connection Requirements Changed",
    description: "Utility company issued new interconnection requirements.",
    project: "Solar Farm Installation",
    status: "Open",
  },
  {
    id: "AL-006",
    severity: "Medium",
    type: "Financial",
    title: "Material Cost Variance",
    description: "Steel prices increased 8% above budgeted rates.",
    project: "Refinery Modernization",
    status: "Open",
  },
  {
    id: "AL-007",
    severity: "Medium",
    type: "Legal",
    title: "Permit Renewal Pending",
    description:
      "Environmental permit expires in 45 days. Renewal application in progress.",
    project: "Water Treatment Facility",
    status: "In Progress",
  },
] as const;

export const demoProjectAlerts: ReviewAlert[] = [
  {
    id: "a-1",
    title: "Delay penalty mismatch",
    severity: "high",
    status: "pending",
    clauseId: "c-101",
    assignee: "legal.reviewer",
  },
  {
    id: "a-2",
    title: "Insurance gap",
    severity: "critical",
    status: "pending",
    clauseId: "c-202",
    assignee: "risk.owner",
  },
];
