/**
 * Demo Mode Context & Provider
 *
 * Manages switching between demo workspace (sample data) and production.
 * Demo mode provides read-only access with sample data for evaluation.
 *
 * @module contexts/demo-mode
 */

"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { useOrganization } from "@clerk/nextjs";

// =============================================================================
// Types
// =============================================================================

export interface DemoModeContextType {
  isDemoMode: boolean;
  demoOrganizationId: string | null;
  productionOrganizationId: string | null;
  toggleDemoMode: () => void;
  setDemoMode: (isDemoMode: boolean) => void;
  demoData: DemoDataType;
  isLoading: boolean;
}

export interface DemoDataType {
  projects: DemoProject[];
  alerts: DemoAlert[];
  stakeholders: DemoStakeholder[];
  documents: DemoDocument[];
  clauses: DemoClause[];
}

export interface DemoProject {
  id: string;
  name: string;
  description: string;
  status: "draft" | "active" | "completed";
  coherence_score: number;
  created_at: string;
  document_count: number;
  clause_count: number;
  alert_count: number;
  stakeholder_count: number;
}

export interface DemoAlert {
  id: string;
  project_id: string;
  type: string;
  severity: "low" | "medium" | "high" | "critical";
  message: string;
  affected_entity: string;
  created_at: string;
  status: "open" | "resolved" | "dismissed";
}

export interface DemoStakeholder {
  id: string;
  name: string;
  organization: string;
  role: string;
  power_level: "low" | "medium" | "high";
  interest_level: "low" | "medium" | "high";
  quadrant: string;
}

export interface DemoDocument {
  id: string;
  name: string;
  type: "contract" | "specification" | "proposal" | "other";
  size: number;
  created_at: string;
  clause_count: number;
}

export interface DemoClause {
  id: string;
  document_id: string;
  text: string;
  type: string;
  confidence: number;
  extracted_at: string;
}

// =============================================================================
// Context
// =============================================================================

const DemoModeContext = createContext<DemoModeContextType | undefined>(
  undefined
);

// =============================================================================
// Provider
// =============================================================================

export function DemoModeProvider({ children }: { children: React.ReactNode }) {
  const { organization } = useOrganization();
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  // Check if current organization is demo on mount
  useEffect(() => {
    if (organization) {
      const metadata = organization.publicMetadata as Record<string, unknown>;
      const isDemo = metadata?.is_demo === true;
      setIsDemoMode(isDemo);
      setIsLoading(false);
    } else {
      setIsDemoMode(false);
      setIsLoading(false);
    }
  }, [organization]);

  const toggleDemoMode = () => {
    setIsDemoMode(!isDemoMode);
  };

  const handleSetDemoMode = (mode: boolean) => {
    setIsDemoMode(mode);
  };

  return (
    <DemoModeContext.Provider
      value={{
        isDemoMode,
        demoOrganizationId: "demo-workspace",
        productionOrganizationId: organization?.id || null,
        toggleDemoMode,
        setDemoMode: handleSetDemoMode,
        demoData: SAMPLE_DATA,
        isLoading,
      }}
    >
      {children}
    </DemoModeContext.Provider>
  );
}

// =============================================================================
// Hooks
// =============================================================================

export function useDemoMode(): DemoModeContextType {
  const context = useContext(DemoModeContext);
  if (context === undefined) {
    throw new Error("useDemoMode must be used within DemoModeProvider");
  }
  return context;
}

export function useDemoData<T>(entityType: keyof DemoDataType): T[] {
  const { demoData } = useDemoMode();
  return (demoData[entityType] || []) as T[];
}

// =============================================================================
// Components
// =============================================================================

export function DemoModeIndicator() {
  const { isDemoMode } = useDemoMode();

  if (!isDemoMode) return null;

  return (
    <div className="bg-yellow-600/20 border-b border-yellow-600/30 px-4 py-2 text-center">
      <p className="text-yellow-400 text-sm font-medium">
        Demo Mode Active - Using Sample Data (Read-Only)
      </p>
    </div>
  );
}

export function DemoModeToggle() {
  const { isDemoMode, toggleDemoMode } = useDemoMode();

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg">
      <label className="flex items-center cursor-pointer">
        <input
          type="checkbox"
          checked={isDemoMode}
          onChange={toggleDemoMode}
          className="w-4 h-4 rounded border-slate-600 bg-slate-700"
        />
        <span className="ml-2 text-sm text-slate-300">
          {isDemoMode ? "Demo Mode" : "Production Mode"}
        </span>
      </label>
    </div>
  );
}

// =============================================================================
// Sample Data
// =============================================================================

export const SAMPLE_DATA: DemoDataType = {
  projects: [
    {
      id: "demo-proj-001",
      name: "Example EPC Project - Oil & Gas Facility",
      description:
        "Engineering, Procurement, and Construction project for offshore oil platform",
      status: "active",
      coherence_score: 85,
      created_at: "2026-01-01T08:00:00Z",
      document_count: 12,
      clause_count: 45,
      alert_count: 3,
      stakeholder_count: 8,
    },
    {
      id: "demo-proj-002",
      name: "Chemical Plant Expansion",
      description: "Expansion of existing chemical manufacturing facility",
      status: "active",
      coherence_score: 78,
      created_at: "2026-01-15T10:30:00Z",
      document_count: 8,
      clause_count: 32,
      alert_count: 5,
      stakeholder_count: 6,
    },
    {
      id: "demo-proj-003",
      name: "Power Generation Infrastructure",
      description: "New solar farm and grid connection project",
      status: "draft",
      coherence_score: 92,
      created_at: "2026-02-01T14:20:00Z",
      document_count: 6,
      clause_count: 28,
      alert_count: 1,
      stakeholder_count: 5,
    },
  ],

  alerts: [
    {
      id: "demo-alert-001",
      project_id: "demo-proj-001",
      type: "scope_mismatch",
      severity: "high",
      message:
        'WBS item "Mechanical Assembly" not covered by any contract clause',
      affected_entity: "WBS-001.02",
      created_at: "2026-02-15T10:30:00Z",
      status: "open",
    },
    {
      id: "demo-alert-002",
      project_id: "demo-proj-001",
      type: "budget_variance",
      severity: "medium",
      message:
        'BOM item "Centrifugal Pump" cost exceeds allocated budget by 12%',
      affected_entity: "BOM-045",
      created_at: "2026-02-14T15:45:00Z",
      status: "open",
    },
    {
      id: "demo-alert-003",
      project_id: "demo-proj-001",
      type: "schedule_conflict",
      severity: "high",
      message:
        "Critical path item delivery timeline conflicts with contract milestone",
      affected_entity: "CP-003",
      created_at: "2026-02-13T09:15:00Z",
      status: "resolved",
    },
    {
      id: "demo-alert-004",
      project_id: "demo-proj-002",
      type: "stakeholder_gap",
      severity: "medium",
      message: "Quality Control Manager role not assigned to any stakeholder",
      affected_entity: "Role-QC-001",
      created_at: "2026-02-12T11:00:00Z",
      status: "open",
    },
    {
      id: "demo-alert-005",
      project_id: "demo-proj-002",
      type: "legal_compliance",
      severity: "critical",
      message:
        "Environmental permits clause missing required compliance standards",
      affected_entity: "Clause-ENV-004",
      created_at: "2026-02-11T08:30:00Z",
      status: "open",
    },
  ],

  stakeholders: [
    {
      id: "demo-sh-001",
      name: "Dr. Sarah Johnson",
      organization: "TechCore Engineering",
      role: "Project Manager",
      power_level: "high",
      interest_level: "high",
      quadrant: "manage_closely",
    },
    {
      id: "demo-sh-002",
      name: "Michael Chen",
      organization: "Supply Chain Excellence",
      role: "Procurement Director",
      power_level: "high",
      interest_level: "high",
      quadrant: "manage_closely",
    },
    {
      id: "demo-sh-003",
      name: "Emma Rodriguez",
      organization: "TechCore Engineering",
      role: "Quality Assurance Lead",
      power_level: "medium",
      interest_level: "high",
      quadrant: "keep_satisfied",
    },
    {
      id: "demo-sh-004",
      name: "James Wilson",
      organization: "Global Construction",
      role: "Site Manager",
      power_level: "high",
      interest_level: "medium",
      quadrant: "keep_satisfied",
    },
    {
      id: "demo-sh-005",
      name: "Priya Patel",
      organization: "Financial Services Inc",
      role: "Finance Controller",
      power_level: "medium",
      interest_level: "medium",
      quadrant: "monitor",
    },
  ],

  documents: [
    {
      id: "demo-doc-001",
      name: "Main EPC Contract",
      type: "contract",
      size: 2500000,
      created_at: "2026-01-01T08:00:00Z",
      clause_count: 18,
    },
    {
      id: "demo-doc-002",
      name: "Technical Specifications",
      type: "specification",
      size: 3200000,
      created_at: "2026-01-02T09:30:00Z",
      clause_count: 12,
    },
    {
      id: "demo-doc-003",
      name: "Design & Engineering Proposal",
      type: "proposal",
      size: 1800000,
      created_at: "2026-01-05T14:15:00Z",
      clause_count: 8,
    },
    {
      id: "demo-doc-004",
      name: "Procurement Strategy Document",
      type: "other",
      size: 950000,
      created_at: "2026-01-08T10:45:00Z",
      clause_count: 7,
    },
  ],

  clauses: [
    {
      id: "demo-clause-001",
      document_id: "demo-doc-001",
      text: "The Contractor shall provide all labor, materials, and equipment necessary to complete the work in accordance with the specifications.",
      type: "scope_of_work",
      confidence: 0.98,
      extracted_at: "2026-01-01T08:30:00Z",
    },
    {
      id: "demo-clause-002",
      document_id: "demo-doc-001",
      text: "Payment shall be made within 30 days of invoice submission, subject to satisfactory completion of work per agreed milestones.",
      type: "payment_terms",
      confidence: 0.96,
      extracted_at: "2026-01-01T08:30:00Z",
    },
    {
      id: "demo-clause-003",
      document_id: "demo-doc-001",
      text: "The project shall be completed by June 30, 2026, with liquidated damages of $10,000 per day for delays beyond this date.",
      type: "schedule",
      confidence: 0.97,
      extracted_at: "2026-01-01T08:30:00Z",
    },
    {
      id: "demo-clause-004",
      document_id: "demo-doc-002",
      text: "All materials shall meet ISO 9001 quality standards and undergo third-party inspection before installation.",
      type: "quality",
      confidence: 0.94,
      extracted_at: "2026-01-02T09:45:00Z",
    },
    {
      id: "demo-clause-005",
      document_id: "demo-doc-002",
      text: "Environmental impact assessment required per EPA regulations; project site must maintain compliance throughout execution.",
      type: "legal_compliance",
      confidence: 0.92,
      extracted_at: "2026-01-02T09:45:00Z",
    },
  ],
};
