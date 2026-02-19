/**
 * Test Suite ID: S3-07
 * Roadmap Reference: S3-07 Severity badge + Stakeholder Map + RACI
 */

export interface RaciAssignment {
  stakeholderId: string;
  role: "R" | "A" | "C" | "I" | "";
}

export interface RaciWorkItem {
  workItemId: string;
  assignments: RaciAssignment[];
}

export interface RaciViolation {
  workItemId: string;
  code: "MULTIPLE_ACCOUNTABLE";
}

export function resolveRaciGridViolations(items: RaciWorkItem[]): RaciViolation[] {
  const violations: RaciViolation[] = [];

  for (const item of items) {
    const accountableCount = item.assignments.filter((assignment) => assignment.role === "A").length;
    if (accountableCount > 1) {
      violations.push({
        workItemId: item.workItemId,
        code: "MULTIPLE_ACCOUNTABLE",
      });
    }
  }

  return violations;
}

