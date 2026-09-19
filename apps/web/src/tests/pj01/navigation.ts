/**
 * PJ-01 navigation model: every journey step must be reachable through visible navigation.
 *
 * Pure: the browser harness collects `{ name, href }` pairs from the project tabs and asks
 * this module where to click. A `null` answer is a navigability gap to report, never a cue to
 * type a URL.
 */

export interface NavLink {
  name: string;
  href: string;
}

export type ProjectTabKey = "health" | "evidence" | "documents" | "report" | "changes";

/** Health lives on a dedicated route or on the analysis page, depending on the build. */
export const HEALTH_ROUTE_PATTERN = /\/projects\/[0-9a-f-]{36}\/(?:health|analysis)(?:[/?#]|$)/i;

const TAB_RULES: Record<ProjectTabKey, { name: RegExp; paths: string[] }> = {
  health: { name: /health/i, paths: ["health", "analysis"] },
  evidence: { name: /evidence/i, paths: ["evidence"] },
  documents: { name: /documents/i, paths: ["documents"] },
  report: { name: /report/i, paths: ["report"] },
  changes: { name: /changed|changes/i, paths: ["changes"] },
};

function pathnameOf(href: string): string {
  try {
    return new URL(href, "http://pj01.invalid").pathname.replace(/\/+$/, "");
  } catch {
    return href;
  }
}

export function findProjectTab(links: NavLink[], projectId: string, key: ProjectTabKey): NavLink | null {
  const rule = TAB_RULES[key];
  const expectedPaths = new Set(rule.paths.map((segment) => `/projects/${projectId}/${segment}`.toLowerCase()));
  return (
    links.find(
      (link) => rule.name.test(link.name.trim()) && expectedPaths.has(pathnameOf(link.href).toLowerCase()),
    ) ?? null
  );
}
