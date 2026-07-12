/**
 * Test Suite ID: TASK-FRT-193
 */
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CategoryV2 } from "@/lib/api/contracts";

interface BudgetReconciliation {
  statedTotal: number;
  computedTotal: number;
  contractTotal: number;
  deltaPercent: number;
  sourceLabel: string | null;
}

interface ReconciliationCardProps {
  category: CategoryV2 | null | undefined;
}

const STATED_KEYS = ["stated_total", "statedTotal", "declared_total", "declaredTotal"];
const COMPUTED_KEYS = ["items_sum", "computed_total", "computedTotal", "line_items_sum"];
const CONTRACT_KEYS = ["contract_total", "contractTotal", "contract_price", "contractPrice"];
const DELTA_KEYS = ["deviation_pct", "deviationPercent", "delta_pct", "deltaPercent"];
const SOURCE_KEYS = ["rule_id", "rule_code", "ruleId", "ruleCode", "finding_id", "findingId"];

export function ReconciliationCard({ category }: ReconciliationCardProps) {
  const reconciliation = extractBudgetReconciliation(category);

  if (!reconciliation) {
    return null;
  }

  return (
    <Card data-testid="budget-reconciliation">
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle>Budget reconciliation</CardTitle>
            <p className="mt-1 text-sm text-muted-foreground">
              Backend DET-BUD totals from structured budget evidence.
            </p>
          </div>
          <Badge variant="secondary">{formatPercent(reconciliation.deltaPercent)}% delta</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 md:grid-cols-3">
          <BudgetFigure label="Stated total" value={reconciliation.statedTotal} />
          <BudgetFigure
            label="Computed from line items"
            value={reconciliation.computedTotal}
          />
          <BudgetFigure label="Contract base" value={reconciliation.contractTotal} />
        </div>
        {reconciliation.sourceLabel ? (
          <p className="mt-4 text-xs text-muted-foreground">
            Source: {reconciliation.sourceLabel}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}

function BudgetFigure({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-md border bg-muted/20 p-3">
      <p className="text-xs font-medium text-muted-foreground">{label}</p>
      <p className="mt-2 font-mono text-xl font-semibold">{formatAmount(value)}</p>
    </div>
  );
}

export function extractBudgetReconciliation(
  category: CategoryV2 | null | undefined,
): BudgetReconciliation | null {
  if (!category || category.category !== "BUDGET") {
    return null;
  }

  const candidates = collectObjects([
    ...(Array.isArray(category.detected_conflicts) ? category.detected_conflicts : []),
    category.calculation_metadata,
  ]);

  const merged = candidates.reduce<Partial<BudgetReconciliation>>((acc, candidate) => {
    return {
      statedTotal: acc.statedTotal ?? readNumber(candidate, STATED_KEYS),
      computedTotal: acc.computedTotal ?? readNumber(candidate, COMPUTED_KEYS),
      contractTotal: acc.contractTotal ?? readNumber(candidate, CONTRACT_KEYS),
      deltaPercent: acc.deltaPercent ?? readNumber(candidate, DELTA_KEYS),
      sourceLabel: acc.sourceLabel ?? readSource(candidate),
    };
  }, {});

  if (
    typeof merged.statedTotal !== "number" ||
    typeof merged.computedTotal !== "number" ||
    typeof merged.contractTotal !== "number"
  ) {
    return null;
  }

  const deltaPercent =
    typeof merged.deltaPercent === "number"
      ? merged.deltaPercent
      : calculateDeltaPercent(merged.statedTotal, merged.computedTotal);

  if (deltaPercent === null) {
    return null;
  }

  return {
    statedTotal: merged.statedTotal,
    computedTotal: merged.computedTotal,
    contractTotal: merged.contractTotal,
    deltaPercent,
    sourceLabel: merged.sourceLabel ?? null,
  };
}

function collectObjects(values: unknown[]): Array<Record<string, unknown>> {
  const objects: Array<Record<string, unknown>> = [];
  const visit = (value: unknown) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      return;
    }

    const record = value as Record<string, unknown>;
    objects.push(record);

    for (const nestedKey of ["raw_data", "metadata", "data", "reconciliation"]) {
      visit(record[nestedKey]);
    }
  };

  values.forEach(visit);
  return objects;
}

function readNumber(record: Record<string, unknown>, keys: string[]) {
  for (const key of keys) {
    const value = record[key];
    if (typeof value === "number" && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === "string" && value.trim()) {
      const parsed = Number(value);
      if (Number.isFinite(parsed)) {
        return parsed;
      }
    }
  }
  return undefined;
}

function readSource(record: Record<string, unknown>) {
  for (const key of SOURCE_KEYS) {
    const value = record[key];
    if (typeof value === "string" && value.trim()) {
      return value;
    }
  }
  return null;
}

function calculateDeltaPercent(statedTotal: number, computedTotal: number) {
  if (statedTotal === 0) {
    return null;
  }
  return (Math.abs(statedTotal - computedTotal) / Math.abs(statedTotal)) * 100;
}

function formatAmount(value: number) {
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number) {
  return new Intl.NumberFormat("en-US", {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(value);
}
