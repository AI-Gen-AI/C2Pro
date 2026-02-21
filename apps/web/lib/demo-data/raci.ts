export const demoRaciData = [
  {
    activity: "Project Planning",
    projectManager: "A",
    technicalLead: "R",
    stakeholder: "C",
    contractor: "I",
  },
  {
    activity: "Requirements Gathering",
    projectManager: "R",
    technicalLead: "A",
    stakeholder: "C",
    contractor: "I",
  },
  {
    activity: "Design Review",
    projectManager: "A",
    technicalLead: "R",
    stakeholder: "C",
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
] as const;

export const raciTypes = {
  R: { label: "Responsible", color: "bg-blue-100 text-blue-700" },
  A: { label: "Accountable", color: "bg-green-100 text-green-700" },
  C: { label: "Consulted", color: "bg-yellow-100 text-yellow-700" },
  I: { label: "Informed", color: "bg-gray-100 text-gray-700" },
} as const;
