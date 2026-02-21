import {
  File,
  FileSpreadsheet,
  type LucideIcon,
  Image as ImageIcon,
} from "lucide-react";

export interface DemoDocument {
  id: string;
  name: string;
  type: string;
  project: string;
  projectId: string;
  uploadDate: string;
  size: string;
  pages: number;
  status: "Analyzed" | "Processing" | "Uploaded";
  alertsFound: number;
  criticalAlerts: number;
  icon: LucideIcon;
}

export const demoDocuments: DemoDocument[] = [
  {
    id: "DOC-001",
    name: "Contract_Final.pdf",
    type: "Contract",
    project: "Petrochemical Plant EPC",
    projectId: "PROJ-001",
    uploadDate: "2026-01-15",
    size: "2.4 MB",
    pages: 58,
    status: "Analyzed",
    alertsFound: 7,
    criticalAlerts: 1,
    icon: File,
  },
  {
    id: "DOC-002",
    name: "Schedule_v3.xlsx",
    type: "Schedule",
    project: "Petrochemical Plant EPC",
    projectId: "PROJ-001",
    uploadDate: "2026-01-14",
    size: "856 KB",
    pages: 15,
    status: "Analyzed",
    alertsFound: 4,
    criticalAlerts: 2,
    icon: FileSpreadsheet,
  },
  {
    id: "DOC-003",
    name: "Budget_Breakdown_Q1.pdf",
    type: "Budget",
    project: "Refinery Modernization",
    projectId: "PROJ-002",
    uploadDate: "2026-01-13",
    size: "1.8 MB",
    pages: 32,
    status: "Analyzed",
    alertsFound: 12,
    criticalAlerts: 5,
    icon: File,
  },
  {
    id: "DOC-004",
    name: "Technical_Specs_Rev2.pdf",
    type: "Technical",
    project: "Solar Farm Installation",
    projectId: "PROJ-004",
    uploadDate: "2026-01-12",
    size: "5.2 MB",
    pages: 124,
    status: "Processing",
    alertsFound: 0,
    criticalAlerts: 0,
    icon: File,
  },
  {
    id: "DOC-005",
    name: "Site_Photos.zip",
    type: "Photos",
    project: "Gas Pipeline Extension",
    projectId: "PROJ-003",
    uploadDate: "2026-01-10",
    size: "42.3 MB",
    pages: 0,
    status: "Uploaded",
    alertsFound: 0,
    criticalAlerts: 0,
    icon: ImageIcon,
  },
  {
    id: "DOC-006",
    name: "Amendment_No3.pdf",
    type: "Contract",
    project: "Water Treatment Facility",
    projectId: "PROJ-006",
    uploadDate: "2026-01-09",
    size: "1.2 MB",
    pages: 18,
    status: "Analyzed",
    alertsFound: 3,
    criticalAlerts: 0,
    icon: File,
  },
  {
    id: "DOC-007",
    name: "Quality_Report_Dec.pdf",
    type: "Quality",
    project: "Refinery Modernization",
    projectId: "PROJ-002",
    uploadDate: "2026-01-08",
    size: "3.1 MB",
    pages: 45,
    status: "Analyzed",
    alertsFound: 6,
    criticalAlerts: 1,
    icon: File,
  },
  {
    id: "DOC-008",
    name: "Procurement_List.xlsx",
    type: "Procurement",
    project: "LNG Terminal Phase 2",
    projectId: "PROJ-005",
    uploadDate: "2026-01-05",
    size: "642 KB",
    pages: 8,
    status: "Analyzed",
    alertsFound: 1,
    criticalAlerts: 0,
    icon: FileSpreadsheet,
  },
];
