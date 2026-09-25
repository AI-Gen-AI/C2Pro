/**
 * PJ-01 run classification: a technically green backend is not a usable journey.
 */

export type Pj01Classification = "USABLE" | "TECHNICALLY_FUNCTIONAL" | "FAIL";

export interface RunFinding {
  kind: "gap" | "violation";
  code: string;
  step: string;
  detail: string;
  /** Blocking findings fail the run; non-blocking ones cap it at TECHNICALLY_FUNCTIONAL. */
  blocking: boolean;
}

export function classifyRun(input: { failedSteps: number; findings: RunFinding[] }): Pj01Classification {
  if (input.failedSteps > 0 || input.findings.some((finding) => finding.blocking)) return "FAIL";
  if (input.findings.length > 0) return "TECHNICALLY_FUNCTIONAL";
  return "USABLE";
}
