/**
 * Project-related TypeScript type definitions
 * Based on backend Pydantic schemas
 */

export type ProjectStatus = 'draft' | 'active' | 'completed' | 'archived' | 'on_hold';

export type ProjectType =
  | 'epc'
  | 'civil'
  | 'building'
  | 'maritime'
  | 'chemical'
  | 'energy'
  | 'municipal'
  | 'oil_gas'
  | 'mining'
  | 'other';

export type Severity = 'critical' | 'high' | 'medium' | 'low';

export type AlertStatus = 'open' | 'in_progress' | 'resolved' | 'closed';

export interface Alert {
  id: string;
  project_id: string;
  project_name?: string; // For display purposes
  rule_id?: string; // Optional for mock data
  type?: string; // Alert category (Legal, Technical, Financial, etc.)
  severity: Severity;
  status: AlertStatus;
  title: string;
  description: string;
  source_clause_id?: string;
  affected_entity_ids?: string[];
  evidence_json?: Record<string, any>;
  created_at: string;
  updated_at: string;
  resolved_at?: string;
  resolved_by?: string;
}

export interface Project {
  id: string;
  tenant_id?: string;
  name: string;
  description?: string;
  code?: string;
  project_type?: ProjectType;
  status: ProjectStatus;
  estimated_budget?: number;
  currency?: string;
  coherence_score?: number;
  open_alerts?: number;
  critical_alerts?: number;
  budget_used?: number;
  metadata?: Record<string, any>;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  code?: string;
  project_type?: ProjectType;
  status?: ProjectStatus;
  estimated_budget?: number;
  currency?: string;
  metadata?: Record<string, any>;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  code?: string;
  project_type?: ProjectType;
  status?: ProjectStatus;
  estimated_budget?: number;
  currency?: string;
  metadata?: Record<string, any>;
}

export interface ProjectStats {
  total_projects: number;
  active_projects: number;
  completed_projects: number;
  draft_projects: number;
  archived_projects: number;
  average_coherence_score: number;
}

export interface ProjectListResponse {
  items: Project[];
  total: number;
  page: number;
  per_page: number;
  pages: number;
}

// Activity type for activity timeline
export interface Activity {
  id: string;
  type: 'project_created' | 'document_uploaded' | 'analysis_completed' | 'alert_created' | 'alert_resolved' | 'status_changed' | 'score_changed' | 'stakeholder_added';
  project_id?: string; // Optional for mock data
  user_id?: string;
  user_name?: string;
  description: string;
  metadata?: Record<string, any>;
  timestamp?: string; // Alias for created_at
  created_at?: string;
}

// Filter and query types
export interface ProjectFilters {
  status?: ProjectStatus | ProjectStatus[];
  project_type?: ProjectType | ProjectType[];
  min_score?: number;
  max_score?: number;
  search?: string;
  created_after?: string;
  created_before?: string;
}

export interface ProjectSortOptions {
  field: 'name' | 'created_at' | 'updated_at' | 'coherence_score' | 'status';
  order: 'asc' | 'desc';
}

// Stakeholder types
export type StakeholderPower = 'high' | 'medium' | 'low' | number; // Number 1-10 for power/interest matrix
export type StakeholderInterest = 'high' | 'medium' | 'low' | number;

export interface Stakeholder {
  id: string;
  project_id?: string; // Optional for mock data
  name: string;
  role?: string;
  organization?: string;
  email?: string;
  phone?: string;
  power: StakeholderPower;
  interest: StakeholderInterest;
  engagement?: string; // critical, active, passive
  initials?: string; // For avatar display
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

// KPI Data for dashboards
export interface KPIData {
  coherenceScore: number;
  coherenceTrend?: number; // Percentage change
  activeProjects: number;
  projectsAtRisk?: number;
  openAlerts?: number;
  criticalAlerts: number;
  documentsAnalyzed?: number;
  budgetUsed?: number; // Percentage
  aiSpendCurrent?: number;
  aiSpendLimit?: number;
}
