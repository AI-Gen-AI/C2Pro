/**
 * Type definitions for Coherence Score and related entities
 */

export type AlertCategory = 'Legal' | 'Financial' | 'Technical' | 'Schedule' | 'Scope' | 'Quality';

export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low';

export interface SeverityBreakdown {
  critical: number;
  high: number;
  medium: number;
  low: number;
}

export interface CategoryBreakdown {
  category: AlertCategory;
  score: number;
  alert_count: number;
  severity_breakdown: SeverityBreakdown;
  impact_percentage: number;
}

export interface CoherenceScoreDetail {
  overall_score: number;
  category_breakdown: CategoryBreakdown[];
  calculated_at: string;
}

// Mock data for development
export const MOCK_COHERENCE_DETAIL: CoherenceScoreDetail = {
  overall_score: 78,
  calculated_at: new Date().toISOString(),
  category_breakdown: [
    {
      category: 'Legal',
      score: 85,
      alert_count: 7,
      severity_breakdown: {
        critical: 1,
        high: 2,
        medium: 3,
        low: 1,
      },
      impact_percentage: 15,
    },
    {
      category: 'Financial',
      score: 72,
      alert_count: 12,
      severity_breakdown: {
        critical: 2,
        high: 5,
        medium: 3,
        low: 2,
      },
      impact_percentage: 28,
    },
    {
      category: 'Technical',
      score: 68,
      alert_count: 9,
      severity_breakdown: {
        critical: 1,
        high: 3,
        medium: 4,
        low: 1,
      },
      impact_percentage: 22,
    },
    {
      category: 'Schedule',
      score: 92,
      alert_count: 2,
      severity_breakdown: {
        critical: 0,
        high: 1,
        medium: 1,
        low: 0,
      },
      impact_percentage: 8,
    },
    {
      category: 'Scope',
      score: 95,
      alert_count: 1,
      severity_breakdown: {
        critical: 0,
        high: 0,
        medium: 1,
        low: 0,
      },
      impact_percentage: 5,
    },
    {
      category: 'Quality',
      score: 80,
      alert_count: 6,
      severity_breakdown: {
        critical: 1,
        high: 2,
        medium: 2,
        low: 1,
      },
      impact_percentage: 22,
    },
  ],
};
