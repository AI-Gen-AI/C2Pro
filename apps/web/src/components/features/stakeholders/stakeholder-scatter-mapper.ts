/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */

export interface StakeholderScatterInput {
  id: string;
  name: string;
  power: number;
  interest: number;
  raci: string;
}

export interface StakeholderScatterPoint {
  id: string;
  label: string;
  x: number;
  y: number;
  group: string;
}

function clamp(value: number): number {
  if (value < 0) return 0;
  if (value > 100) return 100;
  return value;
}

export function mapStakeholdersToScatter(
  stakeholders: StakeholderScatterInput[],
): StakeholderScatterPoint[] {
  return stakeholders.map((stakeholder) => ({
    id: stakeholder.id,
    label: stakeholder.name,
    x: clamp(stakeholder.power * 10),
    y: clamp(stakeholder.interest * 10),
    group: stakeholder.raci,
  }));
}

