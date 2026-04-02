import { http, HttpResponse } from "@/mocks/msw";

const RACI_DATA = [
  {
    activity: "Project Planning",
    projectManager: "R",
    technicalLead: "A",
    stakeholder: "C",
    contractor: "I",
  },
  {
    activity: "Budget Approval",
    projectManager: "R",
    technicalLead: "C",
    stakeholder: "A",
    contractor: "I",
  },
  {
    activity: "Design Review",
    projectManager: "A",
    technicalLead: "R",
    stakeholder: "I",
    contractor: "C",
  },
  {
    activity: "Contract Negotiation",
    projectManager: "R",
    technicalLead: "C",
    stakeholder: "A",
    contractor: "C",
  },
  {
    activity: "Risk Assessment",
    projectManager: "R",
    technicalLead: "R",
    stakeholder: "I",
    contractor: "C",
  },
  {
    activity: "Quality Control",
    projectManager: "A",
    technicalLead: "R",
    stakeholder: "I",
    contractor: "R",
  },
  {
    activity: "Procurement",
    projectManager: "A",
    technicalLead: "C",
    stakeholder: "I",
    contractor: "R",
  },
  {
    activity: "Site Inspection",
    projectManager: "R",
    technicalLead: "R",
    stakeholder: "I",
    contractor: "A",
  },
];

export const raciHandlers = [
  http.get("/api/v1/raci", () => {
    return HttpResponse.json(RACI_DATA);
  }),

  http.get("/api/v1/projects/:projectId/raci", () => {
    return HttpResponse.json(RACI_DATA);
  }),
];
