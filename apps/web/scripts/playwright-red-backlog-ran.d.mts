/** Why a parsed Playwright JSON report is not a RED inventory, or null. */
export function redBacklogProblem(report: unknown): string | null;

/** CLI entry: returns the process exit code for the report at file. */
export function main(file: string | undefined, log?: (message: string) => void): number;
