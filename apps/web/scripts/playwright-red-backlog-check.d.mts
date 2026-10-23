/** Why a parsed Playwright JSON report is not a RED inventory, or null. */
export function redBacklogProblem(report: unknown): string | null;

export const REPORT_PATH: string;

/** CLI entry: returns the process exit code for the report at file. */
export function main(file?: string, log?: (message: string) => void): number;
